from typing import Any

def build_message(
    message: str = "no message",
    result: Any | None = None,
    children: list[Any] | None = None,
    was_category_call: bool = True,
    terminate: bool = False,
    success: bool = True,
    error: str | None = None,
):
    return {
        "message": message,
        "result": result,
        "children": children or [],
        "was_category_call": was_category_call,
        "terminate": terminate,
        "success": success,
        "error": error
    }
