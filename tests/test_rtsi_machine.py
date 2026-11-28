"""
Comprehensive tests for RtsiMachine:
- Full state transition table:
  ENTRY -> open-tab -> DECIDE -> click -> COMPARE -> record-comparison -> JUDGE -> continue -> DECIDE -> successful-termination -> ENDED
- READ tools (refresh-page, find-in-page, read-text) keep session in DECIDE
- Out-of-state calls and 3-strike termination
- Adaptive vs conservative judge policy
- Error handling (stale_ref delivers fresh observation, 5 failures triggers failure_limit)
- Repeat guard (3 times warning, 5 times repeat_limit)
- Step cap (max_steps trigger)
- Duration/idle expiration
- Session superseding
- Reset / abort mid-session
- Termination ends loop vs root menu return
"""
import pytest
import time
from unittest.mock import AsyncMock, MagicMock
from quince_mcp.bridge.config import BridgeSettings
from quince_mcp.bridge.protocol import BridgeError
from quince_mcp.rtsi.machine import RtsiMachine
from quince_mcp.rtsi.states import State


def create_fake_bridge():
    bridge = MagicMock()
    bridge.is_connected = True
    bridge.connected_info = {"version": "1.0.0"}
    bridge.call = AsyncMock(return_value={
        "tabs": [{"tab_id": 1, "url": "https://example.com", "title": "Example"}],
        "tab_id": 1,
        "text": "[e1] heading \"Example Page\"\n[e2] button \"Submit\"",
        "snapshot": "[e1] heading \"Example Page\"\n[e2] button \"Submit\"",
        "page": {"url": "https://example.com", "title": "Example Page"},
        "state_change": {
            "effect": "dom_changed",
            "summary_line": "Page updated",
            "wait": {"settled": True, "reason": "quiet", "elapsed_ms": 100},
            "dom": {"added": [], "removed": [], "changed": []},
            "after": {"url": "https://example.com/step2", "title": "Step 2"},
        },
    })
    return bridge


@pytest.mark.asyncio
async def test_full_rtsi_happy_path_cycle():
    bridge = create_fake_bridge()
    settings = BridgeSettings(judge_policy="conservative", termination_ends_loop=True)
    machine = RtsiMachine(bridge=bridge, settings=settings)

    # 1. ENTRY: navigate("root--browser")
    res_entry = await machine.handle("root--browser", {}, describe_root_fn=AsyncMock())
    assert res_entry["success"] is True
    session = machine._sessions.get_or_none()
    assert session is not None
    assert session.state == State.ENTRY

    # 2. ENTRY -> Open Tab -> Transitions to DECIDE
    res_tab = await machine.handle(
        "root--browser--open-tab",
        {"url": "https://example.com"},
        describe_root_fn=AsyncMock(),
    )
    assert res_tab["success"] is True
    assert session.state == State.DECIDE
    assert session.tab_id == 1

    # 3. DECIDE -> ACT (click) -> Transitions to COMPARE
    res_click = await machine.handle(
        "root--browser--click",
        {"ref": "e2"},
        describe_root_fn=AsyncMock(),
    )
    assert res_click["success"] is True
    assert session.state == State.COMPARE
    assert "state_change_text" in res_click["result"]

    # 4. COMPARE -> Record comparison -> Transitions to JUDGE
    res_comp = await machine.handle(
        "root--browser--record-comparison",
        {"comparison": "Clicked submit, URL changed to /step2"},
        describe_root_fn=AsyncMock(),
    )
    assert res_comp["success"] is True
    assert session.state == State.JUDGE
    assert len(session.history) == 1

    # 5. JUDGE -> continue -> Transitions to DECIDE with fresh observation
    res_cont = await machine.handle(
        "root--browser--continue",
        {},
        describe_root_fn=AsyncMock(),
    )
    assert res_cont["success"] is True
    assert session.state == State.DECIDE
    assert "observation" in res_cont["result"]

    # 6. DECIDE -> Another ACT (click) -> COMPARE -> JUDGE
    await machine.handle("root--browser--click", {"ref": "e2"}, describe_root_fn=AsyncMock())
    await machine.handle("root--browser--record-comparison", {"comparison": "Clicked again"}, describe_root_fn=AsyncMock())
    assert session.state == State.JUDGE

    # 7. JUDGE -> successful-termination -> Session ends
    res_term = await machine.handle(
        "root--browser--successful-termination",
        {"result_summary": "Task completed successfully"},
        describe_root_fn=AsyncMock(),
    )
    assert res_term["success"] is True
    assert res_term["terminate"] is True
    assert session.state == State.ENDED
    assert session.outcome == "success"


@pytest.mark.asyncio
async def test_read_tools_stay_in_decide():
    bridge = create_fake_bridge()
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings())

    session = machine._sessions.begin()
    session.state = State.DECIDE
    session.tab_id = 1

    # find-in-page
    res_find = await machine.handle(
        "root--browser--find-in-page",
        {"query": "Submit"},
        describe_root_fn=AsyncMock(),
    )
    assert res_find["success"] is True
    assert session.state == State.DECIDE

    # read-text
    res_read = await machine.handle(
        "root--browser--read-text",
        {"max_chars": 2000},
        describe_root_fn=AsyncMock(),
    )
    assert res_read["success"] is True
    assert session.state == State.DECIDE

    # refresh-page
    res_refresh = await machine.handle(
        "root--browser--refresh-page",
        {},
        describe_root_fn=AsyncMock(),
    )
    assert res_refresh["success"] is True
    assert session.state == State.DECIDE
    assert "observation" in res_refresh["result"]


@pytest.mark.asyncio
async def test_out_of_state_and_three_strike_rule():
    bridge = create_fake_bridge()
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings())

    session = machine._sessions.begin()
    session.state = State.COMPARE

    # Strike 1: calling click while in COMPARE
    res1 = await machine.handle("root--browser--click", {"ref": "e1"}, describe_root_fn=AsyncMock())
    assert session.bad_call_counter == 1
    assert res1["result"]["error"] == "not_allowed_in_state"
    assert session.state == State.COMPARE

    # Strike 2
    res2 = await machine.handle("root--browser--type-text", {"ref": "e1", "text": "a"}, describe_root_fn=AsyncMock())
    assert session.bad_call_counter == 2
    assert session.state == State.COMPARE

    # Strike 3: ends session
    res3 = await machine.handle("root--browser--click", {"ref": "e1"}, describe_root_fn=AsyncMock())
    assert session.state == State.ENDED
    assert res3["result"]["rtsi_outcome"]["status"] == "failed"


@pytest.mark.asyncio
async def test_adaptive_policy_clean_act():
    bridge = create_fake_bridge()
    # clean act: effect = dom_changed, no errors, no new tabs
    bridge.call = AsyncMock(return_value={
        "tab_id": 1,
        "text": "[e1] heading \"New Page\"",
        "state_change": {
            "effect": "dom_changed",
            "summary_line": "Clean update",
            "wait": {"settled": True, "reason": "quiet", "elapsed_ms": 100},
            "no_visible_change": False,
        },
    })
    settings = BridgeSettings(judge_policy="adaptive")
    machine = RtsiMachine(bridge=bridge, settings=settings)

    session = machine._sessions.begin()
    session.state = State.DECIDE
    session.tab_id = 1

    # With adaptive policy on a clean act, skips COMPARE/JUDGE directly to DECIDE
    res = await machine.handle("root--browser--click", {"ref": "e1"}, describe_root_fn=AsyncMock())
    assert res["success"] is True
    assert session.state == State.DECIDE
    assert "observation" in res["result"]


@pytest.mark.asyncio
async def test_stale_ref_error_recovers_observation():
    bridge = create_fake_bridge()
    bridge.call = AsyncMock(side_effect=[
        BridgeError("stale_ref", "Element ref e10 is no longer valid", data={"hint": "re-read page"}),
        {"text": "[e20] button \"New Submit\"", "tab_id": 1},
    ])
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings())

    session = machine._sessions.begin()
    session.state = State.DECIDE
    session.tab_id = 1

    res = await machine.handle("root--browser--click", {"ref": "e10"}, describe_root_fn=AsyncMock())
    assert res["result"]["error"] == "stale_ref"
    assert "observation" in res["result"]
    assert session.state == State.DECIDE
    assert session.exits_open is True


@pytest.mark.asyncio
async def test_consecutive_failure_limit():
    bridge = create_fake_bridge()
    bridge.call = AsyncMock(side_effect=BridgeError("general_error", "Something went wrong"))
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings())

    session = machine._sessions.begin()
    session.state = State.DECIDE
    session.tab_id = 1

    for _ in range(4):
        res = await machine.handle("root--browser--click", {"ref": "e1"}, describe_root_fn=AsyncMock())
        assert session.state == State.DECIDE
        assert session.failure_streak < 5

    # 5th failure ends session
    res5 = await machine.handle("root--browser--click", {"ref": "e1"}, describe_root_fn=AsyncMock())
    assert session.state == State.ENDED
    assert res5["result"]["rtsi_outcome"]["status"] == "failed"


@pytest.mark.asyncio
async def test_repeat_guard_warning_and_termination():
    bridge = create_fake_bridge()
    # Action results in NO_EFFECT
    bridge.call = AsyncMock(return_value={
        "tab_id": 1,
        "state_change": {
            "effect": "none",
            "causal_outcome": "NO_EFFECT",
            "no_visible_change": True,
            "after": {"url": "https://example.com/page"},
        },
    })
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings(judge_policy="conservative"))

    session = machine._sessions.begin()
    session.state = State.DECIDE
    session.tab_id = 1

    # Action 1 executes and records NO_EFFECT -> enters COMPARE -> JUDGE -> DECIDE
    res1 = await machine.handle("root--browser--click", {"ref": "e1"}, describe_root_fn=AsyncMock())
    assert session.state == State.COMPARE
    assert "[LAST ACTION] NO_EFFECT" in res1["result"]["state_change_text"]
    await machine.handle("root--browser--record-comparison", {"comparison": "none"}, describe_root_fn=AsyncMock())
    await machine.handle("root--browser--continue", {}, describe_root_fn=AsyncMock())

    # Attempts 2-4: identical dead (click, e1) against unchanged state fingerprint is blocked by RTSI
    for _ in range(3):
        res_blk = await machine.handle("root--browser--click", {"ref": "e1"}, describe_root_fn=AsyncMock())
        assert res_blk["success"] is False
        assert res_blk["terminate"] is False
        assert res_blk["result"]["recoverable"] is True
        assert res_blk["result"]["error"] == "repeated_dead_action"
        assert session.state == State.DECIDE

    # Attempt 5: triggers repeat limit termination
    res5 = await machine.handle("root--browser--click", {"ref": "e1"}, describe_root_fn=AsyncMock())
    assert session.state == State.ENDED
    assert res5["result"]["rtsi_outcome"]["status"] == "failed"


@pytest.mark.asyncio
async def test_step_cap():
    bridge = create_fake_bridge()
    settings = BridgeSettings(max_steps=3)
    machine = RtsiMachine(bridge=bridge, settings=settings)

    session = machine._sessions.begin()
    session.state = State.DECIDE
    session.tab_id = 1
    session.step = 3  # Hit max steps

    res = await machine.handle("root--browser--click", {"ref": "e1"}, describe_root_fn=AsyncMock())
    assert session.state == State.ENDED
    assert "hit my step limit" in res["message"]


@pytest.mark.asyncio
async def test_session_expiry():
    bridge = create_fake_bridge()
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings(max_duration_s=60, idle_timeout_s=30))

    session = machine._sessions.begin()
    session.started_at = time.time() - 100  # Expired duration

    res = await machine.handle("root--browser--refresh-page", {}, describe_root_fn=AsyncMock())
    assert res["error"] == "session_expired"
    assert session.state == State.ENDED


@pytest.mark.asyncio
async def test_session_superseding():
    bridge = create_fake_bridge()
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings())

    # Session 1
    await machine.handle("root--browser", {}, describe_root_fn=AsyncMock())
    s1 = machine._sessions.get_or_none()
    assert s1 is not None

    # Re-entering root--browser supersedes Session 1
    await machine.handle("root--browser", {}, describe_root_fn=AsyncMock())
    s2 = machine._sessions.get_or_none()
    assert s2 is not None
    assert s2.id != s1.id
    assert s1.state == State.ENDED
    assert s1.outcome == "superseded"


@pytest.mark.asyncio
async def test_abort_active_session():
    bridge = create_fake_bridge()
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings())

    session = machine._sessions.begin()
    session.state = State.DECIDE

    await machine.abort_active_session(outcome="reset")
    assert session.state == State.ENDED
    assert session.outcome == "reset"


@pytest.mark.asyncio
async def test_search_without_submit_value_changed_and_blocks_premature_exit_once():
    bridge = MagicMock()
    bridge.is_connected = True
    bridge.connected_info = {"version": "1.0.0"}

    snap_unsubmitted = {
        "text": (
            "[PAGE] Amazon | https://www.amazon.com/\n"
            "[VIEWPORT] 0% AT TOP | ~0.0 above | ~4.0 below | can_scroll: down\n"
            '[FOCUS] [e3] searchbox value="headphones" (UNSUBMITTED — press Enter or click submit button)\n'
            '[e3] searchbox "Search Amazon" value="headphones" [focused] [searchbox, enter-submits]'
        ),
        "generation": 2,
        "page": {"url": "https://www.amazon.com/", "title": "Amazon"},
        "observation_meta": {
            "url": "https://www.amazon.com/",
            "title": "Amazon",
            "state_fingerprint": "fp_amazon_typed",
        },
    }
    type_resp = {
        "state_change": {
            "effect": "value_set",
            "causal_outcome": "VALUE_CHANGED",
            "target": {"ref": "e3", "role": "searchbox"},
            "focus": {"before": "e3", "after": "e3", "after_role": "searchbox", "after_value": "headphones"},
            "dom": {
                "added": [],
                "removed": [],
                "changed": [{"ref": "e3", "desc": 'searchbox "Search Amazon"', "fields": {"value": ["", "headphones"]}}],
            },
            "before": {"url": "https://www.amazon.com/", "title": "Amazon"},
            "after": {"url": "https://www.amazon.com/", "title": "Amazon", "generation": 2},
            "state_fingerprint": "fp_amazon_typed",
            "wait": {"settled": True, "reason": "quiet", "elapsed_ms": 120},
        }
    }
    enter_resp = {
        "state_change": {
            "effect": "navigated",
            "causal_outcome": "NAVIGATED",
            "navigated": True,
            "navigation_kind": "full",
            "before": {"url": "https://www.amazon.com/", "title": "Amazon"},
            "after": {"url": "https://www.amazon.com/s?k=headphones", "title": "Amazon: headphones", "generation": 3},
            "state_fingerprint": "fp_amazon_results",
            "wait": {"settled": True, "reason": "quiet", "elapsed_ms": 300},
        }
    }
    snap_results = {
        "text": "[PAGE] Amazon: headphones | https://www.amazon.com/s?k=headphones\n[e10] heading(1) \"Results\"",
        "generation": 3,
        "page": {"url": "https://www.amazon.com/s?k=headphones", "title": "Amazon: headphones"},
        "observation_meta": {"url": "https://www.amazon.com/s?k=headphones", "title": "Amazon: headphones", "state_fingerprint": "fp_amazon_results"},
    }

    bridge.call = AsyncMock(side_effect=[
        type_resp,         # act.type
        snap_unsubmitted,  # adaptive observation
        snap_unsubmitted,  # premature termination corrective observation
        enter_resp,        # act.press_key Enter
        snap_results,      # adaptive observation after Enter
        snap_results,      # final snapshot in _do_termination
    ])

    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    session = machine._sessions.begin()
    session.state = State.DECIDE
    session.tab_id = 1
    session.goal = "Search Amazon for headphones"
    session.ref_desc = {"e3": 'searchbox "Search Amazon"'}

    # 1. Type without submit
    res_type = await machine.handle("root--browser--type-text", {"ref": "e3", "text": "headphones", "submit": False}, describe_root_fn=AsyncMock())
    assert "[LAST ACTION] VALUE_CHANGED — Input value updated; page did NOT navigate and form is not yet submitted." in res_type["result"]["state_change_text"]
    assert "UNSUBMITTED" in res_type["result"]["observation"]
    assert session.unsubmitted_search is True

    # 2. Premature exit is blocked once
    res_premature = await machine.handle(
        "root--browser--successful-termination",
        {"result_summary": "Typed headphones into Amazon search"},
        describe_root_fn=AsyncMock(),
    )
    assert res_premature["success"] is False
    assert res_premature["terminate"] is False
    assert res_premature["recoverable"] is True
    assert res_premature["result"]["error"] == "premature_exit_blocked"
    assert "Call key('Enter') or click the submit button" in res_premature["message"]
    assert session.state == State.DECIDE
    assert session.premature_exit_rejected is True

    # 3. Submit via Enter -> NAVIGATED clears unsubmitted_search
    res_enter = await machine.handle("root--browser--press-key", {"key": "Enter", "ref": "e3"}, describe_root_fn=AsyncMock())
    assert "[LAST ACTION] NAVIGATED" in res_enter["result"]["state_change_text"]
    assert session.unsubmitted_search is False

    # 4. Now successful-termination proceeds
    res_done = await machine.handle(
        "root--browser--successful-termination",
        {"result_summary": "Searched Amazon for headphones"},
        describe_root_fn=AsyncMock(),
    )
    assert res_done["success"] is True
    assert res_done["terminate"] is True
    assert session.state == State.ENDED


@pytest.mark.asyncio
async def test_type_with_submit_true_produces_navigated_and_clears_unsubmitted():
    bridge = MagicMock()
    bridge.is_connected = True
    bridge.call = AsyncMock(side_effect=[
        {
            "state_change": {
                "effect": "navigated",
                "causal_outcome": "NAVIGATED",
                "navigated": True,
                "navigation_kind": "full",
                "before": {"url": "https://www.amazon.com/", "title": "Amazon"},
                "after": {"url": "https://www.amazon.com/s?k=usb+hub", "title": "Amazon: usb hub"},
                "wait": {"settled": True, "reason": "quiet", "elapsed_ms": 350},
            }
        },
        {
            "text": '[PAGE] Amazon: usb hub | https://www.amazon.com/s?k=usb+hub\n[e1] heading(1) "Results"',
            "generation": 4,
            "page": {"url": "https://www.amazon.com/s?k=usb+hub", "title": "Amazon: usb hub"},
        },
    ])
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings(judge_policy="adaptive"))
    session = machine._sessions.begin()
    session.state = State.DECIDE
    session.tab_id = 1
    session.ref_desc = {"e3": 'searchbox "Search Amazon"'}

    res = await machine.handle(
        "root--browser--type-text",
        {"ref": "e3", "text": "usb hub", "submit": True},
        describe_root_fn=AsyncMock(),
    )
    assert res["success"] is True
    assert session.unsubmitted_search is False
    assert "[LAST ACTION] NAVIGATED" in res["result"]["state_change_text"]
    act_call = bridge.call.call_args_list[0][0]
    assert act_call[0] == "act.type"
    assert act_call[1]["submit"] is True
    assert act_call[1]["press_enter"] is True
    assert act_call[1]["clear"] is True


@pytest.mark.asyncio
async def test_two_consecutive_no_effect_triggers_stall_breaker_and_recovery_hint():
    bridge = MagicMock()
    bridge.is_connected = True
    no_effect_sc = {
        "state_change": {
            "effect": "none",
            "causal_outcome": "NO_EFFECT",
            "no_visible_change": True,
            "before": {"url": "https://example.com"},
            "after": {"url": "https://example.com", "state_fingerprint": "fp_static"},
            "state_fingerprint": "fp_static",
            "wait": {"settled": True, "reason": "quiet", "elapsed_ms": 100},
        }
    }
    snap_static = {
        "text": "[e1] button \"Hidden\"\n[e2] button \"Dead\"",
        "page": {"url": "https://example.com", "title": "Example"},
        "observation_meta": {"url": "https://example.com", "title": "Example", "state_fingerprint": "fp_static"},
    }
    bridge.call = AsyncMock(side_effect=[
        no_effect_sc,  # click e1 -> NO_EFFECT (1)
        no_effect_sc,  # click e2 -> NO_EFFECT (2) -> triggers stall breaker -> COMPARE
        snap_static,   # continue -> observation with [RECOVERY]
        snap_static,   # blocked click e2 -> observation with [RECOVERY]
    ])
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings(judge_policy="adaptive"))
    session = machine._sessions.begin()
    session.state = State.DECIDE
    session.tab_id = 1
    session.current_state_fingerprint = "fp_static"

    # 1st NO_EFFECT (click e1)
    await machine.handle("root--browser--click", {"ref": "e1"}, describe_root_fn=AsyncMock())
    assert session.consecutive_no_effect_count() == 1
    await machine.handle("root--browser--record-comparison", {"comparison": "nothing happened"}, describe_root_fn=AsyncMock())
    await machine.handle("root--browser--continue", {}, describe_root_fn=AsyncMock())

    # 2nd consecutive NO_EFFECT (click e2) -> triggers stall breaker & recovery hint
    res2 = await machine.handle("root--browser--click", {"ref": "e2"}, describe_root_fn=AsyncMock())
    assert session.consecutive_no_effect_count() == 2
    assert "RECOVERY:" in res2["result"]["state_change_text"]
    assert "2 consecutive actions had NO_EFFECT" in session.recovery_directive

    await machine.handle("root--browser--record-comparison", {"comparison": "still nothing"}, describe_root_fn=AsyncMock())
    res_cont = await machine.handle("root--browser--continue", {}, describe_root_fn=AsyncMock())
    assert "[RECOVERY]" in res_cont["result"]["observation"]

    # Repeating dead (click, e2) against unchanged fp_static is blocked in RTSI state validation
    res_blocked = await machine.handle("root--browser--click", {"ref": "e2"}, describe_root_fn=AsyncMock())
    assert res_blocked["success"] is False
    assert res_blocked["terminate"] is False
    assert res_blocked["recoverable"] is True
    assert res_blocked["result"]["error"] == "repeated_dead_action"


@pytest.mark.asyncio
async def test_recoverable_errors_do_not_terminate():
    bridge = MagicMock()
    bridge.is_connected = True
    bridge.call = AsyncMock(side_effect=[
        BridgeError("covered_by", "Element is covered by <div>", data={"covered_by": "div"}),
        {"text": "[e1] dialog \"Popup\"", "page": {"url": "https://example.com", "title": "Example"}},
    ])
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings())
    session = machine._sessions.begin()
    session.state = State.DECIDE
    session.tab_id = 1

    res = await machine.handle("root--browser--click", {"ref": "e5"}, describe_root_fn=AsyncMock())
    assert res["success"] is False
    assert res["terminate"] is False
    assert res["recoverable"] is True
    assert res["result"]["recoverable"] is True
    assert res["result"]["error"] == "covered_by"
    assert "observation" in res["result"]

    # Out-of-state error is also recoverable and non-terminating (until 3-strike)
    session.state = State.COMPARE
    res_oos = await machine.handle("root--browser--click", {"ref": "e5"}, describe_root_fn=AsyncMock())
    assert res_oos["success"] is False
    assert res_oos["terminate"] is False
    assert res_oos["recoverable"] is True
    assert res_oos["result"]["error"] == "not_allowed_in_state"
