from __future__ import annotations

import ctypes
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from quince_mcp.menu_node import MenuNode

IS_WINDOWS = os.name == "nt"
MATCH_THRESHOLD = 0.80


@dataclass(frozen=True)
class AppEntry:
    name: str
    path: str
    aliases: tuple[str, ...] = ()


_COMMON_ALIASES = {
    "file explorer": ("explorer.exe", "explorer"),
    "explorer": ("explorer.exe", "file explorer"),
    "browser": ("chrome", "edge", "firefox", "browsing", "internet"),
    "browsing": ("browser", "internet", "web"),
    "terminal": ("windows terminal", "wt", "powershell", "cmd"),
    "code": ("visual studio code", "vs code", "vscode"),
    "vscode": ("visual studio code", "vs code", "code"),
    "calculator": ("calc", "windows calculator"),
    "notepad": ("text editor",),
    "task manager": ("taskmgr", "task manager"),
}

_PROCESS_ALIASES = {
    "chrome": ("chrome.exe",),
    "google chrome": ("chrome.exe",),
    "edge": ("msedge.exe",),
    "microsoft edge": ("msedge.exe",),
    "firefox": ("firefox.exe",),
    "visual studio code": ("code.exe",),
    "vs code": ("code.exe",),
    "code": ("code.exe",),
    "spotify": ("spotify.exe",),
    "discord": ("discord.exe",),
    "telegram": ("telegram.exe",),
    "whatsapp": ("whatsapp.exe",),
    "notepad": ("notepad.exe",),
    "calculator": ("calculatorapp.exe", "calc.exe"),
    "terminal": ("windowsterminal.exe", "wt.exe"),
    "powershell": ("powershell.exe", "pwsh.exe"),
    "cmd": ("cmd.exe",),
    "explorer": ("explorer.exe",),
    "file explorer": ("explorer.exe",),
    "task manager": ("taskmgr.exe",),
    "steam": ("steam.exe",),
    "obsidian": ("obsidian.exe",),
    "lm studio": ("lm studio.exe", "lmstudio.exe"),
}

_BROWSER_PROCESSES = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"}

_APP_ALIAS_GROUPS = {
    "google chrome": {"chrome", "browser", "browsing", "internet", "web"},
    "microsoft edge": {"edge", "browser", "browsing", "internet", "web"},
    "mozilla firefox": {"firefox", "browser", "browsing", "internet", "web"},
    "visual studio code": {"code", "vscode", "vs code", "editor"},
    "windows terminal": {"terminal", "shell"},
    "command prompt": {"cmd", "command line", "terminal"},
    "powershell": {"powershell", "pwsh", "terminal", "shell"},
    "file explorer": {"explorer", "files", "file manager"},
    "task manager": {"taskmgr", "process manager"},
    "calculator": {"calc", "calculator"},
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _clean_app_query(text: str) -> str:
    value = _norm(text)
    value = re.sub(r"^(please\s+)?(open|launch|start|run|close|quit|exit)\s+", "", value)
    value = re.sub(r"\s+(on|in|at)\s+(the\s+)?(browsing|browser|desktop|window).*$", "", value)
    value = re.sub(r"\s+app$", "", value)
    return value.strip()


def _score(query: str, candidate: str) -> float:
    q = _norm(query)
    c = _norm(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    q_tokens, c_tokens = set(q.split()), set(c.split())
    token_score = len(q_tokens & c_tokens) / max(len(q_tokens), 1)
    seq = SequenceMatcher(None, q, c).ratio()
    compact = SequenceMatcher(None, q.replace(" ", ""), c.replace(" ", "")).ratio()
    substring = 1.0 if q in c or c in q else 0.0
    return max(seq, compact, 0.92 * token_score, 0.90 * substring)


def _start_menu_entries() -> list[AppEntry]:
    if not IS_WINDOWS:
        return []

    roots = [
        Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    entries: list[AppEntry] = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob("*"):
                if path.suffix.lower() not in {".lnk", ".exe", ".url"}:
                    continue
                key = str(path).lower()
                if key in seen:
                    continue
                seen.add(key)
                name = path.stem.strip()
                if not name:
                    continue
                entries.append(AppEntry(name=name, path=str(path)))
        except (OSError, PermissionError):
            continue
    return entries


def _well_known_entries() -> list[AppEntry]:
    if not IS_WINDOWS:
        return []
    entries: list[AppEntry] = []

    for name, commands in {
        "File Explorer": ("explorer.exe",),
        "Calculator": ("calc.exe",),
        "Notepad": ("notepad.exe",),
        "Task Manager": ("taskmgr.exe",),
        "Command Prompt": ("cmd.exe",),
        "PowerShell": ("powershell.exe",),
        "Windows Terminal": ("wt.exe",),
    }.items():
        executable = shutil.which(commands[0]) or commands[0]
        entries.append(AppEntry(name=name, path=executable))

    return entries


def _browser_entry() -> AppEntry | None:
    if not IS_WINDOWS:
        return None
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice",
        ) as key:
            prog_id = str(winreg.QueryValueEx(key, "ProgId")[0]).lower()
    except (OSError, ImportError):
        prog_id = ""

    mapping = {
        "chromehtml": ("Google Chrome", "chrome.exe"),
        "mse edgehtm": ("Microsoft Edge", "msedge.exe"),
        "msedgehtm": ("Microsoft Edge", "msedge.exe"),
        "firefoxurl": ("Mozilla Firefox", "firefox.exe"),
    }
    for prefix, (name, executable) in mapping.items():
        if prog_id.startswith(prefix):
            path = shutil.which(executable) or executable
            return AppEntry(name=name, path=path, aliases=("browser", "browsing", "internet"))

    # Guaranteed browser fallback: ask Windows to open a blank HTTP page.
    return AppEntry(name="Default Browser", path="http://example.com", aliases=("browser", "browsing", "internet", "web"))


def _resolve_app(app: str) -> tuple[AppEntry | None, float]:
    query = _clean_app_query(app)
    if not query:
        return None, 0.0

    if query in {"browser", "browsing", "internet", "web"}:
        entry = _browser_entry()
        return entry, 1.0 if entry else 0.0

    entries = _well_known_entries() + _start_menu_entries()
    browser = _browser_entry()
    if browser:
        entries.append(browser)

    # Deduplicate by normalized display name + path.
    unique: dict[tuple[str, str], AppEntry] = {}
    for entry in entries:
        unique[(_norm(entry.name), entry.path.lower())] = entry
    entries = list(unique.values())

    best: AppEntry | None = None
    best_score = 0.0
    for entry in entries:
        entry_key = _norm(entry.name)
        names = list((entry.name,) + entry.aliases + _COMMON_ALIASES.get(entry_key, ()))
        for canonical, aliases in _APP_ALIAS_GROUPS.items():
            if entry_key == _norm(canonical) or any(alias in entry_key for alias in aliases):
                names.append(canonical)
                names.extend(aliases)
            if query in aliases and (entry_key == _norm(canonical) or _score(canonical, entry.name) >= MATCH_THRESHOLD):
                names.append(query)

        process_aliases = _PROCESS_ALIASES.get(entry_key, ())
        names.extend(process_aliases)

        for name in names:
            score = 1.0 if _norm(name) == query else _score(app, name)
            if score > best_score:
                best = entry
                best_score = score

    return (best, best_score) if best_score >= MATCH_THRESHOLD else (None, best_score)


# ---- Windows window primitives -------------------------------------------------

if IS_WINDOWS:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def _window_rows() -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)

            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            process_name = ""
            handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                try:
                    size = ctypes.c_ulong(4096)
                    path_buffer = ctypes.create_unicode_buffer(4096)
                    if kernel32.QueryFullProcessImageNameW(handle, 0, path_buffer, ctypes.byref(size)):
                        process_name = os.path.basename(path_buffer.value).lower()
                finally:
                    kernel32.CloseHandle(handle)

            rows.append({
                "hwnd": int(hwnd),
                "title": buffer.value,
                "process": process_name,
            })
            return True

        user32.EnumWindows(EnumWindowsProc(callback), 0)
        return rows

    def _focus(hwnd: int) -> None:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        else:
            user32.ShowWindow(hwnd, 5)  # SW_SHOW
        user32.SetForegroundWindow(hwnd)


def _find_window(window: str) -> tuple[dict[str, Any] | None, float]:
    if not IS_WINDOWS:
        return None, 0.0
    query = _norm(window)
    if query in {"browsing", "browser", "web", "internet"}:
        for row in _window_rows():
            if row["process"] in _BROWSER_PROCESSES:
                return row, 1.0

    best = None
    best_score = 0.0
    for row in _window_rows():
        title_score = _score(window, row["title"])
        process_score = _score(window, row["process"])
        score = max(title_score, process_score)
        if score > best_score:
            best, best_score = row, score
    return (best, best_score) if best_score >= MATCH_THRESHOLD else (None, best_score)


def open_app(app: str, window: str | None = None) -> dict[str, Any]:
    if not IS_WINDOWS:
        return {"ok": False, "error": "App control is supported only on Windows."}
    app = (app or "").strip()
    if not app:
        return {"ok": False, "error": "app is required"}

    entry, score = _resolve_app(app)
    if entry is None:
        return {"ok": False, "matched": False, "threshold": MATCH_THRESHOLD, "score": round(score, 3), "error": f"No app matched '{app}' at the 80% threshold."}

    target_window = None
    target_score = None
    if window:
        target_window, target_score = _find_window(window)
        if target_window:
            try:
                _focus(target_window["hwnd"])
            except Exception:
                target_window = None

    try:
        if entry.path.startswith("http://") or entry.path.startswith("https://"):
            os.startfile(entry.path)
        elif entry.path.lower().endswith((".lnk", ".url")):
            os.startfile(entry.path)
        else:
            subprocess.Popen([entry.path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {
            "ok": True,
            "action": "open",
            "app": entry.name,
            "matched_input": app,
            "match_score": round(score, 3),
            "window_requested": window,
            "window_found": bool(target_window),
            "window_match_score": round(target_score, 3) if target_score is not None else None,
            "launched_window": launched_window["title"] if launched_window else None,
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "app": entry.name, "match_score": round(score, 3), "error": str(exc)}


def close_app(app: str) -> dict[str, Any]:
    if not IS_WINDOWS:
        return {"ok": False, "error": "App control is supported only on Windows."}
    app = (app or "").strip()
    if not app:
        return {"ok": False, "error": "app is required"}

    entry, score = _resolve_app(app)
    if entry is None:
        return {"ok": False, "matched": False, "threshold": MATCH_THRESHOLD, "score": round(score, 3), "error": f"No app matched '{app}' at the 80% threshold."}

    process_names = set(_PROCESS_ALIASES.get(_norm(entry.name), ()))
    process_names.add(Path(entry.path).name.lower())

    closed = 0
    for row in _window_rows():
        title_score = _score(entry.name, row["title"])
        same_process = bool(row["process"] and row["process"] in process_names)
        if same_process or title_score >= MATCH_THRESHOLD:
            try:
                user32.PostMessageW(row["hwnd"], 0x0010, 0, 0)  # WM_CLOSE
                closed += 1
            except Exception:
                continue

    return {
        "ok": True,
        "action": "close",
        "app": entry.name,
        "match_score": round(score, 3),
        "windows_signalled": closed,
    }


def focus_window(window: str) -> dict[str, Any]:
    if not IS_WINDOWS:
        return {"ok": False, "error": "Window control is supported only on Windows."}
    window = (window or "").strip()
    if not window:
        return {"ok": False, "error": "window is required"}
    row, score = _find_window(window)
    if row is None:
        return {"ok": False, "matched": False, "threshold": MATCH_THRESHOLD, "score": round(score, 3), "error": f"No window matched '{window}' at the 80% threshold."}
    try:
        _focus(row["hwnd"])
    except Exception as exc:
        return {"ok": False, "error": str(exc), "window": row["title"]}
    return {
        "ok": True,
        "action": "focus_window",
        "window": row["title"],
        "process": row["process"],
        "match_score": round(score, 3),
    }


def media_control(action: str = "play_pause") -> dict[str, Any]:
    if not IS_WINDOWS:
        return {"ok": False, "error": "Media key control is supported only on Windows."}
    normalized = _norm(action)
    aliases = {
        "play": "play",
        "pause": "pause",
        "play pause": "play_pause",
        "toggle": "play_pause",
        "resume": "play",
    }
    selected = aliases.get(normalized)
    if selected is None:
        return {"ok": False, "error": "action must be play, pause, or play_pause"}

    # The Windows media key is a toggle. There is no universal play/pause
    # distinction through this API, so play/pause/resume all use the media toggle.
    key = "play/pause media"
    try:
        import keyboard
        keyboard.send(key)
    except Exception:
        # Dependency-free fallback through user32 keybd_event.
        try:
            user32.keybd_event(0xB3, 0, 0, 0)  # VK_MEDIA_PLAY_PAUSE
            user32.keybd_event(0xB3, 0, 2, 0)  # KEYEVENTF_KEYUP
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    return {"ok": True, "action": selected, "key": key, "note": "Windows exposes this as a media toggle; exact play versus pause state is not guaranteed."}


apps_root = MenuNode(
    "apps",
    "Apps",
    "Control Windows applications and top-level windows. Use for open, close, focus, or media-control requests. App names are resolved deterministically against Start Menu entries and common aliases with an 80% minimum match; vague terms like browser/browsing are supported. A requested window is treated as an existing Windows window to focus before launching, not as a virtual desktop or an embedded child window.",
)

apps_root.add_child(MenuNode(
    "open_app",
    "Open App",
    "Open the best matching Windows app. Use this for 'open', 'launch', 'start', 'run', or vague app names. Match input against installed Start Menu app names and aliases; do not guess below the 80% threshold. Optional window selects an existing target window such as 'browsing' and focuses it before launch.",
    handler=open_app,
    parameters={
        "type": "object",
        "properties": {
            "app": {"type": "string", "description": "App name or vague alias, e.g. chrome, browser, code, terminal."},
            "window": {"type": "string", "description": "Optional existing target window, e.g. browsing, browser, YouTube, VS Code project."},
        },
        "required": ["app"],
    },
))

apps_root.add_child(MenuNode(
    "close_app",
    "Close App",
    "Gracefully close matching application windows. Use for 'close', 'quit', 'exit', or 'shut' requests. Do not force-kill processes; send normal WM_CLOSE signals and report if no window matched.",
    handler=close_app,
    parameters={
        "type": "object",
        "properties": {"app": {"type": "string", "description": "App name or vague alias."}},
        "required": ["app"],
    },
))

apps_root.add_child(MenuNode(
    "focus_window",
    "Focus Window",
    "Bring an existing Windows window to the foreground. Use when the user says switch to, go to, focus, bring up, or use a named window. 'browsing'/'browser' resolves to a visible browser window.",
    handler=focus_window,
    parameters={
        "type": "object",
        "properties": {"window": {"type": "string", "description": "Window title/type, e.g. browsing, browser, YouTube, terminal."}},
        "required": ["window"],
    },
))

apps_root.add_child(MenuNode(
    "media_control",
    "Media Control",
    "Control system media playback. Use for play, pause, resume, toggle, or 'stop/start the music' requests. Windows exposes a universal media toggle; the exact play/pause state may be unavailable, so report that honestly.",
    handler=media_control,
    parameters={
        "type": "object",
        "properties": {"action": {"type": "string", "enum": ["play", "pause", "play_pause"], "description": "Requested media action; play/pause both use the Windows media toggle."}},
        "required": [],
    },
))
