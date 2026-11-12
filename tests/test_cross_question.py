"""
Tests for cross-question flow:
- cross-question triggers AWAITING_USER state with pending.kind == "question"
- provide-answer transitions back to DECIDE with user_answer in result
- user_answer is NEVER stored in session.history or printed in log output
"""
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock
from quince_mcp.rtsi.machine import RtsiMachine
from quince_mcp.rtsi.states import State
from quince_mcp.bridge.config import BridgeSettings


@pytest.mark.asyncio
async def test_cross_question_flow_and_privacy(caplog):
    caplog.set_level(logging.DEBUG)

    bridge = MagicMock()
    bridge.call = AsyncMock(return_value={
        "snapshot": "[e1] heading \"Dashboard\"",
        "page": {"url": "https://example.com/dash", "title": "Dashboard"},
    })
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings())

    # Begin session and enter JUDGE state (where cross-question is always valid)
    session = machine._sessions.begin()
    session.state = State.JUDGE

    # 1. Ask cross question
    res_q = await machine.handle(
        "root--browser--cross-question",
        {"question": "What is your username?"},
        describe_root_fn=AsyncMock(),
    )
    assert res_q["success"] is True
    assert session.state == State.AWAITING_USER
    assert session.pending is not None
    assert session.pending.kind == "question"

    # 2. User provides sensitive answer
    secret_answer = "SECRET_USER_12345"
    res_ans = await machine.handle(
        "root--browser--provide-answer",
        {"answer": secret_answer},
        describe_root_fn=AsyncMock(),
    )
    assert res_ans["success"] is True
    assert session.state == State.DECIDE
    assert res_ans["result"]["user_answer"] == secret_answer

    # 3. Verify privacy: secret answer is NOT in history
    for item in session.history:
        assert secret_answer not in (item.action or "")
        assert secret_answer not in (item.summary_line or "")
        assert secret_answer not in (item.comparison or "")

    # 4. Verify privacy: secret answer is NOT anywhere in log records
    for record in caplog.records:
        assert secret_answer not in record.getMessage()


@pytest.mark.asyncio
async def test_cross_question_from_decide_with_exits_open():
    bridge = MagicMock()
    bridge.call = AsyncMock(return_value={
        "snapshot": "[e1] heading \"Dashboard\"",
        "page": {"url": "https://example.com/dash", "title": "Dashboard"},
    })
    machine = RtsiMachine(bridge=bridge, settings=BridgeSettings())

    session = machine._sessions.begin()
    session.state = State.DECIDE
    session.exits_open = True

    res = await machine.handle(
        "root--browser--cross-question",
        {"question": "Which tab should I look at?"},
        describe_root_fn=AsyncMock(),
    )
    assert res["success"] is True
    assert session.state == State.AWAITING_USER
