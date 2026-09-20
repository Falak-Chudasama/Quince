from quince_mcp.schemas.tool import Tool

async def save_command(command: str, is_persistent: bool):
    pass
async def save_long_term(memory: str):
    pass


command = Tool(
    tool_id="root.memory.command",
    description="If user needs you to set up or save a command from the prompt, choose this option",
    arguments_types={
        "command": "string",
        "is_persistent": "boolean"
    },
    handler=save_command,
)

long_term_mem = Tool(
    tool_id="root.memory.long-term-memory",
    description="If user needs you to set up or save a long term memory from the prompt, choose this option",
    arguments_types={
        "memory": "string",
    },
    handler=save_long_term,
)