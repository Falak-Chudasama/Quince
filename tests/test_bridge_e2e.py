"""
End-to-end test with a real WebSocket connection to ExtensionBridge:
- ExtensionBridge starts on 127.0.0.1
- Real WebSocket client connects and performs 'hello' handshake with token
- Bridge verifies token, returns 'hello_ack', and transitions to 'connected'
- MCP navigate_impl('root--browser') sends 'session.begin' and 'tabs.list' over real socket
- Extension replies over socket
- navigate_impl returns successful ENTRY envelope
"""
import asyncio
import json
import pytest
import websockets
from quince_mcp.bridge.server import ExtensionBridge
from quince_mcp.bridge.config import BridgeSettings
from quince_mcp.rtsi.machine import RtsiMachine
import quince_mcp.rtsi.machine as machine_mod
from quince_mcp.server import navigate_impl


@pytest.mark.asyncio
async def test_real_bridge_websocket_handshake():
    # Use ephemeral/custom port for test
    port = 7199
    token = "test_secret_token_123"
    settings = BridgeSettings(port=port, token=token)
    
    bridge = ExtensionBridge()
    bridge.start(settings)
    await asyncio.sleep(0.3)

    assert bridge.state in ("listening", "starting")

    uri = f"ws://127.0.0.1:{port}/"

    async with websockets.connect(uri, additional_headers={"Origin": "chrome-extension://test"}) as ws:
        # 1. Send hello frame
        await ws.send(json.dumps({
            "type": "hello",
            "v": 1,
            "version": "0.1.0",
            "token": token,
            "capabilities": ["snapshot", "actions"]
        }))

        # 2. Receive hello_ack
        raw_ack = await asyncio.wait_for(ws.recv(), timeout=2.0)
        ack = json.loads(raw_ack)
        assert ack["type"] == "hello_ack"
        assert ack.get("protocol", ack.get("protocol_version")) == 1
        assert bridge.is_connected is True

        # 3. Test request-response cycle from bridge to extension
        async def responder():
            # Expect session.begin
            raw_msg1 = await asyncio.wait_for(ws.recv(), timeout=2.0)
            msg1 = json.loads(raw_msg1)
            assert msg1["method"] == "session.begin"
            await ws.send(json.dumps({"id": msg1["id"], "type": "response", "ok": True, "result": {"ok": True}}))

            # Expect tabs.list
            raw_msg2 = await asyncio.wait_for(ws.recv(), timeout=2.0)
            msg2 = json.loads(raw_msg2)
            assert msg2["method"] == "tabs.list"
            await ws.send(json.dumps({
                "id": msg2["id"],
                "type": "response",
                "ok": True,
                "result": {
                    "tabs": [{"tab_id": 10, "url": "https://example.com", "title": "Example", "active": True, "controlled": True}]
                }
            }))

        responder_task = asyncio.create_task(responder())

        # Test navigate_impl through this real bridge connection
        machine = RtsiMachine(bridge=bridge, settings=settings)
        res = await machine.handle("root--browser", {}, describe_root_fn=lambda: [])
        
        await responder_task

        assert res["success"] is True
        assert res["terminate"] is False
        assert "Browser control started." in res["message"]
        assert len(res["result"]["tabs"]) == 1
        assert res["result"]["tabs"][0]["tab_id"] == 10

    # Stop bridge
    bridge.stop()
