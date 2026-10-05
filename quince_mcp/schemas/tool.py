from __future__ import annotations
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, Literal


# TODO: Add argument_grammer for stricter argument.
class QuinceTool:
    def __init__(
        self,
        tool_id: str,
        description: str,
        kind: Literal["category","leaf"] = "leaf",
        feedback: str = "",
        handler: Callable[..., Any] | Callable[..., Awaitable[Any]] | None = None,
        arguments: dict[str, dict[str, Any]] = {},
        required_arguments: list[str] = [],
        choice: Literal["none", "auto", "required"] = "required",
        children: list[QuinceTool] | None = None,
        prereq_services: list[tuple[str, dict[str, dict[str, Any]], Callable[..., Any] | Callable[..., Awaitable[Any]]]] = [],
    ) -> None:
        self.name = tool_id.split('.')[-1]
        self.tool_id = tool_id
        self.description = description
        self.feedback = feedback
        self.arguments = arguments
        self.required_arguments = required_arguments
        self.handler = handler
        self.choice = choice
        self.children = children or []
        self.kind = kind
        self.prereq_services = prereq_services or []

    def add_child(self, child: QuinceTool) -> None:
        self.children.append(child)
        if child.tool_id not in ["reset", "terminate"]:
            self.kind = "category"

    def attach_handler(
        self,
        handler: Callable[..., Any] | Callable[..., Awaitable[Any]],
        arguments: dict[str, dict[str, Any]],
        required_arguments: list[str]
    ) -> None:
        self.handler = handler
        self.arguments = arguments
        self.required_arguments = required_arguments

    async def execute(self, arguments: dict[str, Any]) -> Any:
        if self.handler is None:
            raise ValueError("Handler is not attached")

        result = self.handler(**arguments)

        if inspect.isawaitable(result):
            return await result

        return result