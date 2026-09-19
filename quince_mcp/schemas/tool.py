from __future__ import annotations
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, Literal


class Tool:
    def __init__(
        self,
        tool_id: str,
        description: str,
        feedback: str = "",
        handler: Callable[..., Any] | Callable[..., Awaitable[Any]] | None = None,
        arguments_types: dict[str, str] = {},
        choice: Literal["none", "auto", "required"] = "required",
        children: list[Tool] | None = None,
    ) -> None:
        self.tool_id = tool_id
        self.description = description
        self.feedback = feedback
        self.arguments_types = arguments_types
        self.handler = handler
        self.choice = choice
        self.children = children or []
        self.type = "leaf" if not self.children else "category"

    def add_child(self, child: Tool) -> None:
        self.children.append(child)
        self.type = "category"

    def attach_handler(
        self,
        handler: Callable[..., Any] | Callable[..., Awaitable[Any]],
        arguments_types: dict[str, str],
    ) -> None:
        self.handler = handler
        self.arguments_types = arguments_types

    async def execute(self, arguments: dict[str, Any]) -> Any:
        if self.handler is None:
            raise ValueError("Handler is not attached")

        result = self.handler(**arguments)

        if inspect.isawaitable(result):
            return await result

        return result