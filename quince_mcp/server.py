from typing import Any
from mcp.server import MCPServer

from quince_mcp.schemas.tool import Tool
from quince_mcp.tools.util import terminate, reset, chat
# from quince_mcp.tools.system.system import SYSTEM_TOOLS_TREE


mcp = MCPServer("Quince MCP")

root = Tool(tool_id="root", description="", children=[chat])

TOOL_TREE = {
    "root": root,
    "terminate": terminate,
    "reset": reset,
    "root.chat": chat
    # **SYSTEM_TOOLS_TREE
}


terminate_summary = { "tool_id": terminate.tool_id, "description": terminate.description, "argument_types": terminate.arguments_types }
reset_summary = { "tool_id": reset.tool_id, "description": reset.description, "argument_types": reset.arguments_types }
ALWAYS_AVAILABLE = [terminate_summary, reset_summary]


@mcp.tool()
async def navigate(tool_id: str, arguments: dict[str, Any] | None = None):
    if tool_id == "terminate":
        return { "children": [], "message": "Execution terminated", "success": True }
    elif tool_id == "reset":
        return {
            "children": [
                {
                    "tool_id": c.tool_id,
                    "description": c.description,
                    "argument_types": c.arguments_types
                }
                for c in root.children
            ] + [terminate_summary],
            "message": "Navigation reset to root",
            "success": True
        }

    tool = TOOL_TREE.get(tool_id)

    if tool is None:
        return { "message": f"Tool with tool_id {tool_id} does not exist", "success": False }

    if tool.type == "category":
        return {
            "message": "Category contents",
            "success": True,
            "children": [
                {
                    "tool_id": c.tool_id,
                    "description": c.description,
                    "argument_types": c.arguments_types
                }
                for c in tool.children
            ] + ALWAYS_AVAILABLE
        }

    try:
        result = await tool.execute(arguments or {})
    except Exception as exc:
        return { "message": f"Failure while executing {tool_id}: {exc}", "error": str(exc), "success": False }

    return {
        "message": tool.feedback,
        "success": True,
        "result": result,
    }