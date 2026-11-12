"""
RTSI render helpers — pure functions, no I/O.

render_state_change: converts raw state_change JSON -> formatted text (≤~900 chars).
parse_snapshot_refs: extract ref -> 'role "name"' from snapshot text.
render_history: format history list for JUDGE response.
"""
from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Snapshot ref parser
# ---------------------------------------------------------------------------

_REF_LINE_RE = re.compile(
    r"^\[((f\d+\.)?e\d+)\]\s+(\w+)(?:\(\d+\))?\s+\"([^\"]*)\"|^\[((f\d+\.)?e\d+)\]\s+(\w+)(?:\(\d+\))?",
    re.MULTILINE,
)


def parse_snapshot_refs(snapshot_text: str) -> dict[str, str]:
    """
    Extract {ref: 'role "name"'} from snapshot lines like:
      [e12] button "Send"
      [f1.e3] textbox "Email" type=email
      [e4] heading(1) "Sign in"
    """
    refs: dict[str, str] = {}
    for line in snapshot_text.splitlines():
        line = line.strip()
        m = re.match(r"^\[((f\d+\.)?e\d+)\]\s+(\S+)\s+\"([^\"]*)\"", line)
        if m:
            ref = m.group(1)
            role = m.group(3).split("(")[0]
            name = m.group(4)
            refs[ref] = f'{role} "{name}"'
            continue
        m2 = re.match(r"^\[((f\d+\.)?e\d+)\]\s+(\S+)", line)
        if m2:
            ref = m2.group(1)
            role = m2.group(3).split("(")[0]
            refs[ref] = f'{role} (unnamed)'
    return refs


# ---------------------------------------------------------------------------
# State change renderer
# ---------------------------------------------------------------------------

def _trunc(s: str, n: int) -> str:
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + "…"


def render_state_change(
    sc: dict[str, Any],
    action_desc: str = "",
    ref_desc: dict[str, str] | None = None,
    raw: bool = False,
) -> str:
    """
    Render a state_change dict as human-readable text for the LLM.

    Append Appendix E format: deterministic templates, ≤~900 chars.
    If raw=True: return the JSON representation (debug mode).
    """
    if raw:
        import json
        return json.dumps(sc, indent=2)

    ref_desc = ref_desc or {}
    lines: list[str] = []

    if action_desc:
        lines.append(f"CHANGE after {action_desc}:")

    effect = sc.get("effect", "none")
    wait_info = sc.get("wait", {})
    settled = wait_info.get("settled", True)
    reason = wait_info.get("reason", "")
    elapsed = wait_info.get("elapsed_ms", 0)
    timed_out = wait_info.get("timed_out", False)

    settle_str = "timed out" if timed_out else f"{reason}, {elapsed} ms"
    lines.append(f"RESULT: {effect} | {'settled' if settled else 'unsettled'} ({settle_str})")

    before_url = sc.get("before", {}).get("url", "")
    after_url = sc.get("after", {}).get("url", "")
    after_title = sc.get("after", {}).get("title", "")
    navigated = sc.get("navigated", False)

    page_str = _trunc(after_url, 60)
    if after_title:
        page_str += f" \"{_trunc(after_title, 40)}\""
    if navigated:
        nav_kind = sc.get("navigation_kind", "full")
        lines.append(f"PAGE: {_trunc(before_url, 40)} → {page_str} [{nav_kind}]")
    else:
        lines.append(f"PAGE: {page_str} (unchanged URL)")

    # DOM changes (skip on full navigation)
    if not navigated or sc.get("navigation_kind") != "full":
        dom = sc.get("dom", {})
        added = dom.get("added", [])
        removed = dom.get("removed", [])
        changed = dom.get("changed", [])
        overflow = dom.get("overflow", {})

        def _fmt_el(el: dict[str, Any]) -> str:
            ref = el.get("ref", "?")
            desc = el.get("desc", "")
            return _trunc(f"[{ref}] {desc}", 70)

        if added:
            cap = added[:8]
            rest = len(added) - len(cap) + overflow.get("added", 0)
            s = " | ".join(_fmt_el(e) for e in cap)
            if rest:
                s += f" | +{rest} more"
            lines.append(f"ADDED: {s}")

        if removed:
            cap = removed[:8]
            rest = len(removed) - len(cap) + overflow.get("removed", 0)
            s = " | ".join(_fmt_el(e) for e in cap)
            if rest:
                s += f" | +{rest} more"
            lines.append(f"REMOVED: {s}")

        if changed:
            cap = changed[:8]
            rest = len(changed) - len(cap) + overflow.get("changed", 0)
            parts = []
            for el in cap:
                ref = el.get("ref", "?")
                desc = el.get("desc", "")
                fields = el.get("fields", {})
                if fields:
                    fstr = "; ".join(f"{k} {v[0]}→{v[1]}" for k, v in list(fields.items())[:3])
                    parts.append(_trunc(f"[{ref}] {desc} {fstr}", 70))
                else:
                    parts.append(_trunc(f"[{ref}] {desc}", 70))
            s = " | ".join(parts)
            if rest:
                s += f" | +{rest} more"
            lines.append(f"CHANGED: {s}")

    # Messages / toasts
    messages = sc.get("messages", [])
    if messages:
        msgs = "; ".join(f'"{_trunc(m, 140)}"' for m in messages[:3])
        lines.append(f"MESSAGES: {msgs}")

    # Validation errors
    errors = sc.get("validation_errors", [])
    if errors:
        errs = " | ".join(
            f'[{e.get("ref","?")}] "{_trunc(e.get("message","error"), 80)}"'
            for e in errors[:4]
        )
        lines.append(f"ERRORS: {errs}")

    # Focus change
    focus = sc.get("focus", {})
    f_before = focus.get("before")
    f_after = focus.get("after")
    f_after_desc = focus.get("after_desc", "")
    if f_before or f_after:
        focus_line = f"FOCUS: {f_before or '?'} → {f_after or '?'}"
        if f_after_desc:
            focus_line += f" {_trunc(f_after_desc, 40)}"
        lines.append(focus_line)

    # Scroll
    scroll = sc.get("scroll", {})
    if scroll:
        s_before = scroll.get("before", 0)
        s_after = scroll.get("after", 0)
        s_max = scroll.get("max", 0)
        lines.append(f"SCROLL: {s_before} → {s_after} of {s_max}")

    # New tabs
    new_tabs = sc.get("new_tabs", [])
    if new_tabs:
        tab_strs = "; ".join(
            f'[tab {t.get("tab_id")}] {_trunc(t.get("url","?"), 40)} "{_trunc(t.get("title",""), 30)}"'
            for t in new_tabs[:3]
        )
        lines.append(f"NEW TABS: {tab_strs}")

    # Script dialogs
    dialog = sc.get("dialog", {})
    sd = dialog.get("script_dialog")
    if sd:
        dtype = sd.get("type", "dialog")
        dmsg = _trunc(sd.get("message", ""), 80)
        dauto = sd.get("auto_response", "")
        lines.append(f"DIALOG: script {dtype} \"{dmsg}\" (auto-answered {dauto})")

    # NOTE lines
    if sc.get("no_visible_change"):
        lines.append("NOTE: nothing visibly changed — the action may not have worked.")
    if timed_out:
        lines.append("NOTE: wait timed out — page may still be loading.")
    if sc.get("loop_warning"):
        lines.append(f"NOTE: {sc['loop_warning']}")

    text = "\n".join(lines)
    # Cap at ~900 chars
    if len(text) > 900:
        text = text[:897] + "…"
    return text


# ---------------------------------------------------------------------------
# History renderer (for JUDGE response)
# ---------------------------------------------------------------------------

def render_history(history: list[Any]) -> list[dict[str, Any]]:
    """
    Return comparison_history: first 2 + last 6 items (with omitted count),
    serialized total ≤ ~2000 chars.
    """
    if not history:
        return []

    def item_to_dict(item: Any) -> dict[str, Any]:
        return {
            "step": item.step,
            "action": item.action,
            "summary_line": item.summary_line,
            "comparison": item.comparison,
            "effect": item.effect,
        }

    if len(history) <= 8:
        return [item_to_dict(h) for h in history]

    first2 = [item_to_dict(h) for h in history[:2]]
    last6 = [item_to_dict(h) for h in history[-6:]]
    omitted = len(history) - 8
    return first2 + [{"omitted": omitted}] + last6
