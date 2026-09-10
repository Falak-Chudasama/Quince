from quince_mcp.file_system.file_tools import file_search_tool
from quince_mcp.menu_node import MenuNode


file_root = MenuNode(
    "file_system",
    "File System",
    "Search the filesystem for files.",
)

file_root.add_child(
    MenuNode(
        "search_files",
        "Search Files",
        "Search recursively for a file by name and optional extension.",
        handler=file_search_tool,
        parameters={
            "type": "object",
            "properties": {
                "file_name": {
                    "type": "string",
                    "description": "Part or all of the file name to search for.",
                },
                "extension": {
                    "type": "string",
                    "description": "Optional file extension, such as .txt or .py.",
                },
                "root_path": {
                    "type": "string",
                    "description": "Directory to search from. Defaults to the current directory.",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Maximum number of matching files to return.",
                },
            },
            "required": ["file_name"],
        },
    )
)
