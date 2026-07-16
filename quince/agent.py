from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, Optional

from .browser import BrowserController
from .config import Settings
from .llm import LLMClient
from .native import NativeController
from .perception import ScreenState, capture_screen, try_ocr
from .models import Plan, Step

RISKY_KEYWORDS = {"send", "submit", "buy", "pay", "delete", "overwrite", "publish", "share", "install", "remove", "lock", "logout"}

class QuinceAgent:
    def __init__(self, settings: Settings, preferences_text: str):
        self.settings = settings
        self.llm = LLMClient(settings.groq_api_key, settings.groq_model, preferences_text)
        self.browser = BrowserController(settings.browser_profile_dir, settings.browser_start_url, settings.browser_channel, settings.chromium_sandbox)
        self.native = NativeController()
        self.task_history: list[dict[str, Any]] = []

    def start(self) -> None:
        self.browser.launch()

    def reload_preferences(self, preferences_text: str) -> None:
        self.llm = LLMClient(self.settings.groq_api_key, self.settings.groq_model, preferences_text)

    def stop(self) -> None:
        try:
            self.browser.close()
        except Exception:
            pass

    def _current_context(self) -> ScreenState:
        screen = capture_screen(self.settings.screenshot_dir, prefix="quince")
        if self.settings.use_ocr and screen.screenshot_path:
            screen.ocr_text = try_ocr(screen.screenshot_path)
        try:
            screen.browser_state = self.browser.snapshot()
        except Exception:
            screen.browser_state = {}
        try:
            native_state = {"windows": self.native.list_windows()[:20]}
            if native_state["windows"]:
                native_state["focused"] = native_state["windows"][0]
            screen.native_state = native_state
        except Exception:
            screen.native_state = {}
        return screen

    def _should_force_confirmation(self, task: str, plan: Plan) -> bool:
        text = task.lower()
        if not self.settings.confirm_risky_actions:
            return False
        return any(word in text for word in RISKY_KEYWORDS) or bool(getattr(plan, "needs_user_confirmation", False))

    def plan_task(self, task: str, context_override: Optional[str] = None) -> Plan:
        screen = self._current_context()
        context = context_override or screen.to_context()
        plan = self.llm.plan(task, context, screenshot_b64=screen.screenshot_b64)
        return plan if isinstance(plan, Plan) else Plan.from_dict(plan)

    def _execute_step(self, step: Step) -> Dict[str, Any]:
        tool = step.tool
        args = step.args or {}

        if tool == "browser.open_url":
            return self.browser.open_url(args["url"])
        if tool == "browser.search":
            return self.browser.search(args["query"])
        if tool == "browser.click_text":
            return self.browser.click_text(args["text"])
        if tool == "browser.click_selector":
            return self.browser.click_selector(args["selector"])
        if tool == "browser.find_text":
            return self.browser.find_text(args["text"])
        if tool == "browser.type":
            return self.browser.type(
                text=args["text"],
                selector=args.get("selector", "body"),
                clear=bool(args.get("clear", False)),
                press_enter=bool(args.get("press_enter", False)),
            )
        if tool == "browser.press":
            return self.browser.press(args["keys"])
        if tool == "browser.scroll":
            return self.browser.scroll(int(args.get("delta_y", 800)))
        if tool == "browser.wait":
            return self.browser.wait(float(args.get("seconds", 1.0)))
        if tool == "browser.snapshot":
            return self.browser.snapshot()
        if tool == "browser.back":
            return self.browser.back()
        if tool == "browser.forward":
            return self.browser.forward()
        if tool == "browser.new_tab":
            return self.browser.new_tab(args.get("url", "about:blank"))
        if tool == "browser.close_tab":
            return self.browser.close_tab(int(args.get("index", -1)))
        if tool == "browser.switch_tab":
            return self.browser.switch_tab(int(args["index"]))
        if tool == "browser.list_tabs":
            return self.browser.list_tabs()

        if tool == "native.open_app":
            return self.native.open_app(args["app_name"])
        if tool == "native.focus_window":
            return self.native.focus_window(args["title_hint"])
        if tool == "native.inspect_window":
            return self.native.inspect_window(args["title_hint"])
        if tool == "native.click":
            return self.native.click(int(args["x"]), int(args["y"]), args.get("button", "left"))
        if tool == "native.double_click":
            return self.native.double_click(int(args["x"]), int(args["y"]))
        if tool == "native.right_click":
            return self.native.right_click(int(args["x"]), int(args["y"]))
        if tool == "native.type":
            return self.native.type(args["text"], float(args.get("interval", 0.01)))
        if tool == "native.paste":
            return self.native.paste(args["text"])
        if tool == "native.hotkey":
            return self.native.hotkey(list(args.get("keys", [])))
        if tool == "native.press":
            return self.native.press(args["keys"])
        if tool == "native.scroll":
            return self.native.scroll(int(args.get("amount", -800)))
        if tool == "native.wait":
            return self.native.wait(float(args.get("seconds", 1.0)))
        if tool == "native.screenshot":
            return self.native.screenshot()
        if tool == "native.list_windows":
            return {"windows": self.native.list_windows()}

        if tool == "shell.run":
            cmd = args["command"]
            completed = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return {
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            }
        if tool == "decision.ask_user":
            return {"asked": args.get("question", "Need user input.")}
        raise RuntimeError(f"Unsupported tool: {tool}")

    def run(self, task: str) -> str:
        screen = self._current_context()
        context = screen.to_context()
        plan = self.llm.plan(task, context, screenshot_b64=screen.screenshot_b64)
        plan = plan if isinstance(plan, Plan) else Plan.from_dict(plan)

        if plan.mode == "final":
            return plan.final_message or "Done."

        if plan.mode == "clarify":
            return plan.clarification_question or "I need one clarification before acting."

        if self._should_force_confirmation(task, plan):
            if not plan.follow_up_question:
                plan.follow_up_question = "I have drafted the task. Confirm the final irreversible step?"
            if plan.needs_user_confirmation:
                return plan.follow_up_question

        result_notes = []
        steps = plan.steps[: self.settings.max_steps_per_task]

        for idx, step in enumerate(steps, start=1):
            try:
                outcome = self._execute_step(step)
                after = self._current_context()
                result_notes.append(
                    f"[{idx}] {step.id} {step.tool}: OK\nWHY: {step.why}\nOUTCOME: {json.dumps(outcome, ensure_ascii=False)[:1500]}\nAFTER: {after.active_window or after.browser_state.get('title','')}"
                )
            except Exception as exc:
                failure = f"Step {step.id} ({step.tool}) failed: {exc}"
                result_notes.append(failure)
                revised = self.llm.revise(task, context + "\n\n" + "\n".join(result_notes), failure, screenshot_b64=self._current_context().screenshot_b64)
                if isinstance(revised, Plan):
                    if revised.mode == "clarify" and revised.clarification_question:
                        return revised.clarification_question
                    extra_steps = [s.__dict__ for s in revised.steps]
                else:
                    if revised.get("mode") == "clarify" and revised.get("clarification_question"):
                        return revised["clarification_question"]
                    extra_steps = revised.get("steps", [])
                for extra in extra_steps:
                    if len(result_notes) >= self.settings.max_steps_per_task:
                        break
                    extra_step = Step(**extra)
                    try:
                        outcome = self._execute_step(extra_step)
                        result_notes.append(
                            f"[recovery] {extra_step.id} {extra_step.tool}: OK\nOUTCOME: {json.dumps(outcome, ensure_ascii=False)[:1500]}"
                        )
                    except Exception as exc2:
                        result_notes.append(f"[recovery failed] {extra_step.id}: {exc2}")
                break

        final_summary = "\n".join(result_notes) if result_notes else "No steps were executed."
        final_text = self.llm.final_response(task, context, final_summary, screenshot_b64=self._current_context().screenshot_b64)

        if plan.follow_up_question:
            if final_text:
                return f"{final_text}\n\n{plan.follow_up_question}"
            return plan.follow_up_question

        return final_text or "Done."
