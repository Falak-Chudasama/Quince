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

CAUSAL_OUTCOMES = ("NAVIGATED", "DOM_UPDATED", "VALUE_CHANGED", "SCROLLED", "NO_EFFECT")


def _trunc(s: str, n: int) -> str:
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + "…"


def classify_causal_outcome(sc: dict[str, Any]) -> str:
    """
    Classify a state_change dict into one of the 5 causal outcomes:
    NAVIGATED | DOM_UPDATED | VALUE_CHANGED | SCROLLED | NO_EFFECT.
    """
    explicit = sc.get("causal_outcome")
    if explicit in CAUSAL_OUTCOMES:
        return str(explicit)

    effect = sc.get("effect", "none")
    if sc.get("navigated") or effect == "navigated":
        return "NAVIGATED"

    dom = sc.get("dom", {})
    added = dom.get("added", [])
    removed = dom.get("removed", [])
    changed = dom.get("changed", [])

    has_structural_change = (
        bool(added)
        or bool(removed)
        or bool(sc.get("modal_opened"))
        or bool(sc.get("autocomplete_appeared"))
        or any(
            any(k not in ("value", "checked") for k in (c.get("fields") or {}).keys())
            for c in changed
        )
    )
    if has_structural_change or effect == "dom_changed":
        return "DOM_UPDATED"

    has_value_change = any(
        "value" in (c.get("fields") or {}) or "checked" in (c.get("fields") or {})
        for c in changed
    )
    if has_value_change or effect == "value_set":
        return "VALUE_CHANGED"

    scroll = sc.get("scroll", {})
    if (
        scroll
        and scroll.get("before") is not None
        and scroll.get("after") is not None
        and abs(scroll["after"] - scroll["before"]) > 2
    ):
        return "SCROLLED"

    return "NO_EFFECT"


def render_page_state_header(
    meta: dict[str, Any],
    *,
    unsubmitted_search: bool = False,
) -> str:
    """
    Render the compact deterministic Page State Header (~50-70 tokens):
      [PAGE] ...
      [VIEWPORT] ...
      [FOCUS] ...
      [MODAL] ... (when open)
    """
    lines: list[str] = []
    title = _trunc(meta.get("title") or "(untitled)", 50)
    url = _trunc(meta.get("url") or "", 80)
    if title or url:
        lines.append(f"[PAGE] {title} | {url}")

    vp = meta.get("viewport")
    if isinstance(vp, dict):
        pct = vp.get("scroll_pct", 0)
        flags: list[str] = []
        if vp.get("at_top"):
            flags.append("AT TOP")
        if vp.get("at_bottom"):
            flags.append("AT BOTTOM")
        flag_str = (" " + " ".join(flags)) if flags else ""
        above = float(vp.get("screens_above", 0.0))
        below = float(vp.get("screens_below", 0.0))
        can_scroll_list = vp.get("can_scroll") or []
        can_scroll_str = ",".join(can_scroll_list) if can_scroll_list else "none"
        containers = vp.get("scrollable_containers") or []
        container_str = (
            " | containers: " + ",".join(f"[{c.get('ref', '?')}]" for c in containers[:3])
            if containers
            else ""
        )
        lines.append(
            f"[VIEWPORT] {pct}%{flag_str} | ~{above:.1f} above | ~{below:.1f} below | can_scroll: {can_scroll_str}{container_str}"
        )

    focus = meta.get("focus")
    if isinstance(focus, dict) and focus.get("ref"):
        f_ref = focus["ref"]
        f_role = focus.get("role", "element")
        f_val = focus.get("value", "")
        val_part = f' value="{_trunc(f_val, 30)}"' if f_val else ""
        is_unsub = bool(focus.get("unsubmitted")) or (
            unsubmitted_search and f_role in ("searchbox", "textbox", "combobox") and bool(f_val)
        )
        unsub_part = " (UNSUBMITTED — press Enter or click submit button)" if is_unsub else ""
        lines.append(f"[FOCUS] [{f_ref}] {f_role}{val_part}{unsub_part}")
    elif isinstance(vp, dict) or focus is not None:
        lines.append("[FOCUS] none")

    modal = meta.get("modal")
    if isinstance(modal, dict) and modal.get("ref"):
        m_ref = modal["ref"]
        m_role = modal.get("role", "dialog")
        m_name = modal.get("name", "")
        m_name_part = f' "{_trunc(m_name, 40)}"' if m_name else ""
        lines.append(
            f"[MODAL] [{m_ref}] {m_role}{m_name_part} open — dismiss with Escape or close button"
        )

    return "\n".join(lines)


def render_observation(
    snap: dict[str, Any],
    *,
    unsubmitted_search: bool = False,
    recovery_directive: str = "",
) -> str:
    """
    Ensure snapshot observation has the deterministic Page State Header and any
    active recovery directive or unsubmitted-search hint.
    """
    text = snap.get("text", "")
    meta = snap.get("observation_meta") or snap.get("page") or {}

    parts: list[str] = []
    if recovery_directive:
        parts.append(f"[RECOVERY] {recovery_directive}")

    if not text.lstrip().startswith("[PAGE]") and (meta.get("viewport") or meta.get("url")):
        header = render_page_state_header(meta, unsubmitted_search=unsubmitted_search)
        if header:
            parts.append(header)

    if text:
        parts.append(text)

    rendered = "\n".join(parts)
    if unsubmitted_search and "(UNSUBMITTED" not in rendered:
        rendered = (
            "[HINT] Search/text input has an UNSUBMITTED value — press Enter or click submit button.\n"
            + rendered
        )
    return rendered


def _format_ref_range(items: list[dict[str, Any]]) -> str:
    refs = [str(el.get("ref", "")) for el in items if el.get("ref")]
    if not refs:
        return ""
    if len(refs) == 1:
        return refs[0]
    if len(refs) == 2:
        return ", ".join(refs)
    return f"{refs[0]}..{refs[-1]}"


def _render_last_action_line(sc: dict[str, Any], outcome: str, action_desc: str) -> str:
    after_url = sc.get("after", {}).get("url", "")
    after_title = sc.get("after", {}).get("title", "")
    dom = sc.get("dom", {})
    added = dom.get("added", [])

    if outcome == "NAVIGATED":
        dest = _trunc(after_title or after_url, 60)
        return f"[LAST ACTION] NAVIGATED — Page changed to {dest}; fresh top-of-page snapshot below."

    if outcome == "DOM_UPDATED":
        is_autocomplete = bool(sc.get("autocomplete_appeared")) or any(
            el.get("role") in ("listbox", "option")
            or str(el.get("desc", "")).startswith(("listbox", "option"))
            for el in added
        )
        if is_autocomplete:
            rr = _format_ref_range(added)
            ref_hint = f" [{rr}]" if rr else ""
            return f"[LAST ACTION] DOM_UPDATED — Autocomplete suggestions appeared{ref_hint} — click a suggestion or press Enter."

        is_modal = bool(sc.get("modal_opened")) or any(
            el.get("role") == "dialog" or str(el.get("desc", "")).startswith("dialog")
            for el in added
        )
        if is_modal:
            mref = sc.get("modal_ref") or next(
                (el.get("ref") for el in added if el.get("role") == "dialog" or str(el.get("desc", "")).startswith("dialog")),
                "",
            )
            mref_str = f" [{mref}]" if mref else ""
            return f"[LAST ACTION] DOM_UPDATED — Modal/dialog opened{mref_str} — interact with it or dismiss with Escape."

        rr = _format_ref_range(added)
        if rr:
            return f"[LAST ACTION] DOM_UPDATED — New elements appeared [{rr}]."
        return "[LAST ACTION] DOM_UPDATED — Page structure updated."

    if outcome == "VALUE_CHANGED":
        target_role = (sc.get("target") or {}).get("role", "") or (sc.get("focus") or {}).get("after_role", "")
        is_text = target_role in ("searchbox", "textbox", "combobox") or "type " in action_desc.lower()
        if is_text:
            return "[LAST ACTION] VALUE_CHANGED — Input value updated; page did NOT navigate and form is not yet submitted."
        return "[LAST ACTION] VALUE_CHANGED — Input/toggle value updated."

    if outcome == "SCROLLED":
        scroll = sc.get("scroll", {})
        pct = scroll.get("pct")
        at_bot = scroll.get("at_bottom")
        revealed = scroll.get("revealed_headings") or []
        pos_str = f"{pct}%" if pct is not None else f"{scroll.get('before', 0)}→{scroll.get('after', 0)}"
        bot_str = " (AT BOTTOM)" if at_bot else ""
        rev_str = f" | revealed: {', '.join(revealed[:2])}" if revealed else ""
        return f"[LAST ACTION] SCROLLED — Viewport at {pos_str}{bot_str}{rev_str}."

    return "[LAST ACTION] NO_EFFECT — Action had no effect. Element may be obscured, disabled, or require Enter, Escape, or scrolling."


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
    outcome = classify_causal_outcome(sc)
    wait_info = sc.get("wait", {})
    settled = wait_info.get("settled", True)
    reason = wait_info.get("reason", "")
    elapsed = wait_info.get("elapsed_ms", 0)
    timed_out = wait_info.get("timed_out", False)

    settle_str = "timed out" if timed_out else f"{reason}, {elapsed} ms"
    lines.append(f"RESULT: {effect} | {'settled' if settled else 'unsettled'} ({settle_str})")
    lines.append(_render_last_action_line(sc, outcome, action_desc))

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
    if sc.get("recovery_directive"):
        lines.append(f"RECOVERY: {sc['recovery_directive']}")

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
