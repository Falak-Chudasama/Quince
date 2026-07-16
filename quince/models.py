from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal

ToolName = Literal[
    "browser.open_url",
    "browser.search",
    "browser.click_text",
    "browser.click_selector",
    "browser.find_text",
    "browser.type",
    "browser.press",
    "browser.scroll",
    "browser.wait",
    "browser.snapshot",
    "browser.back",
    "browser.forward",
    "browser.new_tab",
    "browser.close_tab",
    "browser.switch_tab",
    "browser.list_tabs",
    "native.open_app",
    "native.focus_window",
    "native.inspect_window",
    "native.list_windows",
    "native.click",
    "native.double_click",
    "native.right_click",
    "native.type",
    "native.paste",
    "native.hotkey",
    "native.press",
    "native.scroll",
    "native.wait",
    "native.screenshot",
    "shell.run",
    "decision.ask_user",
]

@dataclass
class Step:
    id: str
    tool: ToolName
    args: Dict[str, Any] = field(default_factory=dict)
    why: str = ""
    success_criteria: str = ""

@dataclass
class Plan:
    mode: str
    task_summary: str
    risk_level: str = "low"
    needs_user_confirmation: bool = False
    clarification_question: Optional[str] = None
    follow_up_question: Optional[str] = None
    final_message: Optional[str] = None
    steps: List[Step] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Plan":
        steps = [Step(**step) for step in data.get("steps", [])]
        return cls(
            mode=data.get("mode", "plan"),
            task_summary=data.get("task_summary", ""),
            risk_level=data.get("risk_level", "low"),
            needs_user_confirmation=bool(data.get("needs_user_confirmation", False)),
            clarification_question=data.get("clarification_question"),
            follow_up_question=data.get("follow_up_question"),
            final_message=data.get("final_message"),
            steps=steps,
        )
