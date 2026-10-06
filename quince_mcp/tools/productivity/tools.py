from quince_mcp.schemas.tool import QuinceTool

from .handlers import (
    _cancel_timer,
    _delete_note,
    _edit_note,
    _list_notes,
    _list_timers,
    _read_note,
    _set_timer,
    _write_note,
)


base_tool_id = "root--productivity"


write_note = QuinceTool(
    tool_id=f"{base_tool_id}--notes--write-note",
    description=(
        "CREATE A NEW LOCAL MARKDOWN NOTE. "
        "Use when the user explicitly asks you to save, record, remember-for-later, "
        "write down, or make a note of information. "

        "CRITICAL: note_name is ONLY the filename/title. "
        "content is the ACTUAL NOTE BODY. "
        "The content must preserve the substantive information from the user's "
        "request. NEVER put only the generated title into content. "

        "Example: if the user says "
        "'Make a note that my database exam is on Friday at 10 AM', "
        "a valid call is "
        "note_name='Database Exam', "
        "content='Database exam is on Friday at 10 AM.' "

        "If the user supplies multiple sentences, paragraphs, bullets, code, "
        "or a block of text, preserve all of it in content. "
        "Do not summarize, compress, paraphrase, or omit substantive information "
        "unless the user explicitly asks for a summary. "

        "For an ordinary note-taking request, overwrite must be false. "
        "Only set overwrite=true when the user explicitly asks to replace the "
        "entire existing note."
    ),
    handler=_write_note,
    arguments={
        "note_name": {
            "type": "string",
            "description": (
                "TITLE/FILENAME ONLY. "
                "A concise descriptive title for the note. "
                "This is NOT the note content."
            ),
        },
        "content": {
            "type": "string",
            "description": (
                "THE COMPLETE NOTE BODY. "
                "Write the actual information the user asked Quince to save. "
                "Preserve all substantive details from the user's request. "
                "Never use only the note title here. "
                "Never summarize unless the user explicitly requested summarization."
            ),
        },
        "overwrite": {
            "type": "boolean",
            "description": (
                "Set true only when the user explicitly asks to completely "
                "replace an existing note. Otherwise use false."
            ),
        },
    },
    required_arguments=["note_name", "content"],
)


read_note = QuinceTool(
    tool_id=f"{base_tool_id}--notes--read-note",
    description=(
        "READ ONE EXISTING LOCAL MARKDOWN NOTE. "
        "Use when the user asks to read, open, show, retrieve, inspect, "
        "or quote a saved note. "
        "The note name may be approximate."
    ),
    handler=_read_note,
    arguments={
        "note_name": {
            "type": "string",
            "description": (
                "The note name described by the user. "
                "Pass the user's wording without inventing a different filename."
            ),
        }
    },
    required_arguments=["note_name"],
)


list_notes = QuinceTool(
    tool_id=f"{base_tool_id}--notes--list-notes",
    description=(
        "LIST ALL SAVED LOCAL MARKDOWN NOTES. "
        "Use when the user asks what notes exist or needs to identify a note."
    ),
    handler=_list_notes,
)


delete_note = QuinceTool(
    tool_id=f"{base_tool_id}--notes--delete-note",
    description=(
        "DELETE ONE EXISTING LOCAL MARKDOWN NOTE. "
        "Use only when the user explicitly asks to delete, remove, erase, "
        "or discard a specific note."
    ),
    handler=_delete_note,
    arguments={
        "note_name": {
            "type": "string",
            "description": (
                "The note name described by the user. "
                "It may be approximate."
            ),
        }
    },
    required_arguments=["note_name"],
)


edit_note = QuinceTool(
    tool_id=f"{base_tool_id}--notes--edit-note",
    description=(
        "EDIT ONE EXISTING LOCAL MARKDOWN NOTE. "
        "Use when the user explicitly asks to modify, update, append, prepend, "
        "or replace content in an existing note. "

        "For replace, content must be the COMPLETE NEW NOTE BODY. "
        "For append, content is the exact text to add at the end. "
        "For prepend, content is the exact text to add at the beginning. "
        "For replace_text, provide the exact old and new text."
    ),
    handler=_edit_note,
    arguments={
        "note_name": {
            "type": "string",
            "description": "The existing note name. Approximate names are allowed.",
        },
        "content": {
            "type": "string",
            "description": (
                "For replace: the complete new note body. "
                "For append/prepend: the exact Markdown text to add."
            ),
        },
        "operation": {
            "type": "string",
            "enum": [
                "replace",
                "append",
                "prepend",
                "replace_text",
            ],
            "description": (
                "replace = full rewrite; "
                "append = add to end; "
                "prepend = add to beginning; "
                "replace_text = exact substitution."
            ),
        },
        "old_text": {
            "type": "string",
            "description": (
                "For replace_text only: exact existing text to replace."
            ),
        },
        "new_text": {
            "type": "string",
            "description": (
                "For replace_text only: exact replacement text."
            ),
        },
    },
    required_arguments=["note_name", "operation"],
)


notes = QuinceTool(
    tool_id=f"{base_tool_id}--notes",
    description=(
        "LOCAL NOTE MANAGEMENT. "
        "Use for explicit requests to save, read, list, edit, or delete notes. "
        "Notes are different from long-term memory and behavioral commands."
    ),
    kind="category",
    children=[
        write_note,
        read_note,
        list_notes,
        edit_note,
        delete_note,
    ],
)



set_timer = QuinceTool(
    tool_id=f"{base_tool_id}--timers--set-timer",
    description=(
        "START ONE LOCAL COUNTDOWN TIMER. "
        "Use for explicit duration-based timer requests such as "
        "'set a 10 minute timer'."
    ),
    handler=_set_timer,
    arguments={
        "duration_seconds": {
            "type": "integer",
            "description": (
                "Exact timer duration in seconds. "
                "30 seconds = 30, 5 minutes = 300, 1 hour = 3600."
            ),
            "minimum": 1,
            "maximum": 604800,
        },
        "label": {
            "type": "string",
            "description": (
                "Short description of what the timer is for. "
                "Use 'Timer' if no label is provided."
            ),
        },
    },
    required_arguments=["duration_seconds"],
)


list_timers = QuinceTool(
    tool_id=f"{base_tool_id}--timers--list-timers",
    description=(
        "LIST CURRENTLY ACTIVE COUNTDOWN TIMERS. "
        "Use when the user asks what timers are currently running."
    ),
    handler=_list_timers,
)


cancel_timer = QuinceTool(
    tool_id=f"{base_tool_id}--timers--cancel-timer",
    description=(
        "CANCEL ONE ACTIVE COUNTDOWN TIMER. "
        "Use only when the user explicitly asks to stop or cancel a timer. "
        "Use the exact timer ID returned by a previous timer result."
    ),
    handler=_cancel_timer,
    arguments={
        "timer_id": {
            "type": "string",
            "description": (
                "Exact timer ID returned by set_timer or list_timers. "
                "Never invent one."
            ),
        }
    },
    required_arguments=["timer_id"],
)


timers = QuinceTool(
    tool_id=f"{base_tool_id}--timers",
    description=(
        "LOCAL COUNTDOWN TIMER MANAGEMENT. "
        "Use for explicit duration-based timer requests."
    ),
    kind="category",
    children=[
        set_timer,
        list_timers,
        cancel_timer,
    ],
)



productivity = QuinceTool(
    tool_id=base_tool_id,
    description=(
        "LOCAL PERSONAL PRODUCTIVITY TOOLS. "
        "Includes Markdown note management and countdown timers. "
        "Use notes for explicit note-taking requests. "
        "Use timers for explicit countdown requests."
    ),
    kind="category",
    children=[
        notes,
        timers,
    ],
)


productivity_tool_tree = {
    f"{base_tool_id}": productivity,

    f"{base_tool_id}--notes": notes,
    f"{base_tool_id}--notes--write-note": write_note,
    f"{base_tool_id}--notes--read-note": read_note,
    f"{base_tool_id}--notes--list-notes": list_notes,
    f"{base_tool_id}--notes--edit-note": edit_note,
    f"{base_tool_id}--notes--delete-note": delete_note,

    f"{base_tool_id}--timers": timers,
    f"{base_tool_id}--timers--set-timer": set_timer,
    f"{base_tool_id}--timers--list-timers": list_timers,
    f"{base_tool_id}--timers--cancel-timer": cancel_timer,
}