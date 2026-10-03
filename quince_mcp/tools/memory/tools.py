from quince_mcp.schemas.tool import QuinceTool
from quince_mcp.apis.basket import basket_client


base_tool_id = "root--memory"


add_memory = QuinceTool(
    tool_id=f"{base_tool_id}--add-memory",
    description=(
        "STORE A FACT, PREFERENCE, OR PIECE OF INFORMATION. "
        "Use ONLY when the user explicitly asks Quince to remember, save, retain, "
        "or store information about the user, their preferences, projects, circumstances, "
        "or another factual piece of context. "
        "DO NOT use this tool for behavioral rules or instructions telling Quince HOW TO RESPOND "
        "or WHAT TO DO. Behavioral rules belong to root--memory--add-command. "
        "Examples: 'Remember that I prefer dark mode.' "
        "'Remember that my project uses MongoDB.' "
        "'Remember that I am a B.Tech IT student.' "
        "Not for this tool: 'Always greet me warmly.' "
        "'Never use emojis.' "
        "'Whenever I ask X, do Y.' "
        "Those are commands, not memories."
    ),
    handler=basket_client.add_memory,
    arguments={
        "memory": {
            "type": "string",
            "description": (
                "ONLY the information that should be remembered. "
                "Generate a concise standalone statement containing the actual fact, "
                "preference, context, or information. "
                "Remove phrases such as 'remember this', 'save this', "
                "'keep this permanently', 'for future sessions', and other retention instructions. "
                "Do not include conversational framing. "
                "Example: user says 'Remember that I prefer dark mode permanently.' "
                "Store: 'The user prefers dark mode.'"
            )
        },
        "is_temporary": {
            "type": "boolean",
            "description": (
                "Controls retention only. "
                "Set true for temporary or session-only storage. "
                "Set false for persistent, permanent, long-term, or cross-session storage. "
                "Do not describe retention inside the memory text."
            )
        }
    },
    required_arguments=["memory", "is_temporary"]
)


get_all_memory = QuinceTool(
    tool_id=f"{base_tool_id}--get-all-memory",
    description=(
        "READ STORED MEMORIES. "
        "Use when the user asks what Quince remembers, asks to see stored memories, "
        "asks whether a particular fact is remembered, or when you need to identify "
        "a specific stored memory before deleting it. "
        "This tool only retrieves memories. It does not add, modify, or delete anything. "
        "For deleting a specific memory, use this tool first to obtain its ID."
    ),
    handler=basket_client.get_all_memory
)


delete_memory = QuinceTool(
    tool_id=f"{base_tool_id}--delete-memory",
    description=(
        "DELETE ONE SPECIFIC STORED MEMORY. "
        "Use only when the user wants one particular fact, preference, or memory removed. "
        "Always call root--memory--get-all-memory first when the user identifies the target "
        "by meaning, description, topic, wording, or fuzzy language. "
        "Use only an ID returned by root--memory--get-all-memory. Never invent or guess an ID. "
        "Do not use this tool to delete all memories."
    ),
    handler=basket_client.delete_memory,
    arguments={
        "memory-id": {
            "type": "string",
            "description": (
                "The exact ID of the memory to delete. "
                "Obtain it from root--memory--get-all-memory and match the user's description "
                "against the returned memory contents. Never fabricate or guess an ID."
            )
        }
    },
    required_arguments=["memory-id"]
)


delete_all_memory = QuinceTool(
    tool_id=f"{base_tool_id}--delete-all-memory",
    description=(
        "DELETE ALL STORED MEMORIES. "
        "Use ONLY when the user explicitly asks to erase, forget, clear, or delete "
        "ALL stored memories. "
        "Do not use this tool for deleting one memory or a specific subset."
    ),
    handler=basket_client.delete_all_memory
)


add_command = QuinceTool(
    tool_id=f"{base_tool_id}--add-command",
    description=(
        "STORE A BEHAVIORAL RULE OR INSTRUCTION FOR QUINCE. "
        "Use ONLY when the user explicitly asks Quince to remember, save, retain, "
        "or follow a rule describing HOW QUINCE SHOULD BEHAVE, RESPOND, or ACT. "
        "Examples: 'Always greet me warmly.' "
        "'Never use emojis.' "
        "'When I ask for code, include comments.' "
        "'Whenever I say X, do Y.' "
        "DO NOT use this tool for ordinary facts, preferences, or personal information. "
        "Those belong to root--memory--add-memory. "
        "If the stored text tells Quince WHAT TO DO or HOW TO BEHAVE, it is a COMMAND. "
        "If it tells Quince SOMETHING THAT IS TRUE or PREFERRED, it is a MEMORY."
    ),
    handler=basket_client.add_command,
    arguments={
        "command": {
            "type": "string",
            "description": (
                "ONLY the reusable behavioral instruction Quince should follow. "
                "Generate a concise standalone rule. "
                "Do not include 'remember this', 'save this', 'keep this permanently', "
                "'for future sessions', or any other retention wording. "
                "Retention belongs only in is_temporary. "
                "Example: user says 'Whenever I ask you to greet me, greet me warmly and naturally, "
                "and remember this permanently.' "
                "Store: 'Whenever the user asks to be greeted, greet them warmly and naturally.'"
            )
        },
        "is_temporary": {
            "type": "boolean",
            "description": (
                "Controls retention only. "
                "Set true for temporary or session-only storage. "
                "Set false for persistent, permanent, long-term, or cross-session storage. "
                "If the user says permanently, forever, long-term, or across future sessions, "
                "set this to false."
            )
        }
    },
    required_arguments=["command", "is_temporary"]
)


get_all_commands = QuinceTool(
    tool_id=f"{base_tool_id}--get-all-commands",
    description=(
        "READ STORED BEHAVIORAL COMMANDS. "
        "Use when the user asks what rules, instructions, or behavioral commands "
        "Quince has stored, or when you need to identify a specific command before deleting it. "
        "This tool only retrieves commands. It does not add, modify, or delete anything. "
        "For deleting a specific command, use this tool first to obtain its ID."
    ),
    handler=basket_client.get_all_commands
)


delete_command = QuinceTool(
    tool_id=f"{base_tool_id}--delete-command",
    description=(
        "DELETE ONE SPECIFIC STORED BEHAVIORAL COMMAND. "
        "Use only when the user wants one particular stored rule or instruction removed. "
        "Always call root--memory--get-all-commands first when the user identifies the target "
        "by meaning, description, wording, behavior, or fuzzy language. "
        "Use only an ID returned by root--memory--get-all-commands. Never invent or guess an ID. "
        "Do not use this tool to delete all commands."
    ),
    handler=basket_client.delete_command,
    arguments={
        "command-id": {
            "type": "string",
            "description": (
                "The exact ID of the command to delete. "
                "Obtain it from root--memory--get-all-commands and match the user's description "
                "against the returned command contents. Never fabricate or guess an ID."
            )
        }
    },
    required_arguments=["command-id"]
)


delete_all_commands = QuinceTool(
    tool_id=f"{base_tool_id}--delete-all-commands",
    description=(
        "DELETE ALL STORED BEHAVIORAL COMMANDS. "
        "Use ONLY when the user explicitly asks to erase, forget, clear, or delete "
        "ALL stored commands, rules, or behavioral instructions. "
        "Do not use this tool for deleting one command or a specific subset."
    ),
    handler=basket_client.delete_all_commands
)


memory = QuinceTool(
    tool_id=base_tool_id,
    description=(
        "MANAGE STORED MEMORIES AND BEHAVIORAL COMMANDS. "
        "MEMORY = something that is TRUE, KNOWN, PREFERRED, or PERSONAL CONTEXT. "
        "Examples: 'I prefer dark mode', 'My project uses MongoDB', "
        "'I am a B.Tech IT student'. "
        "COMMAND = something Quince must DO, FOLLOW, AVOID, or HOW IT MUST BEHAVE. "
        "Examples: 'Always greet me warmly', 'Never use emojis', "
        "'When I ask for code, include comments'. "
        "Use root--memory--add-memory for facts, preferences, and context. "
        "Use root--memory--add-command for behavioral rules and instructions. "
        "Use root--memory--get-all-memory to read memories. "
        "Use root--memory--get-all-commands to read commands. "
        "When deleting one item, first call the corresponding get-all tool to obtain its real ID, "
        "then call the corresponding delete tool. Never invent an ID. "
        "Use root--memory--delete-all-memory only for deleting all memories. "
        "Use root--memory--delete-all-commands only for deleting all commands."
    ),
    kind="category",
    children=[
        add_memory,
        get_all_memory,
        delete_memory,
        delete_all_memory,
        add_command,
        get_all_commands,
        delete_command,
        delete_all_commands,
    ]
)


memory_tool_tree = {
    f"{base_tool_id}": memory,

    f"{base_tool_id}--add-memory": add_memory,
    f"{base_tool_id}--get-all-memory": get_all_memory,
    f"{base_tool_id}--delete-memory": delete_memory,
    f"{base_tool_id}--delete-all-memory": delete_all_memory,

    f"{base_tool_id}--add-command": add_command,
    f"{base_tool_id}--get-all-commands": get_all_commands,
    f"{base_tool_id}--delete-command": delete_command,
    f"{base_tool_id}--delete-all-commands": delete_all_commands,
}