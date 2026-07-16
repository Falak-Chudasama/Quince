from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from groq import Groq

from .prompts import build_system_prompt
from .models import Plan

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "mode": {"type": "string", "enum": ["plan", "clarify", "execute", "final"]},
        "task_summary": {"type": "string"},
        "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
        "needs_user_confirmation": {"type": "boolean"},
        "clarification_question": {"type": ["string", "null"]},
        "follow_up_question": {"type": ["string", "null"]},
        "final_message": {"type": ["string", "null"]},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "tool": {
                        "type": "string",
                        "enum": [
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
                        ],
                    },
                    "args": {"type": "object"},
                    "why": {"type": "string"},
                    "success_criteria": {"type": "string"},
                },
                "required": ["id", "tool", "args", "why", "success_criteria"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["mode", "task_summary", "risk_level", "needs_user_confirmation", "clarification_question", "follow_up_question", "final_message", "steps"],
    "additionalProperties": False,
}

def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()

def _extract_json(text: str) -> str:
    text = _strip_code_fences(text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text

class LLMClient:
    def __init__(self, api_key: str, model: str, preferences_text: str):
        self.client = Groq(api_key=api_key)
        self.model = model
        self.system_prompt = build_system_prompt(preferences_text)

    def _user_content(self, task: str, context: str) -> str:
        return (
            f"TASK:\n{task}\n\n"
            f"CONTEXT:\n{context}\n\n"
            "Return only a single JSON object that follows the schema."
        )

    def _create_json(self, messages: list) -> Dict[str, Any]:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_completion_tokens": 1200,
        }
        # Prefer structured outputs when the model supports it.
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "quince_plan",
                "strict": False,
                "schema": PLAN_SCHEMA,
            },
        }
        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception:
            kwargs["response_format"] = {"type": "json_object"}
            response = self.client.chat.completions.create(**kwargs)

        raw = (response.choices[0].message.content or "").strip()
        if not raw:
            raise RuntimeError("Model returned empty content.")
        raw = _extract_json(raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Model returned invalid JSON: {raw[:500]}") from exc

    def plan(self, task: str, context: str, screenshot_b64: Optional[str] = None) -> Plan:
        # The Groq Chat Completions endpoint currently expects text messages here.
        # We keep the signature for compatibility, but fold screen evidence into text context.
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self._user_content(task, context)},
        ]
        return Plan.from_dict(self._create_json(messages))

    def revise(self, task: str, context: str, failure_note: str, screenshot_b64: Optional[str] = None) -> Plan:
        prompt = f"""The previous step failed or became ambiguous.

FAILURE NOTE:
{failure_note}

Return a revised JSON plan with only the next best steps.
"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self._user_content(task + "\n\n" + prompt, context)},
        ]
        return Plan.from_dict(self._create_json(messages))

    def final_response(self, task: str, context: str, result_summary: str, screenshot_b64: Optional[str] = None) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self._user_content(
                f"{task}\n\nTask result:\n{result_summary}\n\nProvide the terminal-facing final response and, if useful, a single follow-up question.",
                context,
            )},
        ]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_completion_tokens=300,
        )
        return (response.choices[0].message.content or "").strip()
