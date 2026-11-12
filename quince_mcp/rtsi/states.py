"""
RTSI states, tool classes, and allowed-tools tables.
All transitions are enforced by the machine, never by the LLM.
"""
from __future__ import annotations

from enum import Enum


class State(str, Enum):
    ENTRY = "ENTRY"
    DECIDE = "DECIDE"
    COMPARE = "COMPARE"
    JUDGE = "JUDGE"
    AWAITING_USER = "AWAITING_USER"
    ENDED = "ENDED"


class ToolClass(str, Enum):
    READ = "READ"
    ACT = "ACT"
    CONTROL = "CONTROL"
    HIDDEN = "HIDDEN"


# Map tool_id suffix -> ToolClass
TOOL_CLASSES: dict[str, ToolClass] = {
    "list-tabs": ToolClass.READ,
    "refresh-page": ToolClass.READ,
    "find-in-page": ToolClass.READ,
    "read-text": ToolClass.READ,

    "open-tab": ToolClass.ACT,
    "use-current-tab": ToolClass.ACT,
    "switch-tab": ToolClass.ACT,
    "close-tab": ToolClass.ACT,
    "navigate": ToolClass.ACT,
    "click": ToolClass.ACT,
    "type-text": ToolClass.ACT,
    "press-key": ToolClass.ACT,
    "scroll": ToolClass.ACT,
    "select-option": ToolClass.ACT,
    "set-checked": ToolClass.ACT,
    "hover": ToolClass.ACT,
    "fill-form": ToolClass.ACT,
    "wait": ToolClass.ACT,

    "record-comparison": ToolClass.CONTROL,
    "continue": ToolClass.CONTROL,
    "successful-termination": ToolClass.CONTROL,
    "unsuccessful-termination": ToolClass.CONTROL,
    "cross-question": ToolClass.CONTROL,
    "provide-answer": ToolClass.HIDDEN,
}

# Tab-selection ACT tools that SKIP Compare/Judge (no meaningful before/after)
TAB_SELECTION_TOOLS = {
    "root--browser--open-tab",
    "root--browser--use-current-tab",
    "root--browser--switch-tab",
    "root--browser--close-tab",
}

# All READ tool ids
READ_TOOL_IDS = {
    f"root--browser--{k}" for k, v in TOOL_CLASSES.items() if v == ToolClass.READ
}

# All ACT tool ids
ACT_TOOL_IDS = {
    f"root--browser--{k}" for k, v in TOOL_CLASSES.items() if v == ToolClass.ACT
}

# Per-state allowed tool-id sets
def allowed_tools(state: State, exits_open: bool = False) -> set[str]:
    if state == State.ENTRY:
        return {
            "root--browser--list-tabs",
            "root--browser--open-tab",
            "root--browser--use-current-tab",
            "root--browser--switch-tab",
        }
    if state == State.DECIDE:
        base = READ_TOOL_IDS | ACT_TOOL_IDS
        if exits_open:
            base = base | {
                "root--browser--successful-termination",
                "root--browser--unsuccessful-termination",
                "root--browser--cross-question",
            }
        return base
    if state == State.COMPARE:
        return {"root--browser--record-comparison"}
    if state == State.JUDGE:
        return {
            "root--browser--continue",
            "root--browser--successful-termination",
            "root--browser--unsuccessful-termination",
            "root--browser--cross-question",
        }
    if state == State.AWAITING_USER:
        return {"root--browser--provide-answer"}
    # ENDED
    return set()


def get_tool_class(tool_id: str) -> ToolClass | None:
    suffix = tool_id.split("--")[-1]
    return TOOL_CLASSES.get(suffix)
