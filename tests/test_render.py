"""
Tests for quince_mcp.rtsi.render:
- parse_snapshot_refs
- render_state_change (length caps, format, raw mode, pure function)
- render_history (first 2 + last 6 truncation)
"""
import json
from quince_mcp.rtsi.render import (
    classify_causal_outcome,
    parse_snapshot_refs,
    render_history,
    render_observation,
    render_page_state_header,
    render_state_change,
)
from quince_mcp.rtsi.session import HistoryItem


def test_parse_snapshot_refs():
    sample = """
[e1] heading(1) "Welcome to Shop"
[e2] textbox "Search products" type=text
[f1.e10] button "Submit"
[e20] separator
[e25] link "Privacy Policy"
"""
    refs = parse_snapshot_refs(sample)
    assert refs["e1"] == 'heading "Welcome to Shop"'
    assert refs["e2"] == 'textbox "Search products"'
    assert refs["f1.e10"] == 'button "Submit"'
    assert refs["e20"] == 'separator (unnamed)'
    assert refs["e25"] == 'link "Privacy Policy"'


def test_render_state_change_basic():
    sc = {
        "effect": "dom_changed",
        "wait": {"settled": True, "reason": "quiet", "elapsed_ms": 350, "timed_out": False},
        "before": {"url": "https://example.com/login", "title": "Login"},
        "after": {"url": "https://example.com/inbox", "title": "Inbox"},
        "navigated": True,
        "navigation_kind": "spa",
        "dom": {
            "added": [{"ref": "e10", "desc": 'button "Compose"'}],
            "removed": [{"ref": "e1", "desc": 'button "Old"'}, {"ref": "e2", "desc": 'textbox "Search"'}],
            "changed": [{"ref": "e5", "desc": "Refresh", "fields": {"disabled": [False, True]}}],
        },
        "messages": ["Logged in successfully"],
        "validation_errors": [],
        "focus": {"before": "e2", "after": "e10", "after_desc": 'button "Compose"'},
        "scroll": {"before": 0, "after": 100, "max": 1000},
        "new_tabs": [{"tab_id": 12, "url": "https://help.example.com", "title": "Help"}],
        "dialog": {"script_dialog": {"type": "alert", "message": "Notice", "auto_response": "ok"}},
        "no_visible_change": False,
    }
    rendered = render_state_change(sc, action_desc='click [e2] button "Sign in"')
    assert "CHANGE after click [e2] button \"Sign in\":" in rendered
    assert "RESULT: dom_changed | settled (quiet, 350 ms)" in rendered
    assert "PAGE:" in rendered
    assert "https://example.com/inbox" in rendered
    assert "ADDED: [e10] button \"Compose\"" in rendered
    assert "REMOVED: [e1] button \"Old\" | [e2] textbox \"Search\"" in rendered
    assert "CHANGED: [e5] Refresh disabled False→True" in rendered
    assert "MESSAGES: \"Logged in successfully\"" in rendered
    assert "FOCUS: e2 → e10 button \"Compose\"" in rendered
    assert "NEW TABS: [tab 12] https://help.example.com \"Help\"" in rendered
    assert "DIALOG: script alert \"Notice\" (auto-answered ok)" in rendered
    assert len(rendered) <= 900


def test_render_state_change_raw():
    sc = {"effect": "none", "before": {"url": "https://example.com"}}
    raw = render_state_change(sc, raw=True)
    parsed = json.loads(raw)
    assert parsed["effect"] == "none"


def test_render_state_change_caps():
    # Test capping when >8 items in dom added
    sc = {
        "effect": "dom_changed",
        "dom": {
            "added": [{"ref": f"e{i}", "desc": f"item {i}"} for i in range(20)],
            "removed": [{"ref": f"e{100+i}", "desc": f"old {i}"} for i in range(20)],
        },
    }
    rendered = render_state_change(sc)
    assert "+12 more" in rendered


def test_render_history_under_cap():
    items = [
        HistoryItem(step=i, action=f"act {i}", summary_line=f"sum {i}", comparison=f"comp {i}", effect="dom_changed")
        for i in range(5)
    ]
    res = render_history(items)
    assert len(res) == 5
    for i in range(5):
        assert res[i]["action"] == f"act {i}"
        assert res[i]["step"] == i


def test_render_history_over_cap():
    items = [
        HistoryItem(step=i, action=f"act {i}", summary_line=f"sum {i}", comparison=f"comp {i}", effect="dom_changed")
        for i in range(12)
    ]
    res = render_history(items)
    # 2 (first) + 1 (omitted indicator) + 6 (last) = 9 lines
    assert len(res) == 9
    assert res[0]["action"] == "act 0"
    assert res[1]["action"] == "act 1"
    assert res[2]["omitted"] == 4  # 12 - 8 = 4
    assert res[-1]["action"] == "act 11"


def test_render_page_state_header_viewport_and_focus():
    header_top = render_page_state_header({
        "title": "Amazon.com: Shop",
        "url": "https://www.amazon.com/",
        "viewport": {
            "scroll_pct": 0,
            "at_top": True,
            "at_bottom": False,
            "screens_above": 0.0,
            "screens_below": 4.2,
            "can_scroll": ["down"],
            "scrollable_containers": [{"ref": "e15", "role": "region", "name": "Filters"}],
        },
        "focus": {
            "ref": "e3",
            "role": "searchbox",
            "value": "wireless mouse",
            "unsubmitted": True,
        },
    })
    assert "[PAGE] Amazon.com: Shop | https://www.amazon.com/" in header_top
    assert "[VIEWPORT] 0% AT TOP | ~0.0 above | ~4.2 below | can_scroll: down | containers: [e15]" in header_top
    assert '[FOCUS] [e3] searchbox value="wireless mouse" (UNSUBMITTED — press Enter or click submit button)' in header_top

    header_bottom = render_page_state_header({
        "title": "Results",
        "url": "https://www.amazon.com/s?k=mouse",
        "viewport": {
            "scroll_pct": 100,
            "at_top": False,
            "at_bottom": True,
            "screens_above": 3.5,
            "screens_below": 0.0,
            "can_scroll": ["up"],
        },
        "focus": None,
    })
    assert "[VIEWPORT] 100% AT BOTTOM | ~3.5 above | ~0.0 below | can_scroll: up" in header_bottom
    assert "[FOCUS] none" in header_bottom


def test_render_page_state_header_modal_and_observation():
    obs = render_observation({
        "text": '[e41] button "Accept All"\n[e42] button "Close"',
        "observation_meta": {
            "title": "Example",
            "url": "https://example.com",
            "viewport": {
                "scroll_pct": 0,
                "at_top": True,
                "at_bottom": True,
                "screens_above": 0.0,
                "screens_below": 0.0,
                "can_scroll": [],
            },
            "focus": None,
            "modal": {"ref": "e40", "role": "dialog", "name": "Cookie Preferences"},
        },
    })
    assert "[VIEWPORT] 0% AT TOP AT BOTTOM | ~0.0 above | ~0.0 below | can_scroll: none" in obs
    assert '[MODAL] [e40] dialog "Cookie Preferences" open — dismiss with Escape or close button' in obs
    assert '[e41] button "Accept All"' in obs


def test_render_state_change_causal_outcomes_autocomplete_and_modal():
    # Autocomplete listbox
    sc_ac = {
        "effect": "dom_changed",
        "dom": {
            "added": [
                {"ref": "e30", "role": "listbox", "desc": 'listbox "Suggestions"'},
                {"ref": "e31", "role": "option", "desc": 'option "wireless headphones"'},
                {"ref": "e32", "role": "option", "desc": 'option "wireless charger"'},
            ],
            "removed": [],
            "changed": [],
        },
    }
    assert classify_causal_outcome(sc_ac) == "DOM_UPDATED"
    rendered_ac = render_state_change(sc_ac, action_desc='type into [e3] searchbox "Search"')
    assert "[LAST ACTION] DOM_UPDATED — Autocomplete suggestions appeared [e30..e32]" in rendered_ac

    # Dialog modal
    sc_modal = {
        "effect": "dom_changed",
        "modal_opened": True,
        "modal_ref": "e50",
        "dom": {
            "added": [{"ref": "e50", "role": "dialog", "desc": 'dialog "Sign in"'}],
            "removed": [],
            "changed": [],
        },
    }
    assert classify_causal_outcome(sc_modal) == "DOM_UPDATED"
    rendered_modal = render_state_change(sc_modal, action_desc="click [e10]")
    assert "[LAST ACTION] DOM_UPDATED — Modal/dialog opened [e50]" in rendered_modal

    # VALUE_CHANGED on searchbox
    sc_val = {
        "effect": "value_set",
        "target": {"ref": "e3", "role": "searchbox"},
        "dom": {
            "added": [],
            "removed": [],
            "changed": [{"ref": "e3", "desc": 'searchbox "Search"', "fields": {"value": ["", "laptop"]}}],
        },
    }
    assert classify_causal_outcome(sc_val) == "VALUE_CHANGED"
    rendered_val = render_state_change(sc_val, action_desc='type into [e3] searchbox "Search"')
    assert "[LAST ACTION] VALUE_CHANGED — Input value updated; page did NOT navigate and form is not yet submitted." in rendered_val

    # SCROLLED
    sc_scroll = {
        "effect": "none",
        "scroll": {"before": 0, "after": 640, "max": 2000, "pct": 32, "at_bottom": False, "revealed_headings": ['[e25] "Specs"']},
    }
    assert classify_causal_outcome(sc_scroll) == "SCROLLED"
    rendered_scroll = render_state_change(sc_scroll, action_desc="scroll down")
    assert "[LAST ACTION] SCROLLED — Viewport at 32%" in rendered_scroll

    # NO_EFFECT
    sc_none = {"effect": "none", "no_visible_change": True}
    assert classify_causal_outcome(sc_none) == "NO_EFFECT"
    rendered_none = render_state_change(sc_none, action_desc="click [e9]")
    assert "[LAST ACTION] NO_EFFECT — Action had no effect." in rendered_none
