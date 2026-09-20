from typing import Any
from mcp.server import MCPServer

from quince_mcp.schemas.tool import QuinceTool
from quince_mcp.tools.util import terminate, reset, chat
# from quince_mcp.tools.system.system import SYSTEM_TOOLS_TREE


mcp = MCPServer("Quince MCP")

root = QuinceTool(tool_id="root", kind="category", description="", children=[chat])

TOOL_TREE = {
    "root": root,
    "terminate": terminate,
    "reset": reset,
    "root.chat": chat
    # **SYSTEM_TOOLS_TREE
}


terminate_summary = { "tool_id": terminate.tool_id, "description": terminate.description, "arguments": terminate.arguments }
reset_summary = { "tool_id": reset.tool_id, "description": reset.description, "arguments": reset.arguments }
ALWAYS_AVAILABLE = [terminate_summary, reset_summary]


@mcp.tool()
async def navigate(tool_id: str, arguments: dict[str, Any] | None = None):
    if tool_id == "terminate":
        return {
            "children": [],
            "message": "Execution terminated",
            "was_category_call": False,
            "terminate": True,
            "success": True
        }
    elif tool_id == "reset":
        return {
            "children": [
                {
                    "tool_id": c.tool_id,
                    "description": c.description,
                    "arguments": c.arguments
                }
                for c in root.children
            ] + [terminate_summary],
            "message": "Navigation reset to root",
            "was_category_call": True,
            "terminate": False,
            "success": True
        }

    tool = TOOL_TREE.get(tool_id)

    if tool is None:
        return { "message": f"Tool with tool_id {tool_id} does not exist", "success": False }

    if tool.kind == "category":
        return {
            "message": "Category contents",
            "was_category_call": True,
            "terminate": False,
            "success": True,
            "children": [
                {
                    "tool_id": c.tool_id,
                    "description": c.description,
                    "feedback": c.feedback,
                    "arguments": c.arguments,
                    "required_arguments": c.required_arguments,
                }
                for c in tool.children
            ] + ALWAYS_AVAILABLE
        }

    try:
        result = await tool.execute(arguments or {})
    except Exception as exc:
        return {
            "message": f"Failure while executing {tool_id}: {exc}",
            "error": str(exc),
            "terminate": True,
            "was_category_call": True,
            "success": False
        }

    return {
        "message": tool.feedback,
        "success": True,
        "result": result,
        "was_category_call": False,
    }