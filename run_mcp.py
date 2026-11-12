import argparse
import os
from quince_mcp.server import mcp

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quince MCP Server")
    parser.add_argument(
        "--transport",
        choices=["streamable-http", "sse", "stdio"],
        default=os.getenv("QUINCE_MCP_TRANSPORT", "streamable-http"),
        help="Transport protocol (default: streamable-http)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("QUINCE_MCP_HOST", "127.0.0.5"),
        help="Host for streamable-http / sse (default: 127.0.0.5)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("QUINCE_MCP_PORT", "10010")),
        help="Port for streamable-http / sse (default: 10010)",
    )
    parser.add_argument(
        "--path",
        default=os.getenv("QUINCE_MCP_PATH", "/mcp"),
        help="Path for streamable-http (default: /mcp)",
    )
    args = parser.parse_args()

    if args.transport == "streamable-http":
        print(f"[Quince MCP] Running on Streamable HTTP at http://{args.host}:{args.port}{args.path}")
        bridge_host = os.getenv("QUINCE_BRIDGE_HOST", "127.0.0.5")
        bridge_port = os.getenv("QUINCE_BRIDGE_PORT", "7100")
        print(f"[Quince MCP] Chrome Extension Bridge active on ws://{bridge_host}:{bridge_port}/")
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            streamable_http_path=args.path,
        )
    elif args.transport == "sse":
        print(f"[Quince MCP] Running on SSE at http://{args.host}:{args.port}/sse")
        mcp.run(
            transport="sse",
            host=args.host,
            port=args.port,
        )
    else:
        mcp.run(transport="stdio")