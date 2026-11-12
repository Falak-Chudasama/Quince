from typing import Any


def build_message(
    message: str = "no message",
    result: Any | None = None,
    children: list[Any] | None = None,
    was_category_call: bool = True,
    terminate: bool = False,
    success: bool = True,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build the standard Quince navigate response envelope.

    All existing callers (no extra) receive byte-identical output.
    New RTSI callers may pass extra={...} to merge additional top-level keys
    (e.g. rtsi, await_user, mode_prompt, speak, replaces).
    """
    base: dict[str, Any] = {
        "message": message,
        "result": result,
        "children": children or [],
        "was_category_call": was_category_call,
        "terminate": terminate,
        "success": success,
        "error": error,
    }
    if extra:
        base.update(extra)
    return base
