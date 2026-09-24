from quince_mcp.schemas.tool import QuinceTool
from .handlers import _get_ram_usage


get_ram_usage = QuinceTool(
    tool_id="root.system.get_ram_usage",
    description="",
    handler=_get_ram_usage
)


system = QuinceTool(
    tool_id="root.system",
    description="",
    kind="category",
    children=[get_ram_usage]
)

system_tool_tree = {
    "root.system": system,
    "root.system.get_ram_usage": get_ram_usage
}