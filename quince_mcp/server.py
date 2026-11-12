import logging
import sys
from typing import Any
from mcp.server import MCPServer

# Ensure all library loggers (websockets, asyncio, etc.) log to stderr, never stdout
for _log_name in ("websockets", "asyncio", "mcp"):
    _l = logging.getLogger(_log_name)
    _l.propagate = False
    _l.addHandler(logging.StreamHandler(sys.stderr))

from quince_mcp.utils.execute import execute
from quince_mcp.tool_tree import TOOL_TREE, root
from quince_mcp.tools.util import terminate_summary, reset_summary
from quince_mcp.utils.message import build_message

mcp = MCPServer("Quince MCP")

# Start bridge listener in background daemon thread
try:
    from quince_mcp.bridge.server import start_bridge
    start_bridge()
except Exception:
    pass


async def _describe_children(tool, include_hidden: bool = False):
    children = []

    for c in tool.children:
        # Hidden tools are never listed in children responses.
        if getattr(c, "hidden", False) and not include_hidden:
            continue

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

    return children


async def navigate_impl(tool_id: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Core implementation of the navigate tool.

    Extracted so it can be called directly in tests without going through
    the @mcp.tool() decorator machinery.
    """
    # --- Browser / RTSI delegation ---
    # All root--browser* ids are handled by the RTSI machine.
    if tool_id == "root--browser" or tool_id.startswith("root--browser--"):
        try:
            from quince_mcp.rtsi.machine import get_rtsi_machine
            machine = get_rtsi_machine()
            return await machine.handle(
                tool_id=tool_id,
                arguments=arguments or {},
                describe_root_fn=lambda: _describe_children(root),
            )
        except Exception as exc:
            return build_message(
                message=f"Browser tool error: {exc}",
                error=str(exc),
                terminate=True,
                success=False,
            )

    # --- Existing behaviour (unchanged) ---
    if tool_id == "terminate" or tool_id == "root--chat":
        # End any active RTSI session cleanly before terminating.
        try:
            from quince_mcp.rtsi.machine import get_rtsi_machine
            machine = get_rtsi_machine()
            await machine.abort_active_session(outcome="terminated")
        except Exception:
            pass

        return build_message(
            children=[],
            message="Loop Terminate",
            was_category_call=False,
            terminate=True,
        )
    elif tool_id == "reset":
        # End any active RTSI session cleanly before reset.
        try:
            from quince_mcp.rtsi.machine import get_rtsi_machine
            machine = get_rtsi_machine()
            await machine.abort_active_session(outcome="reset")
        except Exception:
            pass

        try:
            children = await _describe_children(root)
        except Exception as exc:
            return build_message(
                message=f"Failure while building root category: {exc}",
                error=str(exc),
                terminate=True,
                success=False
            )

        children.append(terminate_summary)

        return build_message(children=children, message="Category contents")

    tool = TOOL_TREE.get(tool_id)

    if tool is None:
        return build_message(
            message=f"Tool with tool_id {tool_id} does not exist",
            success=False,
            error="unknown_tool",
            terminate=True,
        )

    if tool.kind == "category":
        try:
            children = await _describe_children(tool)
        except Exception as exc:
            return build_message(
                message=f"Failure while building category {tool_id}: {exc}",
                error=str(exc),
                terminate=True,
                success=False
            )

        children.extend([terminate_summary, reset_summary])

        return build_message(children=children, message="Category contents")

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


@mcp.tool()
async def navigate(tool_id: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    return await navigate_impl(tool_id, arguments)
