from __future__ import annotations

from quince_mcp.schemas.tool import QuinceTool
from .handlers import (
    _list_directory,
    _read_file,
    _write_file,
    _append_file,
    _search_files,
    _get_file_info,
    _make_directory,
    _copy_file,
    _move_file,
    _delete_file,
)

base_tool_id = "root--files"

list_directory = QuinceTool(
    tool_id=f"{base_tool_id}--list-directory",
    description=(
        "LIST FILES AND FOLDERS IN A DIRECTORY. "
        "Use when the user asks to see what is in a folder or directory, "
        "like 'what's on my Desktop', 'list files in Downloads', or 'show folder contents'."
    ),
    handler=_list_directory,
    arguments={
        "path": {
            "type": "string",
            "description": "Folder path to list (e.g. 'Desktop', 'Downloads', 'Documents', 'C:\\\\Projects'). Defaults to user home if empty."
        },
        "include_hidden": {
            "type": "boolean",
            "description": "Whether to include hidden files (files starting with a dot)."
        }
    },
    required_arguments=[]
)

read_file = QuinceTool(
    tool_id=f"{base_tool_id}--read-file",
    description=(
        "READ TEXT CONTENT FROM A LOCAL FILE. "
        "Use when the user asks to read, inspect, check, or view the contents of a file (text, code, markdown, csv, json)."
    ),
    handler=_read_file,
    arguments={
        "path": {
            "type": "string",
            "description": "Full or relative path to the file to read."
        },
        "max_chars": {
            "type": "integer",
            "description": "Maximum characters to return (default 4000)."
        },
        "start_line": {
            "type": "integer",
            "description": "Line number to start reading from (1-indexed)."
        }
    },
    required_arguments=["path"]
)

write_file = QuinceTool(
    tool_id=f"{base_tool_id}--write-file",
    description=(
        "CREATE OR OVERWRITE A FILE WITH SPECIFIED CONTENT. "
        "Use when the user asks to create a file, save content to a file, or write a script/document."
    ),
    handler=_write_file,
    arguments={
        "path": {
            "type": "string",
            "description": "Destination file path (e.g. 'Desktop/todo.txt', 'C:\\\\Users\\\\...\\\\script.py')."
        },
        "content": {
            "type": "string",
            "description": "The exact text content to write."
        },
        "overwrite": {
            "type": "boolean",
            "description": "Whether to overwrite if the file already exists (default false)."
        }
    },
    required_arguments=["path", "content"]
)

append_file = QuinceTool(
    tool_id=f"{base_tool_id}--append-file",
    description=(
        "APPEND TEXT CONTENT TO THE END OF AN EXISTING FILE. "
        "Use when the user asks to add, append, or log text to a file without overwriting existing data."
    ),
    handler=_append_file,
    arguments={
        "path": {
            "type": "string",
            "description": "Path to the file."
        },
        "content": {
            "type": "string",
            "description": "The text content to append."
        }
    },
    required_arguments=["path", "content"]
)

search_files = QuinceTool(
    tool_id=f"{base_tool_id}--search-files",
    description=(
        "SEARCH FOR FILES MATCHING A GLOB PATTERN OR NAME. "
        "Use when the user asks to find, locate, or search for a file (e.g. 'find my resume.pdf', 'search for *.py in Projects')."
    ),
    handler=_search_files,
    arguments={
        "pattern": {
            "type": "string",
            "description": "Search pattern or filename (e.g. '*.pdf', '*report*', 'main.py')."
        },
        "root_dir": {
            "type": "string",
            "description": "Directory to search within (e.g. 'Downloads', 'Documents', 'C:\\\\'). Defaults to user home."
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum results to return (default 25)."
        }
    },
    required_arguments=["pattern"]
)

get_file_info = QuinceTool(
    tool_id=f"{base_tool_id}--get-file-info",
    description=(
        "GET DETAILED METADATA ABOUT A FILE OR FOLDER (size, creation time, modification time, type). "
        "Use when the user asks how big a file is, when it was modified, or if it exists."
    ),
    handler=_get_file_info,
    arguments={
        "path": {
            "type": "string",
            "description": "Path to the file or directory."
        }
    },
    required_arguments=["path"]
)

make_directory = QuinceTool(
    tool_id=f"{base_tool_id}--make-directory",
    description=(
        "CREATE A NEW DIRECTORY / FOLDER. "
        "Use when the user asks to create a folder or directory on disk."
    ),
    handler=_make_directory,
    arguments={
        "path": {
            "type": "string",
            "description": "Path of the directory to create."
        }
    },
    required_arguments=["path"]
)

copy_file = QuinceTool(
    tool_id=f"{base_tool_id}--copy-file",
    description=(
        "COPY A FILE OR DIRECTORY TO A NEW LOCATION. "
        "Use when the user asks to copy a file or folder."
    ),
    handler=_copy_file,
    arguments={
        "source": {
            "type": "string",
            "description": "Source file or directory path."
        },
        "destination": {
            "type": "string",
            "description": "Destination file or directory path."
        }
    },
    required_arguments=["source", "destination"]
)

move_file = QuinceTool(
    tool_id=f"{base_tool_id}--move-file",
    description=(
        "MOVE OR RENAME A FILE OR DIRECTORY. "
        "Use when the user asks to move a file, or rename a file or folder."
    ),
    handler=_move_file,
    arguments={
        "source": {
            "type": "string",
            "description": "Source path."
        },
        "destination": {
            "type": "string",
            "description": "Destination path."
        }
    },
    required_arguments=["source", "destination"]
)

delete_file = QuinceTool(
    tool_id=f"{base_tool_id}--delete-file",
    description=(
        "DELETE A FILE OR DIRECTORY FROM DISK. "
        "Use only when the user explicitly asks to delete or remove a file or folder."
    ),
    handler=_delete_file,
    choice="required",
    arguments={
        "path": {
            "type": "string",
            "description": "Path of the file or directory to delete."
        }
    },
    required_arguments=["path"]
)

files = QuinceTool(
    tool_id=base_tool_id,
    description=(
        "FILE SYSTEM AND DIRECTORY MANAGEMENT. "
        "List files in directories, read files, write/create files, append text, search files by pattern, "
        "inspect file metadata, create folders, copy, move/rename, or delete files."
    ),
    kind="category",
    children=[
        list_directory,
        read_file,
        write_file,
        append_file,
        search_files,
        get_file_info,
        make_directory,
        copy_file,
        move_file,
        delete_file,
    ]
)

files_tool_tree = {
    f"{base_tool_id}": files,
    f"{base_tool_id}--list-directory": list_directory,
    f"{base_tool_id}--read-file": read_file,
    f"{base_tool_id}--write-file": write_file,
    f"{base_tool_id}--append-file": append_file,
    f"{base_tool_id}--search-files": search_files,
    f"{base_tool_id}--get-file-info": get_file_info,
    f"{base_tool_id}--make-directory": make_directory,
    f"{base_tool_id}--copy-file": copy_file,
    f"{base_tool_id}--move-file": move_file,
    f"{base_tool_id}--delete-file": delete_file,
}
