from typing import Any
from mcp.server import MCPServer

from quince_mcp.tool_tree import TOOL_TREE, root
from quince_mcp.tools.util import terminate_summary, reset_summary
from quince_mcp.utils.message import build_message

mcp = MCPServer("Quince MCP")


@mcp.tool()
async def navigate(tool_id: str, arguments: dict[str, Any] | None = None):
    if tool_id == "terminate" or tool_id == "root.chat":
        return build_message(
            children=[],
            message="Loop Terminate",
            was_category_call=False,
            terminate=True,
        )
    elif tool_id == "reset":
        return build_message(
            children=[
                {
                    "tool_id": c.tool_id,
                    "description": c.description,
                    "feedback": c.feedback,
                    "kind": c.kind,
                    "arguments": c.arguments,
                    "required_arguments": c.required_arguments,
                }
                for c in root.children
            ] + [terminate_summary],
            message="Navigation reset to root",
        )

    tool = TOOL_TREE.get(tool_id)

    if tool is None:
        return { "message": f"Tool with tool_id {tool_id} does not exist", "success": False }

    if tool.kind == "category":
        return build_message(
            children=[
                {
                    "tool_id": c.tool_id,
                    "description": c.description,
                    "feedback": c.feedback,
                    "kind": c.kind,
                    "arguments": c.arguments,
                    "required_arguments": c.required_arguments,
                }
                for c in tool.children
            ] + [terminate_summary, reset_summary],
            message="Category contents",
        )

    try:
        result = await tool.execute(arguments or {})
    except Exception as exc:
        return build_message(
            message=f"Failure while executing {tool_id}: {exc}",
            error=str(exc),
            terminate=True,
            success=False
        )

    return build_message(
        message=tool.feedback,
        result=result,
        was_category_call=False,
        terminate=False,
        children=[terminate_summary, reset_summary]
    )