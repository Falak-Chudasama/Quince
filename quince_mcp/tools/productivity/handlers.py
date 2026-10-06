import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from quince_mcp.util.fuzzy_search import resolve_fuzzy_match
from quince_mcp.tools.system.handlers import _send_notification

NOTES_DIRECTORY = Path(r"C:\Users\ADMIN\OneDrive\CODES\Projects\Projects\Basket\fruits\quince\quince_notes")
NOTE_FUZZY_THRESHOLD = 80.0

_timer_lock = threading.Lock()
_timers: dict[str, dict[str, object]] = {}


def _ensure_notes_directory():
    NOTES_DIRECTORY.mkdir(parents=True, exist_ok=True)


def _normalize_note_name(note_name: str) -> str:
    value = note_name.strip()

    if not value:
        raise ValueError("Note name cannot be empty")

    if value.lower().endswith(".md"):
        value = value[:-3]

    if not value.strip():
        raise ValueError("Note name cannot be empty")

    if any(part in value for part in ("/", "\\")):
        raise ValueError("Note name must be a single file name")

    if value in {".", ".."} or ".." in Path(value).parts:
        raise ValueError("Invalid note name")

    value = re.sub(r"[<>:\"/\\|?*]", "_", value).strip()

    if not value:
        raise ValueError("Note name contains no usable characters")

    return f"{value}.md"


def _note_path(note_name: str) -> Path:
    _ensure_notes_directory()
    filename = _normalize_note_name(note_name)
    path = NOTES_DIRECTORY / filename
    resolved_root = NOTES_DIRECTORY.resolve()
    resolved_path = path.resolve()

    if resolved_path.parent != resolved_root:
        raise ValueError("Invalid note path")

    return path


def _available_note_paths() -> list[Path]:
    _ensure_notes_directory()
    return list(NOTES_DIRECTORY.glob("*.md"))


def _resolve_note_path(note_name: str, require_exists: bool = True) -> Path:
    exact_path = _note_path(note_name)

    if exact_path.exists():
        return exact_path

    if not require_exists:
        return exact_path

    candidates = _available_note_paths()
    match = resolve_fuzzy_match(
        candidates=candidates,
        query=note_name,
        threshold=NOTE_FUZZY_THRESHOLD,
        key=lambda path: path.stem,
    )

    if match is None:
        available = [path.stem for path in candidates]
        if available:
            raise FileNotFoundError(
                f"Note '{note_name}' does not exist and no note matched the 80% similarity threshold"
            )
        raise FileNotFoundError(f"Note '{note_name}' does not exist")

    return match.candidate


def _write_note(
    note_name: str,
    content: str,
    overwrite: bool = False,
):
    """
    Create a Markdown note.

    note_name:
        Filename/title only.

    content:
        The COMPLETE substantive note body.
        This must contain what the user actually asked Quince to remember/write down.
    """
    if not isinstance(note_name, str) or not note_name.strip():
        raise ValueError("note_name must contain the note title")

    if not isinstance(content, str) or not content.strip():
        raise ValueError(
            "content must contain the complete note body and cannot be empty"
        )

    clean_title = note_name.strip()
    clean_content = content.strip()

    # Hard protection against the most common LLM failure:
    # sending the generated title as the entire note body.
    if clean_content.casefold() == clean_title.casefold():
        raise ValueError(
            "INVALID NOTE CONTENT: content contains only the note title. "
            "content must contain the actual information the user asked Quince "
            "to write down, not merely the note title."
        )

    path = _note_path(clean_title)
    existed = path.exists()

    if existed and not overwrite:
        raise FileExistsError(
            f"Note '{path.name}' already exists. "
            "Use edit_note to modify an existing note, or set overwrite=true "
            "only when the user explicitly asks to replace the entire note."
        )

    path.write_text(clean_content, encoding="utf-8", newline="")

    return {
        "note_name": path.stem,
        "path": str(path),
        "content": clean_content,
        "characters": len(clean_content),
        "lines": len(clean_content.splitlines()),
        "overwritten": existed and overwrite,
    }


def _read_note(note_name: str):
    path = _resolve_note_path(note_name)

    return {
        "note_name": path.stem,
        "path": str(path),
        "content": path.read_text(encoding="utf-8"),
    }


def _list_notes():
    _ensure_notes_directory()

    notes = []

    for path in sorted(
        NOTES_DIRECTORY.glob("*.md"),
        key=lambda item: item.name.lower(),
    ):
        stat = path.stat()

        notes.append(
            {
                "note_name": path.stem,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(
                    stat.st_mtime
                ).astimezone().isoformat(),
            }
        )

    return {
        "directory": str(NOTES_DIRECTORY),
        "notes": notes,
        "count": len(notes),
    }


def _delete_note(note_name: str):
    path = _resolve_note_path(note_name)
    path.unlink()

    return {
        "deleted": True,
        "note_name": path.stem,
        "path": str(path),
    }


def _edit_note(
    note_name: str,
    content: str | None = None,
    operation: str = "replace",
    old_text: str | None = None,
    new_text: str | None = None,
):
    path = _resolve_note_path(note_name)
    current_content = path.read_text(encoding="utf-8")

    if operation == "replace":
        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                "For replace, content must contain the complete new note body"
            )

        updated_content = content

    elif operation == "append":
        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                "For append, content must contain the text to append"
            )

        separator = (
            "\n"
            if current_content and not current_content.endswith("\n")
            else ""
        )

        updated_content = f"{current_content}{separator}{content}"

    elif operation == "prepend":
        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                "For prepend, content must contain the text to prepend"
            )

        separator = (
            "\n"
            if current_content and not content.endswith("\n")
            else ""
        )

        updated_content = f"{content}{separator}{current_content}"

    elif operation == "replace_text":
        if not isinstance(old_text, str) or not old_text:
            raise ValueError("For replace_text, old_text is required")

        if not isinstance(new_text, str):
            raise ValueError("For replace_text, new_text is required")

        if old_text not in current_content:
            raise ValueError("old_text was not found in the note")

        updated_content = current_content.replace(old_text, new_text)

    else:
        raise ValueError(
            "operation must be one of: "
            "replace, append, prepend, replace_text"
        )

    path.write_text(updated_content, encoding="utf-8")

    return {
        "edited": True,
        "note_name": path.stem,
        "path": str(path),
        "operation": operation,
        "content": updated_content,
        "characters": len(updated_content),
        "lines": len(updated_content.splitlines()),
    }


def _timer_snapshot(timer_id: str, timer: dict[str, object]):
    end_time = float(timer["end_time"])
    remaining = max(0, end_time - time.time())

    return {
        "timer_id": timer_id,
        "label": str(timer["label"]),
        "duration_seconds": int(timer["duration_seconds"]),
        "remaining_seconds": int(remaining),
        "end_time": datetime.fromtimestamp(end_time).astimezone().isoformat()
    }


def _timer_finished(timer_id: str):
    with _timer_lock:
        timer = _timers.pop(timer_id, None)

    if timer is None:
        return

    label = str(timer["label"])

    try:
        _send_notification("Quince Timer", f"Timer finished: {label}")
    except Exception:
        pass


def _set_timer(duration_seconds: int, label: str = "Timer"):
    if duration_seconds < 1:
        raise ValueError("duration_seconds must be at least 1")

    if duration_seconds > 604800:
        raise ValueError("duration_seconds cannot exceed 604800")

    timer_id = f"timer-{uuid.uuid4().hex[:8]}"
    end_time = time.time() + duration_seconds
    timer = {
        "label": label.strip() or "Timer",
        "duration_seconds": duration_seconds,
        "end_time": end_time,
    }

    timer_thread = threading.Timer(duration_seconds, _timer_finished, args=(timer_id,))
    timer_thread.daemon = True

    with _timer_lock:
        _timers[timer_id] = timer

    timer_thread.start()

    return _timer_snapshot(timer_id, timer)


def _list_timers():
    with _timer_lock:
        snapshots = [
            _timer_snapshot(timer_id, timer)
            for timer_id, timer in _timers.items()
        ]

    snapshots.sort(key=lambda item: item["end_time"])

    return {
        "timers": snapshots,
        "count": len(snapshots)
    }


def _get_timer(timer_id: str):
    with _timer_lock:
        timer = _timers.get(timer_id)

        if timer is None:
            raise KeyError(f"Timer '{timer_id}' does not exist or has already finished")

        return _timer_snapshot(timer_id, timer)


def _cancel_timer(timer_id: str):
    with _timer_lock:
        timer = _timers.pop(timer_id, None)

    if timer is None:
        raise KeyError(f"Timer '{timer_id}' does not exist or has already finished")

    return {
        "cancelled": True,
        "timer_id": timer_id,
        "label": str(timer["label"])
    }
