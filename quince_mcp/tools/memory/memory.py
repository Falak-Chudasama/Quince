from quince_mcp.schemas.tool import QuinceTool

async def save_command(command: str, is_persistent: bool):
    pass
async def save_long_term(memory: str):
    pass


command = QuinceTool(
    tool_id="root.memory.command",
    description="If user needs you to set up or save a command from the prompt, choose this option",
    arguments={
        "command": {
            "type": "string",
            "description": "Actual command in the form of text to add, write it yourself"
        }
    },
    kind="leaf",
    handler=save_command,
)

long_term_mem = QuinceTool(
    tool_id="root.memory.long-term-memory",
    description="If user needs you to set up or save a long term memory from the prompt, choose this option",
    arguments={
        "memory": {
            "type": "string",
            "description": "Actual memory in the form of text to add, write it yourself"
        }
    },
    kind="leaf",
    handler=save_long_term,
)