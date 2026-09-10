from __future__ import annotations

import inspect
import json
import logging
from typing import Any

import websockets

from quince_mcp.menu_node import MenuNode
from quince_mcp.protocol import response

logger = logging.getLogger("quince.mcp")


class MCPServer:
    """Hierarchical MCP-over-WebSocket server owned by the Quince process."""

    def __init__(self, root: MenuNode, host: str = "127.0.0.1", port: int = 7100) -> None:
        self.root = root
        self.host = host
        self.port = port
        self._server: Any | None = None

    async def start(self) -> None:
        self._server = await websockets.serve(self._handle, self.host, self.port)
        logger.info("MCP server listening on ws://%s:%d/mcp", self.host, self.port)

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None
        logger.info("MCP server stopped.")

    async def _handle(self, websocket: Any) -> None:
        current = self.root
        logger.info("MCP connection accepted from %s", websocket.remote_address)

        async for raw in websocket:
            request: dict[str, Any] = {}
            try:
                request = json.loads(raw)
                if not isinstance(request, dict):
                    raise ValueError("MCP request must be an object")
                request_id = str(request.get("id", ""))
                message_type = request.get("type")

                if message_type == "reset":
                    current = self.root
                    await websocket.send(json.dumps(response(
                        request_id=request_id,
                        message_type="reset",
                        path=[node.id for node in current.path()],
                        tools=current.to_tool_schema(),
                    )))
                    continue

                if message_type != "call":
                    raise ValueError(f"Unknown MCP message type: {message_type!r}")

                name = request.get("name")
                arguments = request.get("arguments") or {}
                if not isinstance(name, str):
                    raise ValueError("MCP call requires a tool name")
                if not isinstance(arguments, dict):
                    raise ValueError("MCP arguments must be an object")

                node = current.children.get(name)
                if node is None:
                    raise ValueError(
                        f"Tool {name!r} is not visible at path "
                        f"{'/'.join(n.id for n in current.path())}"
                    )

                if node.is_branch:
                    current = node
                    await websocket.send(json.dumps(response(
                        request_id=request_id,
                        message_type="explore",
                        path=[n.id for n in current.path()],
                        tool=name,
                        tools=current.to_tool_schema(),
                    )))
                    continue

                result = node.handler(**arguments) if node.handler else None
                if inspect.isawaitable(result):
                    result = await result

                await websocket.send(json.dumps(response(
                    request_id=request_id,
                    message_type="execute",
                    path=[n.id for n in current.path()],
                    tool=name,
                    result=result,
                )))

            except Exception as exc:
                logger.exception("MCP request failed")
                request_id = str(request.get("id", "")) if isinstance(request, dict) else ""
                await websocket.send(json.dumps(response(
                    request_id=request_id,
                    message_type="error",
                    error=str(exc),
                )))

        logger.info("MCP connection closed: %s", websocket.remote_address)
