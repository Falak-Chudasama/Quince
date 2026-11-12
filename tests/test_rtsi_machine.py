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
    # Action results in no_visible_change
    bridge.call = AsyncMock(return_value={
        "tab_id": 1,
        "state_change": {
            "effect": "none",
            "no_visible_change": True,
            "after": {"url": "https://example.com/page"},
        },
    })
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings(judge_policy="conservative"))

    session = machine._sessions.begin()
    session.state = State.DECIDE
    session.tab_id = 1

    # Actions 1 & 2
    for _ in range(2):
        await machine.handle("root--browser--click", {"ref": "e1"}, describe_root_fn=AsyncMock())
        await machine.handle("root--browser--record-comparison", {"comparison": "none"}, describe_root_fn=AsyncMock())
        await machine.handle("root--browser--continue", {}, describe_root_fn=AsyncMock())

    # Action 3: injects loop_warning
    res3 = await machine.handle("root--browser--click", {"ref": "e1"}, describe_root_fn=AsyncMock())
    assert "NOTE: You repeated the same action and nothing changed" in res3["result"]["state_change_text"]

    await machine.handle("root--browser--record-comparison", {"comparison": "none"}, describe_root_fn=AsyncMock())
    await machine.handle("root--browser--continue", {}, describe_root_fn=AsyncMock())

    # Action 4
    await machine.handle("root--browser--click", {"ref": "e1"}, describe_root_fn=AsyncMock())
    await machine.handle("root--browser--record-comparison", {"comparison": "none"}, describe_root_fn=AsyncMock())
    await machine.handle("root--browser--continue", {}, describe_root_fn=AsyncMock())

    # Action 5: triggers repeat limit termination
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
