from __future__ import annotations

import inspect
import json
import logging
from typing import Any

import websockets
import time

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
        if self._server is not None:
            return
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
        logger.info("MCP CONNECTION OPEN remote=%s", websocket.remote_address)

        try:
            async for raw in websocket:
                started = time.perf_counter()
                request: dict[str, Any] = {}
                try:
                    request = json.loads(raw)
                    if not isinstance(request, dict):
                        raise ValueError("MCP request must be an object")

                    request_id = str(request.get("id", ""))
                    message_type = request.get("type")
                    logger.info(
                        "MCP RECV id=%s type=%s payload=%r",
                        request_id,
                        message_type,
                        request,
                    )

                    if message_type == "reset":
                        current = self.root
                        reply = response(
                            request_id=request_id,
                            message_type="reset",
                            path=[node.id for node in current.path()],
                            tools=current.to_tool_schema(),
                        )
                        logger.info(
                            "MCP RESET path=%s tools=%s",
                            "/".join(node.id for node in current.path()),
                            list(current.children),
                        )
                        await websocket.send(json.dumps(reply))
                        logger.info(
                            "MCP SEND id=%s type=reset elapsed=%.3fs",
                            request_id,
                            time.perf_counter() - started,
                        )
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
                        logger.info(
                            "MCP EXPLORE path=%s tool=%s",
                            "/".join(n.id for n in current.path()),
                            name,
                        )
                        current = node
                        reply = response(
                            request_id=request_id,
                            message_type="explore",
                            path=[n.id for n in current.path()],
                            tool=name,
                            tools=current.to_tool_schema(),
                        )
                        await websocket.send(json.dumps(reply))
                        logger.info(
                            "MCP SEND id=%s type=explore new_path=%s tools=%s elapsed=%.3fs",
                            request_id,
                            "/".join(n.id for n in current.path()),
                            list(current.children),
                            time.perf_counter() - started,
                        )
                        continue

                    logger.info(
                        "MCP EXECUTE START path=%s tool=%s args=%r",
                        "/".join(n.id for n in current.path()),
                        name,
                        arguments,
                    )
                    result = node.handler(**arguments) if node.handler else None
                    if inspect.isawaitable(result):
                        result = await result

                    reply = response(
                        request_id=request_id,
                        message_type="execute",
                        path=[n.id for n in current.path()],
                        tool=name,
                        result=result,
                    )
                    await websocket.send(json.dumps(reply))
                    logger.info(
                        "MCP EXECUTE COMPLETE id=%s tool=%s elapsed=%.3fs result=%r",
                        request_id,
                        name,
                        time.perf_counter() - started,
                        result,
                    )
                except Exception as exc:
                    logger.exception(
                        "MCP REQUEST FAILED id=%s elapsed=%.3fs",
                        request.get("id", "") if isinstance(request, dict) else "",
                        time.perf_counter() - started,
                    )
                    request_id = str(request.get("id", "")) if isinstance(request, dict) else ""
                    reply = response(
                        request_id=request_id,
                        message_type="error",
                        error=str(exc),
                    )
                    await websocket.send(json.dumps(reply))
        finally:
            logger.info("MCP CONNECTION CLOSED remote=%s", websocket.remote_address)
