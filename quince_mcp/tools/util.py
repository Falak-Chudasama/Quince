from quince_mcp.schemas.tool import Tool

chat = Tool(
    tool_id="root.chat",
    description="If user does not need any other tasks to be done, and just needs a simple response from you, choose this option"
)

terminate = Tool(
    tool_id="terminate",
    description="If everything in the prompt has been executed, choose this option",
)

reset = Tool(
    tool_id="reset",
    description="If the tool you are looking for or its category or subcategory does not exist here, choose this option",
)