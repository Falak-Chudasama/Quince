from quince_mcp.menu_node import MenuNode
from .file_tools import file_search_tool

file_root = MenuNode(
    "file_system",
    "File System",
    "Search local files.",
)

file_search = MenuNode(
    id="search_files",
    name="Search Files",
    description="Find files by name and optional extension.",
    handler=file_search_tool,
    parameters={
        "type": "object",
        "properties": {
            "file_name": {
                "type": "string",
                "description": "Name or partial name.",
            },
            "extension": {
                "type": "string",
                "description": "Optional extension, e.g. .py.",
            },
            "root_path": {
                "type": "string",
                "description": "Directory to search from.",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": ["file_name"],
    },
)

file_root.add_child(file_search)
