import asyncio
import inspect
from typing import Any

async def execute(handler, arguments: dict[str, Any] | None = None) -> Any:
    if handler is None:
        raise ValueError("Handler is not provided")

    if arguments is not None:
        if inspect.iscoroutinefunction(handler):
            return await handler(**arguments)
        return await asyncio.to_thread(handler, **arguments)

    if inspect.iscoroutinefunction(handler):
        return await handler()

    return await asyncio.to_thread(handler)
