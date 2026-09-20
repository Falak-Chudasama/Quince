from __future__ import annotations

import difflib
import subprocess
import time
from typing import Any

import win32con
import win32gui
import win32process

# --- App list cache -------------------------------------------------------
# Get-StartApps spawns PowerShell and enumerates the Start Menu index, which
# takes real time (hundreds of ms). Re-running it on every open_app() call
# adds avoidable latency to an already multi-hop agentic loop, so we cache
# it and only refresh after TTL_SECONDS.

_APP_CACHE: list[tuple[str, str]] = []
_APP_CACHE_TS: float = 0.0
_APP_CACHE_TTL_SECONDS = 300.0  # 5 min; raise if you rarely install/remove apps


def _get_start_apps(force_refresh: bool = False) -> list[tuple[str, str]]:
    global _APP_CACHE, _APP_CACHE_TS

    now = time.time()
    if not force_refresh and _APP_CACHE and (now - _APP_CACHE_TS) < _APP_CACHE_TTL_SECONDS:
        return _APP_CACHE

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-StartApps | ForEach-Object { \"$($_.Name)`t$($_.AppID)\" }",
            ],
            capture_output=True,
            text=True,
            timeout=10.0,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Don't raise into the MCP tool loop - fall back to whatever we had
        # cached before, even if stale, rather than hard-failing the call.
        return _APP_CACHE

    apps: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if "\t" not in line:
            continue
        name, app_id = line.split("\t", 1)
        if name.strip() and app_id.strip():
            apps.append((name.strip(), app_id.strip()))

    _APP_CACHE = apps
    _APP_CACHE_TS = now
    return apps


def _find_app(app_name: str) -> dict:
    """
    Returns one of:
      {"status": "found", "name": ..., "app_id": ...}
      {"status": "ambiguous", "candidates": [names...]}
      {"status": "not_found"}

    We do not silently accept the top fuzzy match. A small LLM picking
    "app_name" as a free-text argument is exactly the situation where a
    wrong 0.80-similarity guess (e.g. "Word" -> "WordPad") fails silently -
    the tool would report success having opened the wrong app. Instead,
    ambiguous cases are handed back to the caller (LLM) to disambiguate.

    NOTE: if you're seeing "not found" for apps you know are installed
    (e.g. Chrome), print/log `_get_start_apps()`'s raw output once and
    check the exact string Get-StartApps reports for that app - it is
    not always the display name you'd expect, and non-UWP apps' AppID
    is often a raw .lnk path rather than a PackageFamilyName!AppId,
    which also affects whether shell:AppsFolder launches it correctly
    below.
    """
    apps = _get_start_apps()

    exact = [app for app in apps if app[0].lower() == app_name.lower()]
    if exact:
        return {"status": "found", "name": exact[0][0], "app_id": exact[0][1]}

    names = [name for name, _ in apps]
    matches = difflib.get_close_matches(app_name, names, n=3, cutoff=0.80)

    if not matches:
        return {"status": "not_found"}

    if len(matches) == 1:
        matched_name = matches[0]
        app_id = next(app_id for name, app_id in apps if name == matched_name)
        return {"status": "found", "name": matched_name, "app_id": app_id}

    # Multiple plausible matches at similar confidence - don't guess.
    return {"status": "ambiguous", "candidates": matches}


# --- Window confirmation (PID-scoped, never focus-stealing by default) ---


def _windows_for_pid(pid: int) -> list[int]:
    matches: list[int] = []

    def callback(hwnd: int, _: Any) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        if not win32gui.GetWindowText(hwnd).strip():
            return True
        _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
        if window_pid == pid:
            matches.append(hwnd)
        return True

    win32gui.EnumWindows(callback, None)
    return matches


def _find_window_by_title(window_name: str, exclude_hwnds: set[int]) -> int | None:
    """
    Title-substring fallback, used only when PID-scoping finds nothing
    (common for UWP apps launched via explorer.exe/AppsFolder, where the
    visible window's PID often doesn't match the process we Popen'd).
    exclude_hwnds lets us ignore windows that already existed before we
    launched, so we don't "confirm" against something the user already
    had open.
    """
    matches: list[int] = []

    def callback(hwnd: int, _: Any) -> bool:
        if hwnd in exclude_hwnds:
            return True
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd).strip()
        if title and window_name.lower() in title.lower():
            matches.append(hwnd)
        return True

    win32gui.EnumWindows(callback, None)
    return matches[0] if matches else None


def _snapshot_visible_hwnds() -> set[int]:
    hwnds: list[int] = []

    def callback(hwnd: int, acc: list[int]) -> bool:
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd).strip():
            acc.append(hwnd)
        return True

    win32gui.EnumWindows(callback, hwnds)
    return set(hwnds)


def _focus_window(hwnd: int) -> None:
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)


# --- Public tool entry point ----------------------------------------------


def open_app(
    app_name: str,
    window: str | None = None,
    bring_to_front: bool = False,
) -> dict:
    """
    Launches an app by name via the Start Menu index.

    IMPORTANT - two separate knobs, do not conflate them in the tool
    schema that describes this function to the LLM:

      window          -> ONLY used to *confirm* the launch succeeded by
                          polling for a matching window. Never causes
                          focus/foreground by itself.
      bring_to_front   -> the ONLY thing that causes SetForegroundWindow
                          to be called. Defaults to False (stealth).

    If the tool schema's description tells the model that `window`
    controls foreground behavior, the model will pass `window` whenever
    it wants foreground and never learn `bring_to_front` exists (since
    it isn't in the schema) - it will get stealth behavior it didn't ask
    for, and the code will look "broken" when it's actually the schema
    that's wrong. Keep the tool schema's per-argument descriptions in
    sync with this docstring.
    """
    match = _find_app(app_name)

    if match["status"] == "not_found":
        return {
            "success": False,
            "message": f"Application not found: {app_name}",
        }

    if match["status"] == "ambiguous":
        return {
            "success": False,
            "message": (
                f"Multiple apps match '{app_name}': "
                f"{', '.join(match['candidates'])}. Ask the user which one, "
                f"or call again with the exact name."
            ),
            "candidates": match["candidates"],
        }

    matched_name, app_id = match["name"], match["app_id"]

    pre_launch_hwnds = _snapshot_visible_hwnds() if window else set()

    try:
        proc = subprocess.Popen(
            ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        return {
            "success": False,
            "message": f"Failed to launch {matched_name}: {exc}",
        }

    if not window:
        # No confirmation requested - launch is fire-and-forget, no window
        # enumeration at all, no chance of touching an unrelated window.
        return {"success": True, "message": f"Opened {matched_name}"}

    deadline = time.time() + 5.0
    hwnd: int | None = None

    while time.time() < deadline:
        # explorer.exe shell:AppsFolder launches are often proxied through
        # explorer.exe itself rather than keeping proc.pid as the visible
        # window's owner, so PID-scoping against proc.pid is unreliable
        # here specifically for UWP/Store apps. Try PID scoping first, in
        # case it's a traditional win32 app; fall back to a title-substring
        # search excluding pre-existing windows if PID scoping is empty.
        # Verify on your machine which path your target apps actually take.
        pid_matches = _windows_for_pid(proc.pid)
        candidate_hwnds = [h for h in pid_matches if h not in pre_launch_hwnds]

        if candidate_hwnds:
            title = win32gui.GetWindowText(candidate_hwnds[0]).strip()
            if window.lower() in title.lower():
                hwnd = candidate_hwnds[0]
                break

        title_match = _find_window_by_title(window, exclude_hwnds=pre_launch_hwnds)
        if title_match:
            hwnd = title_match
            break

        time.sleep(0.25)

    if hwnd is None:
        return {
            "success": True,
            "message": f"Opened {matched_name}, but window '{window}' was not confirmed",
        }

    if bring_to_front:
        _focus_window(hwnd)
        return {"success": True, "message": f"Opened {matched_name} and focused window '{window}'"}

    return {"success": True, "message": f"Opened {matched_name}, window '{window}' confirmed"}