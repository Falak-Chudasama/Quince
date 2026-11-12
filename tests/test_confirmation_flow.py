"""
Tests for confirmation flow and deterministic yes/no parsing:
- parse_yes_no (yes, no, ambiguous, empty, safe defaults)
- build_confirmation_question (length <= 160, sanitization)
- RtsiMachine confirmation execution (no -> never re-sends, yes -> re-sends once with token, ambiguous twice -> no, expired -> no)
"""
import pytest
import time
from unittest.mock import AsyncMock, MagicMock
from quince_mcp.rtsi.confirm import build_confirmation_question, parse_yes_no, AMBIGUOUS_RETRY_QUESTION
from quince_mcp.rtsi.machine import RtsiMachine
from quince_mcp.rtsi.session import PendingUser, RtsiSession
from quince_mcp.rtsi.states import State
from quince_mcp.bridge.config import BridgeSettings


def test_parse_yes_no():
    assert parse_yes_no("yes") == "yes"
    assert parse_yes_no("yeah") == "yes"
    assert parse_yes_no("sure") == "yes"
    assert parse_yes_no("go ahead") == "yes"
    assert parse_yes_no("please do") == "yes"

    assert parse_yes_no("no") == "no"
    assert parse_yes_no("nope") == "no"
    assert parse_yes_no("cancel") == "no"
    assert parse_yes_no("don't") == "no"
    assert parse_yes_no("stop") == "no"

    assert parse_yes_no("") == "no"
    assert parse_yes_no("   ") == "no"
    assert parse_yes_no("random gibberish") == "no"  # safe default

    # Ambiguous when both present
    assert parse_yes_no("yes, wait no stop") == "ambiguous"
    assert parse_yes_no("sure but dont") == "ambiguous"


def test_build_confirmation_question():
    q = build_confirmation_question("Send Email", "mail.google.com", "root--browser--click")
    assert "mail.google.com" in q
    assert len(q) <= 160
    assert "\x00" not in q

    # Control chars removed and length capped
    q_long = build_confirmation_question("A" * 200 + "\x01\x02", "example.com", "root--browser--click")
    assert len(q_long) <= 160


@pytest.mark.asyncio
async def test_confirmation_flow_no_declines():
    bridge = MagicMock()
    bridge.call = AsyncMock()
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings())

    # Create active session in AWAITING_USER
    session = machine._sessions.begin()
    session.state = State.AWAITING_USER
    session.pending = PendingUser(
        kind="confirmation",
        tool_id="root--browser--click",
        arguments={"ref": "e14"},
        token="token_123",
        question="Should I send?",
        attempts=0,
        expires_at=time.time() + 60,
    )

    res = await machine.handle(
        "root--browser--provide-answer",
        {"answer": "no"},
        describe_root_fn=AsyncMock(),
    )

    assert res["success"] is True
    assert res["result"]["user_declined"] is True
    assert session.state == State.DECIDE
    assert session.exits_open is True
    # Bridge should NEVER have been called to execute the action
    bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_confirmation_flow_yes_resends():
    bridge = MagicMock()
    bridge.call = AsyncMock(return_value={
        "state_change": {
            "effect": "dom_changed",
            "wait": {"settled": True, "reason": "quiet", "elapsed_ms": 100},
            "summary_line": "Message sent",
        }
    })
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings())

    session = machine._sessions.begin()
    session.state = State.AWAITING_USER
    session.pending = PendingUser(
        kind="confirmation",
        tool_id="root--browser--click",
        arguments={"ref": "e14"},
        token="token_123",
        question="Should I send?",
        attempts=0,
        expires_at=time.time() + 60,
    )

    res = await machine.handle(
        "root--browser--provide-answer",
        {"answer": "yes"},
        describe_root_fn=AsyncMock(),
    )

    assert res["success"] is True
    # Should transition to COMPARE (or JUDGE if merged)
    assert session.state in (State.COMPARE, State.JUDGE)
    # Bridge.call should be called with act.click and confirm_token
    bridge.call.assert_called_once()
    call_args = bridge.call.call_args[0]
    assert call_args[0] == "act.click"
    assert call_args[1]["confirm_token"] == "token_123"


@pytest.mark.asyncio
async def test_confirmation_flow_ambiguous_retry_then_no():
    bridge = MagicMock()
    bridge.call = AsyncMock()
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings())

    session = machine._sessions.begin()
    session.state = State.AWAITING_USER
    session.pending = PendingUser(
        kind="confirmation",
        tool_id="root--browser--click",
        arguments={"ref": "e14"},
        token="token_123",
        question="Should I send?",
        attempts=0,
        expires_at=time.time() + 60,
    )

    # First ambiguous answer
    res1 = await machine.handle(
        "root--browser--provide-answer",
        {"answer": "yes wait no"},
        describe_root_fn=AsyncMock(),
    )
    assert session.state == State.AWAITING_USER
    assert session.pending.attempts == 1
    assert res1["result"]["question"] == AMBIGUOUS_RETRY_QUESTION

    # Second ambiguous answer -> treated as no
    res2 = await machine.handle(
        "root--browser--provide-answer",
        {"answer": "yes or no"},
        describe_root_fn=AsyncMock(),
    )
    assert session.state == State.DECIDE
    assert res2["result"]["user_declined"] is True
    bridge.call.assert_not_called()


@pytest.mark.asyncio
async def test_confirmation_flow_expired():
    bridge = MagicMock()
    bridge.call = AsyncMock()
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings())

    session = machine._sessions.begin()
    session.state = State.AWAITING_USER
    session.pending = PendingUser(
        kind="confirmation",
        tool_id="root--browser--click",
        arguments={"ref": "e14"},
        token="token_123",
        question="Should I send?",
        attempts=0,
        expires_at=time.time() - 10,  # Expired
    )

    res = await machine.handle(
        "root--browser--provide-answer",
        {"answer": "yes"},
        describe_root_fn=AsyncMock(),
    )
    assert res["result"]["user_declined"] is True
    assert session.state == State.DECIDE
    bridge.call.assert_not_called()
