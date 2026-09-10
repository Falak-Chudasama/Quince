from __future__ import annotations

from typing import Any

from quince_mcp.basket_api import BasketAPI
from quince_mcp.menu_node import MenuNode


def build_quince_root(api: BasketAPI) -> MenuNode:
    quince = MenuNode(
        "quince",
        "Quince",
        "Manage Quince memory and commands.",
    )

    memory = quince.add_child(MenuNode(
        "long_term_memory",
        "Long Term Memory",
        "Store or search durable Quince memories.",
    ))
    memory.add_child(MenuNode(
        "store",
        "Store Memory",
        "Save a durable memory.",
        handler=api.memory_store,
        parameters={
            "type": "object",
            "properties": {
                "document": {"type": "string"},
                "source": {"type": "string"},
            },
            "required": ["document"],
        },
    ))
    memory.add_child(MenuNode(
        "search",
        "Search Memory",
        "Search durable Quince memories.",
        handler=api.memory_search,
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "n_result": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["query"],
        },
    ))

    commands = quince.add_child(MenuNode(
        "command_management",
        "Command Management",
        "Add, list, or delete Quince commands.",
    ))
    commands.add_child(MenuNode(
        "add",
        "Add Command",
        "Add a Quince command.",
        handler=api.command_add,
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "is_temporary": {"type": "boolean"},
            },
            "required": ["command"],
        },
    ))
    commands.add_child(MenuNode(
        "list",
        "List Commands",
        "List saved Quince commands.",
        handler=api.command_list,
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ))
    commands.add_child(MenuNode(
        "delete",
        "Delete Command",
        "Delete a saved Quince command.",
        handler=api.command_delete,
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
            },
            "required": ["command"],
        },
    ))

    return quince
