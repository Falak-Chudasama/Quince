from typing import Any
import inspect

async def execute(handler, arguments: dict[str, Any] | None = None) -> Any:
    if handler is None:
        raise ValueError("Handler is not provided")

    if arguments is not None:
        result = handler(**arguments)
    else:
        result = handler()

    if inspect.isawaitable(result):
        return await result

    return result