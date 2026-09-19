from quince_mcp.schemas.tool import Tool


terminate = Tool(
    tool_id="terminate",
    description="If everything in the prompt has been executed, choose this option",
)

reset = Tool(
    tool_id="reset",
    description="If the tool you are looking for or its category or subcategory does not exist here, choose this option",
)