from quince_mcp.schemas.tool import QuinceTool
from quince_mcp.tools.util import terminate, reset, chat
from quince_mcp.tools.system.tools import system_tool_tree


root = QuinceTool(
    tool_id="root",
    kind="category",
    description="",
    children=[chat],
)


TOOL_TREE = {
    "root": root,
    "terminate": terminate,
    "reset": reset,
    "root.chat": chat,
    **system_tool_tree
}