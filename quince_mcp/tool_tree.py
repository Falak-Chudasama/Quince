from quince_mcp.schemas.tool import QuinceTool
from quince_mcp.tools.util import terminate, reset, chat
from quince_mcp.tools.system.tools import system, system_tool_tree
from quince_mcp.tools.memory.tools import memory, memory_tool_tree
from quince_mcp.tools.productivity.tools import productivity, productivity_tool_tree
from quince_mcp.tools.knowledge.tools import knowledge, knowledge_tool_tree


root = QuinceTool(
    tool_id="root",
    kind="category",
    description=(
        "Top-level menu. Pick the category that matches the user's requested capability. "
        "system = direct Windows computer control and hardware telemetry; "
        "productivity = local Quince notes and countdown timers; use productivity notes for prompts such as 'save this', 'write this down', 'make a note', 'read my notes', or 'edit my note'; "
        "knowledge = Wikipedia and Wikimedia knowledge retrieval; "
        "memory = stored memories and behavioral commands. "
        "If the request is general conversation, something you can answer directly, or "
        "doesn't need live data from this device or these services, pick chat — never guess a category."
    ),
    children=[chat, system, productivity, knowledge, memory],
)


TOOL_TREE = {
    "root": root,
    "terminate": terminate,
    "reset": reset,
    "root--chat": chat,
    **system_tool_tree,
    **productivity_tool_tree,
    **knowledge_tool_tree,
    **memory_tool_tree
}
