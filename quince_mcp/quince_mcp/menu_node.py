from __future__ import annotations
from typing import Any, Callable


class MenuNode:
    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        handler: Callable[..., Any] | None = None,
        parameters: dict[str, Any] | None = None,
    ):
        self.id = id
        self.name = name
        self.description = description
        self.handler = handler
        self.parameters = parameters or {
            "type": "object",
            "properties": {},
            "required": [],
        }
        self.children: dict[str, "MenuNode"] = {}
        self.parent: "MenuNode | None" = None

    @property
    def is_leaf(self) -> bool:
        return self.handler is not None

    @property
    def is_branch(self) -> bool:
        return not self.is_leaf

    def add_child(self, node: "MenuNode") -> "MenuNode":
        if self.handler is not None:
            raise ValueError(
                f"'{self.id}' has a handler and can't also have children "
                f"(tried to add '{node.id}') — a node must be either a "
                f"branch or a leaf, not both."
            )
        if node.id in self.children:
            raise ValueError(f"'{self.id}' already has a child with id '{node.id}'")
        node.parent = self
        self.children[node.id] = node
        return node

    def path(self) -> list["MenuNode"]:
        node, chain = self, []
        while node is not None:
            chain.append(node)
            node = node.parent
        return list(reversed(chain))

    def to_tool_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": child.id,
                    "description": child.description,
                    "parameters": child.parameters,
                },
            }
            for child in self.children.values()
        ]