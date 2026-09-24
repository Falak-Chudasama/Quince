from quince_mcp.schemas.tool import QuinceTool
from quince_mcp.tools.util import terminate, reset, chat
from quince_mcp.tools.system.tools import system, system_tool_tree


root = QuinceTool(
    tool_id="root",
    kind="category",
    description=(
        "Top-level menu. Pick the category that matches what the user is asking about. "
        "If the request is general conversation, something you can answer directly, or "
        "doesn't need live data from this device, pick chat — never guess a category."
    ),
    children=[chat, system],
)


TOOL_TREE = {
    "root": root,
    "terminate": terminate,
    "reset": reset,
    "root.chat": chat,
    **system_tool_tree
}