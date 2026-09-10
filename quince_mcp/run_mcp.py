from __future__ import annotations

import asyncio
import os

from quince_mcp.root_mcp import build_root
from quince_mcp.server import MCPServer


async def main() -> None:
    server = MCPServer(
        build_root(os.getenv("BASKET_API_URL", "http://127.0.0.1:7000")),
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("MCP_PORT", "7100")),
    )
    await server.start()
    try:
        await asyncio.Future()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
