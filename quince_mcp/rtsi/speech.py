"""
Deterministic speech lines lookup for RTSI. No LLM involved.
Maps tool_id / event -> short spoken line (or None for silence).
"""
from __future__ import annotations


def get_speak_line(tool_id: str, args: dict | None = None) -> str | None:
    """Return a short deterministic spoken line, or None for silence."""
    args = args or {}
    suffix = tool_id.split("--")[-1]

    if tool_id == "root--browser":
        return "On it."
    if suffix == "open-tab":
        return "Opening that."
    if suffix == "use-current-tab":
        return "Taking a look at this page."
    if suffix == "navigate":
        if args.get("action") == "goto":
            return "Loading it."
    # Everything else: silence
    return None
