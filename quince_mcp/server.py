from typing import Any
from mcp.server import MCPServer

from quince_mcp.utils.execute import execute
from quince_mcp.tool_tree import TOOL_TREE, root
from quince_mcp.tools.util import terminate_summary, reset_summary
from quince_mcp.utils.message import build_message

mcp = MCPServer("Quince MCP")


@mcp.tool()
async def navigate(tool_id: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    if tool_id == "terminate" or tool_id == "root--chat":
        return build_message(
            children=[],
            message="Loop Terminate",
            was_category_call=False,
            terminate=True,
        )
    elif tool_id == "reset":
        children = []
        for c in root.children:
            child_obj = {
                "tool_id": c.tool_id,
                "description": c.description,
                "feedback": c.feedback,
                "kind": c.kind,
                "arguments": c.arguments,
                "required_arguments": c.required_arguments,
            }

            if len(c.prereq_services) > 0:
                prereq_results = {}
                
                for service_id, arguments, handler in c.prereq_services:
                    result = await execute(handler, arguments)
                    prereq_results[f"{service_id}_result"] = result

                child_obj["prereq_results"] = prereq_results

            children.append(child_obj)

        children.append(terminate_summary)

        return build_message(children=children,message="Category contents")

    tool = TOOL_TREE.get(tool_id)

    if tool is None:
        return { "message": f"Tool with tool_id {tool_id} does not exist", "success": False }

    if tool.kind == "category":
        children = []
        for c in tool.children:
            child_obj = {
                "tool_id": c.tool_id,
                "description": c.description,
                "feedback": c.feedback,
                "kind": c.kind,
                "arguments": c.arguments,
                "required_arguments": c.required_arguments,
            }

            if len(c.prereq_services) > 0:
                prereq_results = {}

                for service_id, arguments, handler in c.prereq_services:
                    result = await execute(handler, arguments)
                    prereq_results[f"{service_id}_result"] = result

                child_obj["prereq_results"] = prereq_results

            children.append(child_obj)

        children.extend([terminate_summary, reset_summary])

        return build_message(children=children,message="Category contents")

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