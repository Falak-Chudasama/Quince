from quince_mcp.schemas.tool import QuinceTool

chat = QuinceTool(
    tool_id="root.chat",
    description="If user does not need any other tasks to be done, and just needs a simple response from you, choose this option",
    kind="leaf",
)

terminate = QuinceTool(
    tool_id="terminate",
    description="If everything in the prompt has been executed, choose this option",
    kind="leaf",
)

reset = QuinceTool(
    tool_id="reset",
    description="If the tool you are looking for or its category or subcategory does not exist here, choose this option",
    kind="leaf",
)

terminate_summary = { "tool_id": terminate.tool_id, "description": terminate.description, "arguments": terminate.arguments }
reset_summary = { "tool_id": reset.tool_id, "description": reset.description, "arguments": reset.arguments }

DEFAULT_UTILITY = [terminate, reset]