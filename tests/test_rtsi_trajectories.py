"""
Layer 2: Multi-step RTSI trajectory and failure-mode recovery tests.
Exercises full end-to-end trajectories through RtsiMachine + render.py + session.py.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from quince_mcp.bridge.config import BridgeSettings
from quince_mcp.bridge.protocol import BridgeError
from quince_mcp.rtsi.machine import RtsiMachine
from quince_mcp.rtsi.states import State


def _make_bridge(side_effects: list[dict | Exception]) -> MagicMock:
    bridge = MagicMock()
    bridge.is_connected = True
    bridge.connected_info = {"version": "0.1.0"}
    bridge.call = AsyncMock(side_effect=side_effects)
    return bridge


@pytest.mark.asyncio
async def test_trajectory_amazon_search_without_submit_recovery():
    snap_home = {
        "text": (
            "[PAGE] Amazon.com | https://www.amazon.com/\n"
            "[VIEWPORT] 0% AT TOP | ~0.0 above | ~5.0 below | can_scroll: down\n"
            "[FOCUS] none\n"
            '[e3] searchbox "Search Amazon" [searchbox, enter-submits]\n'
            '[e4] button "Go"'
        ),
        "generation": 1,
        "page": {"url": "https://www.amazon.com/", "title": "Amazon.com"},
        "observation_meta": {"url": "https://www.amazon.com/", "title": "Amazon.com", "state_fingerprint": "fp_home"},
    }
    snap_typed = {
        "text": (
            "[PAGE] Amazon.com | https://www.amazon.com/\n"
            "[VIEWPORT] 0% AT TOP | ~0.0 above | ~5.0 below | can_scroll: down\n"
            '[FOCUS] [e3] searchbox value="usb c hub" (UNSUBMITTED — press Enter or click submit button)\n'
            '[e3] searchbox "Search Amazon" value="usb c hub" [focused] [searchbox, enter-submits]'
        ),
        "generation": 2,
        "page": {"url": "https://www.amazon.com/", "title": "Amazon.com"},
        "observation_meta": {"url": "https://www.amazon.com/", "title": "Amazon.com", "state_fingerprint": "fp_typed"},
    }
    snap_results = {
        "text": (
            "[PAGE] Amazon.com : usb c hub | https://www.amazon.com/s?k=usb+c+hub\n"
            "[VIEWPORT] 0% AT TOP | ~0.0 above | ~6.0 below | can_scroll: down\n"
            "[FOCUS] none\n"
            '[e10] heading(1) "Results"\n'
            '[e11] link "Anker USB-C Hub $25.99"'
        ),
        "generation": 3,
        "page": {"url": "https://www.amazon.com/s?k=usb+c+hub", "title": "Amazon.com : usb c hub"},
        "observation_meta": {"url": "https://www.amazon.com/s?k=usb+c+hub", "title": "Amazon.com : usb c hub", "state_fingerprint": "fp_results"},
    }

    bridge = _make_bridge([
        {"ok": True},  # session.begin
        {"tabs": [{"tab_id": 1, "url": "about:blank", "title": ""}]},  # tabs.list
        {"tab_id": 1, "url": "https://www.amazon.com/", "title": "Amazon.com"},  # tabs.open
        snap_home,  # observation after open-tab
        {
            "state_change": {
                "effect": "value_set",
                "causal_outcome": "VALUE_CHANGED",
                "target": {"ref": "e3", "role": "searchbox"},
                "before": {"url": "https://www.amazon.com/", "title": "Amazon.com"},
                "after": {"url": "https://www.amazon.com/", "title": "Amazon.com", "generation": 2, "state_fingerprint": "fp_typed"},
                "dom": {"added": [], "removed": [], "changed": [{"ref": "e3", "desc": 'searchbox "Search Amazon"', "fields": {"value": ["", "usb c hub"]}}]},
                "wait": {"settled": True, "reason": "quiet", "elapsed_ms": 110},
            }
        },  # act.type(submit=False)
        snap_typed,  # adaptive observation
        snap_typed,  # corrective observation on premature exit
        {
            "state_change": {
                "effect": "navigated",
                "causal_outcome": "NAVIGATED",
                "navigated": True,
                "navigation_kind": "full",
                "before": {"url": "https://www.amazon.com/", "title": "Amazon.com"},
                "after": {"url": "https://www.amazon.com/s?k=usb+c+hub", "title": "Amazon.com : usb c hub", "generation": 3, "state_fingerprint": "fp_results"},
                "wait": {"settled": True, "reason": "navigation_complete", "elapsed_ms": 340},
            }
        },  # act.press_key(Enter)
        snap_results,  # adaptive observation
        snap_results,  # final snapshot on termination
        {"ok": True},  # session.end
    ])

    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    res_entry = await machine.handle("root--browser", {"goal": "Search Amazon for usb c hub"}, describe_root_fn=AsyncMock())
    assert "mode_prompt" in res_entry
    assert "rtsi" in res_entry and "max_hops" in res_entry["rtsi"]

    res_open = await machine.handle("root--browser--open-tab", {"url": "https://www.amazon.com/"}, describe_root_fn=AsyncMock())
    assert res_open["replaces"] == "observation"
    assert "[VIEWPORT] 0% AT TOP" in res_open["result"]["observation"]

    res_type = await machine.handle("root--browser--type-text", {"ref": "e3", "text": "usb c hub", "submit": False}, describe_root_fn=AsyncMock())
    assert "[LAST ACTION] VALUE_CHANGED" in res_type["result"]["state_change_text"]
    assert "UNSUBMITTED" in res_type["result"]["observation"]

    # Premature exit blocked once
    res_premature = await machine.handle("root--browser--successful-termination", {"result_summary": "Searched usb c hub"}, describe_root_fn=AsyncMock())
    assert res_premature["success"] is False
    assert res_premature["terminate"] is False
    assert res_premature["recoverable"] is True
    assert res_premature["result"]["error"] == "premature_exit_blocked"

    # Recover by pressing Enter
    res_enter = await machine.handle("root--browser--press-key", {"key": "Enter", "ref": "e3"}, describe_root_fn=AsyncMock())
    assert "[LAST ACTION] NAVIGATED" in res_enter["result"]["state_change_text"]
    assert "Anker USB-C Hub" in res_enter["result"]["observation"]

    # Complete cleanly
    res_done = await machine.handle("root--browser--successful-termination", {"result_summary": "Found Anker USB-C Hub for $25.99"}, describe_root_fn=AsyncMock())
    assert res_done["success"] is True
    assert res_done["terminate"] is True
    assert res_done["rtsi_outcome"]["status"] == "success"
    assert res_done["rtsi_outcome"]["final_url"] == "https://www.amazon.com/s?k=usb+c+hub"


@pytest.mark.asyncio
async def test_trajectory_atomic_search_with_submit_happy_path():
    snap_home = {
        "text": '[PAGE] Shop | https://shop.example.com/\n[VIEWPORT] 0% AT TOP | ~0.0 above | ~2.0 below | can_scroll: down\n[e2] searchbox "Search" [searchbox, enter-submits]',
        "generation": 1,
        "page": {"url": "https://shop.example.com/", "title": "Shop"},
    }
    snap_res = {
        "text": '[PAGE] Results | https://shop.example.com/search?q=keyboard\n[VIEWPORT] 0% AT TOP | ~0.0 above | ~3.0 below | can_scroll: down\n[e5] heading(1) "Keychron K2"',
        "generation": 2,
        "page": {"url": "https://shop.example.com/search?q=keyboard", "title": "Results"},
    }
    bridge = _make_bridge([
        {"ok": True},
        {"tabs": []},
        {"tab_id": 7, "url": "https://shop.example.com/", "title": "Shop"},
        snap_home,
        {
            "state_change": {
                "effect": "navigated",
                "causal_outcome": "NAVIGATED",
                "navigated": True,
                "navigation_kind": "full",
                "before": {"url": "https://shop.example.com/", "title": "Shop"},
                "after": {"url": "https://shop.example.com/search?q=keyboard", "title": "Results", "generation": 2},
                "wait": {"settled": True, "reason": "quiet", "elapsed_ms": 220},
            }
        },
        snap_res,
        {"text": "Keychron K2 Mechanical Keyboard $89"},
        snap_res,
        {"ok": True},
    ])

    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    await machine.handle("root--browser", {}, describe_root_fn=AsyncMock())
    await machine.handle("root--browser--open-tab", {"url": "https://shop.example.com/"}, describe_root_fn=AsyncMock())
    res_type = await machine.handle("root--browser--type-text", {"ref": "e2", "text": "keyboard", "submit": True}, describe_root_fn=AsyncMock())
    assert res_type["replaces"] == "observation"
    assert "[LAST ACTION] NAVIGATED" in res_type["result"]["state_change_text"]

    res_read = await machine.handle("root--browser--read-text", {}, describe_root_fn=AsyncMock())
    assert "Keychron K2" in res_read["result"]["text"]

    res_done = await machine.handle("root--browser--successful-termination", {"result_summary": "Keychron K2 is $89"}, describe_root_fn=AsyncMock())
    assert res_done["success"] is True
    assert res_done["rtsi_outcome"]["steps"] == 1


@pytest.mark.asyncio
async def test_trajectory_modal_interruption_dismiss_and_retry():
    snap_modal = {
        "text": (
            "[PAGE] News | https://news.example.com/\n"
            "[VIEWPORT] 0% AT TOP | ~0.0 above | ~4.0 below | can_scroll: down\n"
            "[FOCUS] none\n"
            '[MODAL] [e40] dialog "Subscribe" open — dismiss with Escape or close button\n'
            '[e41] button "Close"\n'
            '[e5] link "Top Story"'
        ),
        "generation": 2,
        "page": {"url": "https://news.example.com/", "title": "News"},
        "observation_meta": {"url": "https://news.example.com/", "title": "News", "state_fingerprint": "fp_modal"},
    }
    snap_clear = {
        "text": '[PAGE] News | https://news.example.com/\n[VIEWPORT] 0% AT TOP | ~0.0 above | ~4.0 below | can_scroll: down\n[e5] link "Top Story"',
        "generation": 3,
        "page": {"url": "https://news.example.com/", "title": "News"},
        "observation_meta": {"url": "https://news.example.com/", "title": "News", "state_fingerprint": "fp_clear"},
    }
    snap_article = {
        "text": '[PAGE] Top Story | https://news.example.com/story\n[VIEWPORT] 0% AT TOP | ~0.0 above | ~2.0 below | can_scroll: down\n[e1] heading(1) "Breaking News"',
        "generation": 4,
        "page": {"url": "https://news.example.com/story", "title": "Top Story"},
    }
    bridge = _make_bridge([
        BridgeError("covered_by", "Element is covered by <dialog>", data={"covered_by": "dialog"}),
        snap_modal,
        {
            "state_change": {
                "effect": "dom_changed",
                "causal_outcome": "DOM_UPDATED",
                "dom": {"added": [], "removed": [{"ref": "e40", "desc": 'dialog "Subscribe"'}], "changed": []},
                "before": {"url": "https://news.example.com/", "title": "News"},
                "after": {"url": "https://news.example.com/", "title": "News", "generation": 3, "state_fingerprint": "fp_clear"},
                "wait": {"settled": True, "reason": "quiet", "elapsed_ms": 80},
            }
        },
        snap_clear,
        {
            "state_change": {
                "effect": "navigated",
                "causal_outcome": "NAVIGATED",
                "navigated": True,
                "navigation_kind": "full",
                "before": {"url": "https://news.example.com/", "title": "News"},
                "after": {"url": "https://news.example.com/story", "title": "Top Story", "generation": 4},
                "wait": {"settled": True, "reason": "quiet", "elapsed_ms": 200},
            }
        },
        snap_article,
        snap_article,
        {"ok": True},
    ])

    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    session = machine._sessions.begin()
    session.state = State.DECIDE
    session.tab_id = 1

    res_cov = await machine.handle("root--browser--click", {"ref": "e5"}, describe_root_fn=AsyncMock())
    assert res_cov["success"] is False and res_cov["recoverable"] is True and res_cov["terminate"] is False
    assert "[MODAL] [e40]" in res_cov["result"]["observation"]

    res_esc = await machine.handle("root--browser--press-key", {"key": "Escape"}, describe_root_fn=AsyncMock())
    assert "[LAST ACTION] DOM_UPDATED" in res_esc["result"]["state_change_text"]

    res_retry = await machine.handle("root--browser--click", {"ref": "e5"}, describe_root_fn=AsyncMock())
    assert "[LAST ACTION] NAVIGATED" in res_retry["result"]["state_change_text"]

    res_done = await machine.handle("root--browser--successful-termination", {"result_summary": "Opened top story"}, describe_root_fn=AsyncMock())
    assert res_done["success"] is True


@pytest.mark.asyncio
async def test_trajectory_offscreen_scroll_and_bottom_boundary():
    snap_bottom = {
        "text": (
            "[PAGE] Specs | https://example.com/specs\n"
            "[VIEWPORT] 100% AT BOTTOM | ~3.0 above | ~0.0 below | can_scroll: up\n"
            "[FOCUS] none\n"
            '[e30] button "Buy Warranty"'
        ),
        "generation": 2,
        "page": {"url": "https://example.com/specs", "title": "Specs"},
    }
    bridge = _make_bridge([
        {
            "results": [{"ref": "e30", "role": "button", "name": "Buy Warranty", "position": "below"}],
            "counts": {"total": 2, "in_viewport": 0, "above_viewport": 0, "below_viewport": 2},
        },
        {
            "state_change": {
                "effect": "none",
                "causal_outcome": "SCROLLED",
                "no_visible_change": False,
                "scroll": {"before": 0, "after": 1500, "max": 1500, "pct": 100, "at_bottom": True, "revealed_headings": ['[e29] "Warranty"']},
                "before": {"url": "https://example.com/specs", "title": "Specs", "scroll": 0},
                "after": {"url": "https://example.com/specs", "title": "Specs", "scroll": 1500, "generation": 2},
                "wait": {"settled": True, "reason": "quiet", "elapsed_ms": 40},
            }
        },
        snap_bottom,
    ])

    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings(judge_policy="adaptive"))
    session = machine._sessions.begin()
    session.state = State.DECIDE
    session.tab_id = 1

    res_find = await machine.handle("root--browser--find-in-page", {"query": "Warranty"}, describe_root_fn=AsyncMock())
    assert "2 below viewport" in res_find["result"]["summary"]

    res_scroll = await machine.handle("root--browser--scroll", {"direction": "down", "pages": 0.8}, describe_root_fn=AsyncMock())
    assert res_scroll["success"] is True
    assert "[LAST ACTION] SCROLLED — Viewport at 100% (AT BOTTOM)" in res_scroll["result"]["state_change_text"]
    assert "AT BOTTOM" in res_scroll["result"]["observation"]
    assert "can_scroll: up" in res_scroll["result"]["observation"]


@pytest.mark.asyncio
async def test_trajectory_stale_ref_and_mid_action_navigation_recovery():
    snap_fresh = {
        "text": '[PAGE] Cart | https://shop.example.com/cart\n[VIEWPORT] 0% AT TOP | ~0.0 above | ~1.0 below | can_scroll: down\n[e12] button "Proceed"',
        "generation": 5,
        "page": {"url": "https://shop.example.com/cart", "title": "Cart"},
    }
    snap_next = {
        "text": '[PAGE] Shipping | https://shop.example.com/shipping\n[VIEWPORT] 0% AT TOP | ~0.0 above | ~1.0 below | can_scroll: down\n[e1] heading(1) "Shipping Address"',
        "generation": 6,
        "page": {"url": "https://shop.example.com/shipping", "title": "Shipping"},
    }
    bridge = _make_bridge([
        BridgeError("stale_ref", "Ref e4 is stale", data={"hint": "use fresh ref"}),
        snap_fresh,
        {
            "state_change": {
                "effect": "navigated",
                "causal_outcome": "NAVIGATED",
                "navigated": True,
                "navigation_kind": "full",
                "before": {"url": "https://shop.example.com/cart", "title": "Cart"},
                "after": {"url": "https://shop.example.com/shipping", "title": "Shipping", "generation": 6},
                "wait": {"settled": True, "reason": "navigation_complete", "elapsed_ms": 280},
            }
        },
        snap_next,
    ])

    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings(judge_policy="adaptive"))
    session = machine._sessions.begin()
    session.state = State.DECIDE
    session.tab_id = 1

    res_stale = await machine.handle("root--browser--click", {"ref": "e4"}, describe_root_fn=AsyncMock())
    assert res_stale["success"] is False
    assert res_stale["terminate"] is False
    assert res_stale["recoverable"] is True
    assert res_stale["replaces"] == "observation"
    assert session.observation_generation == 5

    res_ok = await machine.handle("root--browser--click", {"ref": "e12"}, describe_root_fn=AsyncMock())
    assert res_ok["success"] is True
    assert "[LAST ACTION] NAVIGATED" in res_ok["result"]["state_change_text"]
    assert session.observation_generation == 6
    assert "Shipping Address" in res_ok["result"]["observation"]
