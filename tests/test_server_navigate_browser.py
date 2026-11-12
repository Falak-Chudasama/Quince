"""
Integration tests for server.py navigate_impl with RTSI:
- baseline tool tree contains browser and its tools
- navigate_impl('root--browser') when disconnected -> extension_not_connected
- navigate_impl('root--browser') when connected -> enters session
- navigate_impl('reset') and navigate_impl('terminate') clean up any active session
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from quince_mcp.server import navigate_impl
from quince_mcp.tool_tree import TOOL_TREE, root
from quince_mcp.rtsi.states import State
import quince_mcp.rtsi.machine as machine_mod


def test_tool_tree_includes_browser():
    assert "root--browser" in [c.tool_id for c in root.children]
    assert "root--browser" in TOOL_TREE
    assert "root--browser--click" in TOOL_TREE
    assert "root--browser--type-text" in TOOL_TREE
    assert "root--browser--open-tab" in TOOL_TREE
    assert "root--browser--list-tabs" in TOOL_TREE
    assert "root--browser--continue" in TOOL_TREE
    assert "root--browser--successful-termination" in TOOL_TREE


@pytest.mark.asyncio
async def test_navigate_impl_browser_disconnected():
    # Ensure bridge is not connected
    mock_bridge = MagicMock()
    mock_bridge.is_connected = False
    
    with patch.object(machine_mod, "_machine", None):
        machine = machine_mod.get_rtsi_machine()
        machine._bridge = mock_bridge
        res = await navigate_impl("root--browser")
        assert res["success"] is False
        assert res["error"] == "extension_not_connected"
        assert res["terminate"] is True


@pytest.mark.asyncio
async def test_navigate_impl_browser_connected():
    mock_bridge = MagicMock()
    mock_bridge.is_connected = True
    mock_bridge.connected_info = {"version": "1.0.0"}
    mock_bridge.call = AsyncMock(return_value={
        "tabs": [{"tab_id": 1, "url": "https://example.com", "title": "Example"}],
    })
    
    with patch.object(machine_mod, "_machine", None):
        machine = machine_mod.get_rtsi_machine()
        machine._bridge = mock_bridge
        res = await navigate_impl("root--browser")
        assert res["success"] is True
        assert res["terminate"] is False
        assert "Browser control started." in res["message"]
        assert res["result"]["extension_version"] == "1.0.0"


@pytest.mark.asyncio
async def test_reset_and_terminate_abort_session():
    mock_bridge = MagicMock()
    mock_bridge.is_connected = True
    mock_bridge.connected_info = {"version": "1.0.0"}
    mock_bridge.call = AsyncMock(return_value={"tabs": []})

    with patch.object(machine_mod, "_machine", None):
        machine = machine_mod.get_rtsi_machine()
        machine._bridge = mock_bridge
        
        # Start session
        await navigate_impl("root--browser")
        session = machine._sessions.get_or_none()
        assert session is not None
        assert session.state == State.ENTRY

        # Call reset
        res_reset = await navigate_impl("reset")
        assert res_reset["message"] == "Category contents"
        assert session.state == State.ENDED
        assert session.outcome == "reset"
