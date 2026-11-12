"""quince_mcp.bridge — WebSocket bridge between the MCP server and Chrome extension."""
from .server import ExtensionBridge, bridge, start_bridge

__all__ = ["ExtensionBridge", "bridge", "start_bridge"]
