"""
Tests for quince_mcp.rtsi.render:
- parse_snapshot_refs
- render_state_change (length caps, format, raw mode, pure function)
- render_history (first 2 + last 6 truncation)
"""
import json
from quince_mcp.rtsi.render import parse_snapshot_refs, render_history, render_state_change
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
