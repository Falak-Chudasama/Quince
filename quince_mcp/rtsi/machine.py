"""
RtsiMachine — the deterministic RTSI state machine.

Pure with respect to I/O except through the injected `bridge`.
All state transitions are program-enforced; the LLM only chooses menu items.

NEVER writes to stdout.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time
import urllib.parse
from typing import Any, Callable, Coroutine

from quince_mcp.bridge.protocol import BridgeError
from quince_mcp.rtsi.confirm import (
    AMBIGUOUS_RETRY_QUESTION,
    build_confirmation_question,
    parse_yes_no,
)
from quince_mcp.rtsi.prompts import RTSI_MODE_PROMPT
from quince_mcp.rtsi.render import parse_snapshot_refs, render_history, render_state_change
from quince_mcp.rtsi.session import ActionRecord, PendingUser, RtsiSession, SessionManager
from quince_mcp.rtsi.speech import get_speak_line
from quince_mcp.rtsi.states import (
    ACT_TOOL_IDS,
    TAB_SELECTION_TOOLS,
    State,
    ToolClass,
    allowed_tools,
    get_tool_class,
)
from quince_mcp.tools.util import reset_summary, terminate_summary
from quince_mcp.utils.logging_setup import get_logger
from quince_mcp.utils.message import build_message

logger = get_logger("rtsi")


class RtsiMachine:
    """
    Implements the RTSI navigate protocol as a state machine over the existing
    `navigate` tool. All decisions that can be made by program ARE made by program.
    """

    def __init__(self, bridge: Any, settings: Any) -> None:
        self._bridge = bridge
        self._settings = settings
        self._sessions = SessionManager()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def handle(
        self,
        tool_id: str,
        arguments: dict[str, Any],
        describe_root_fn: Callable[[], Coroutine[Any, Any, list[dict[str, Any]]]],
    ) -> dict[str, Any]:
        """
        Handle any root--browser* navigate call.
        Returns a build_message-shaped dict.
        """
        session = self._sessions.get_or_none()

        # Check expiry on every call.
        if session is not None and session.state != State.ENDED:
            expired, reason = session.is_expired(
                self._settings.max_duration_s, self._settings.idle_timeout_s
            )
            if expired:
                await self._end_session(session, reason)
                return build_message(
                    message="Browser control session expired.",
                    success=False,
                    error="session_expired",
                    terminate=True,
                )

        # Entry into the category.
        if tool_id == "root--browser":
            return await self._handle_entry(session, describe_root_fn)

        # If no session is active, any other browser tool is stale.
        if session is None or session.state == State.ENDED:
            return build_message(
                message="No active browser session. Navigate to root--browser to start.",
                success=False,
                error="session_ended",
                terminate=True,
            )

        session.touch()

        # Dispatch by state.
        if session.state == State.AWAITING_USER:
            return await self._handle_awaiting_user(session, tool_id, arguments)

        if session.state == State.ENTRY:
            return await self._handle_entry_tool(session, tool_id, arguments)

        if session.state in (State.DECIDE,):
            return await self._handle_decide(session, tool_id, arguments)

        if session.state == State.COMPARE:
            return await self._handle_compare(session, tool_id, arguments)

        if session.state == State.JUDGE:
            return await self._handle_judge(session, tool_id, arguments)

        return build_message(
            message="Unexpected RTSI state.",
            success=False, error="internal_error", terminate=True,
        )

    async def abort_active_session(self, outcome: str = "aborted") -> None:
        """Called by server.py on reset/terminate to clean up any active session."""
        session = self._sessions.get_or_none()
        if session is not None and session.state != State.ENDED:
            await self._end_session(session, outcome)

    # ------------------------------------------------------------------
    # Entry
    # ------------------------------------------------------------------

    async def _handle_entry(
        self,
        old_session: RtsiSession | None,
        describe_root_fn: Callable,
    ) -> dict[str, Any]:
        """Handle navigate("root--browser") — create session, connect extension."""
        # Check extension connected.
        if not self._bridge.is_connected:
            return build_message(
                message="The browser extension is not connected, so I can't control the browser.",
                success=False,
                error="extension_not_connected",
                terminate=True,
            )

        # End old session if any.
        if old_session is not None:
            await self._end_session(old_session, "superseded")

        session = self._sessions.begin()
        logger.info("RTSI session %s started", session.id)

        # Signal extension.
        try:
            await self._bridge.call("session.begin", {"session_id": session.id}, timeout=5.0)
        except Exception as exc:
            logger.warning("session.begin failed: %s", exc)

        # Get tab list.
        try:
            tabs_result = await self._bridge.call("tabs.list", {}, timeout=20.0)
            tabs = tabs_result.get("tabs", [])[:10]
        except Exception:
            tabs = []

        ext_version = self._bridge.connected_info.get("version", "?")

        entry_children = self._build_children_for_state(session)

        result = {
            "session_id": session.id,
            "tabs": tabs,
            "extension_version": ext_version,
            "hint": "Open a site, or use-current-tab if the user says 'this page'.",
        }

        extra = {
            "rtsi": self._rtsi_meta(session),
            "mode_prompt": RTSI_MODE_PROMPT,
            "speak": get_speak_line("root--browser"),
        }

        return build_message(
            message="Browser control started.",
            result=result,
            children=entry_children + [terminate_summary, reset_summary],
            was_category_call=True,
            terminate=False,
            success=True,
            extra=extra,
        )

    # ------------------------------------------------------------------
    # ENTRY state tools (tab selection before deciding)
    # ------------------------------------------------------------------

    async def _handle_entry_tool(
        self, session: RtsiSession, tool_id: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        allowed = allowed_tools(State.ENTRY)
        if tool_id not in allowed:
            return self._out_of_state(session, tool_id)

        if tool_id == "root--browser--list-tabs":
            return await self._do_list_tabs(session)

        # Tab selection tools from ENTRY
        return await self._do_tab_selection(session, tool_id, arguments, from_entry=True)

    # ------------------------------------------------------------------
    # DECIDE state
    # ------------------------------------------------------------------

    async def _handle_decide(
        self, session: RtsiSession, tool_id: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        allowed = allowed_tools(State.DECIDE, exits_open=session.exits_open)
        if tool_id not in allowed:
            return self._out_of_state(session, tool_id)

        tc = get_tool_class(tool_id)

        if tool_id == "root--browser--list-tabs":
            return await self._do_list_tabs(session)

        if tool_id in TAB_SELECTION_TOOLS or tool_id == "root--browser--close-tab":
            return await self._do_tab_selection(session, tool_id, arguments, from_entry=False)

        if tc == ToolClass.READ:
            return await self._do_read(session, tool_id, arguments)

        if tc == ToolClass.ACT:
            return await self._do_act(session, tool_id, arguments)

        if tool_id in ("root--browser--successful-termination", "root--browser--unsuccessful-termination"):
            return await self._do_termination(session, tool_id, arguments)

        if tool_id == "root--browser--cross-question":
            return await self._do_cross_question(session, arguments)

        return self._out_of_state(session, tool_id)

    # ------------------------------------------------------------------
    # COMPARE state
    # ------------------------------------------------------------------

    async def _handle_compare(
        self, session: RtsiSession, tool_id: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if tool_id != "root--browser--record-comparison":
            return self._out_of_state(session, tool_id)

        comparison = str(arguments.get("comparison", "")).strip()[:280]

        # Record into history.
        last_action = session.last_action
        sc = session.last_state_change or {}
        action_desc = last_action.ref_desc if last_action else ""
        summary_line = sc.get("summary_line", "")
        effect = sc.get("effect", "none")

        session.add_history(action_desc, summary_line, comparison, effect)
        logger.info("RTSI %s COMPARE recorded", session.id)

        # Transition to JUDGE.
        session.state = State.JUDGE
        judge_children = self._build_children_for_state(session)

        sc_text = self._render_sc(sc, action_desc)
        result = {
            "state_change_text": sc_text,
            "comparison_history": render_history(session.history),
            "step": session.step,
            "max_steps": self._settings.max_steps,
        }
        extra = {"rtsi": self._rtsi_meta(session)}
        return build_message(
            message="Comparison recorded. Now judge: continue, terminate, or ask the user.",
            result=result,
            children=judge_children,
            was_category_call=True,
            terminate=False,
            success=True,
            extra=extra,
        )

    # ------------------------------------------------------------------
    # JUDGE state
    # ------------------------------------------------------------------

    async def _handle_judge(
        self, session: RtsiSession, tool_id: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        allowed = allowed_tools(State.JUDGE)
        if tool_id not in allowed:
            return self._out_of_state(session, tool_id)

        if tool_id == "root--browser--continue":
            return await self._do_continue(session)

        if tool_id in ("root--browser--successful-termination", "root--browser--unsuccessful-termination"):
            return await self._do_termination(session, tool_id, arguments)

        if tool_id == "root--browser--cross-question":
            return await self._do_cross_question(session, arguments)

        return self._out_of_state(session, tool_id)

    # ------------------------------------------------------------------
    # AWAITING_USER state
    # ------------------------------------------------------------------

    async def _handle_awaiting_user(
        self, session: RtsiSession, tool_id: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if tool_id != "root--browser--provide-answer":
            return build_message(
                message="Waiting for the user to answer.",
                success=False,
                error="awaiting_user_answer",
                children=[],
                terminate=False,
            )

        if session.pending is None:
            return self._out_of_state(session, tool_id)

        # Check pending expiry.
        if time.time() > session.pending.expires_at:
            session.pending = None
            session.state = State.DECIDE
            session.exits_open = True
            return build_message(
                message="Confirmation expired; treating as no.",
                result={"user_declined": True, "note": "Confirmation timed out; treated as no."},
                children=self._build_children_for_state(session),
                was_category_call=True, terminate=False, success=True,
                extra={"rtsi": self._rtsi_meta(session)},
            )

        pending = session.pending
        answer = str(arguments.get("answer", "")).strip()
        polarity = parse_yes_no(answer)

        if pending.kind == "confirmation":
            return await self._handle_confirmation_answer(session, pending, polarity, answer)
        else:
            return await self._handle_question_answer(session, pending, polarity, answer)

    async def _handle_confirmation_answer(
        self,
        session: RtsiSession,
        pending: PendingUser,
        polarity: str,
        answer: str,
    ) -> dict[str, Any]:
        if polarity == "yes":
            # Re-send the action with confirm_token.
            session.pending = None
            args = dict(pending.arguments)
            args["confirm_token"] = pending.token
            # Re-execute the action.
            return await self._do_act_execute(session, pending.tool_id, args)

        if polarity == "no":
            session.pending = None
            session.state = State.DECIDE
            session.exits_open = True
            action_desc = pending.arguments.get("ref", "action")
            session.add_history(
                f"declined: {pending.tool_id}",
                "User declined the action.",
                None, "none"
            )
            result = {
                "user_declined": True,
                "note": "The user said no. Do not retry that action. Choose a different approach or stop.",
            }
            return build_message(
                message="User declined.",
                result=result,
                children=self._build_children_for_state(session),
                was_category_call=True, terminate=False, success=True,
                extra={"rtsi": self._rtsi_meta(session)},
            )

        # Ambiguous.
        if pending.attempts == 0:
            pending.attempts = 1
            q = AMBIGUOUS_RETRY_QUESTION
            await_user = {"kind": "confirmation", "question": q, "timeout_s": 60}
            return build_message(
                message="Waiting for the user's confirmation.",
                result={"question": q},
                children=[],
                was_category_call=True, terminate=False, success=True,
                extra={
                    "rtsi": self._rtsi_meta(session),
                    "await_user": await_user,
                    "speak": q,
                },
            )
        else:
            # Second ambiguous → treat as no.
            pending.attempts = 2
            return await self._handle_confirmation_answer(session, pending, "no", "")

    async def _handle_question_answer(
        self,
        session: RtsiSession,
        pending: PendingUser,
        polarity: str,
        answer: str,
    ) -> dict[str, Any]:
        # Answer never logged or stored in history.
        session.pending = None

        if not answer:
            session.state = State.DECIDE
            session.exits_open = True
            result = {
                "user_answer": None,
                "note": "The user did not answer.",
            }
        else:
            session.state = State.DECIDE
            session.exits_open = False
            obs = await self._get_observation(session)
            result = {"user_answer": answer}
            if obs is not None:
                result["observation"] = obs
                result["observation_id"] = session.observation_id
                result["observation_meta"] = {}

        return build_message(
            message="User answered.",
            result=result,
            children=self._build_children_for_state(session),
            was_category_call=True, terminate=False, success=True,
            extra={"rtsi": self._rtsi_meta(session), "replaces": "observation"},
        )

    # ------------------------------------------------------------------
    # Individual tool handlers
    # ------------------------------------------------------------------

    async def _do_list_tabs(self, session: RtsiSession) -> dict[str, Any]:
        try:
            result = await self._bridge.call("tabs.list", {}, timeout=20.0)
        except BridgeError as exc:
            return self._bridge_error(session, exc)
        return build_message(
            message="Tab list retrieved.",
            result=result,
            children=self._build_children_for_state(session),
            was_category_call=True, terminate=False, success=True,
            extra={"rtsi": self._rtsi_meta(session)},
        )

    async def _do_tab_selection(
        self, session: RtsiSession, tool_id: str, arguments: dict[str, Any], from_entry: bool
    ) -> dict[str, Any]:
        """Tab-selection actions: always skip Compare/Judge, deliver fresh observation."""
        method_map = {
            "root--browser--open-tab": "tabs.open",
            "root--browser--use-current-tab": "tabs.use_current",
            "root--browser--switch-tab": "tabs.switch",
            "root--browser--close-tab": "tabs.close",
        }
        method = method_map.get(tool_id)
        if method is None:
            return self._out_of_state(session, tool_id)

        params = self._translate_args(tool_id, arguments)
        speak = get_speak_line(tool_id, arguments)

        try:
            tab_result = await self._bridge.call(method, params, timeout=20.0)
        except BridgeError as exc:
            # Error stays in ENTRY if from_entry, else DECIDE(exits_open=True).
            if not from_entry:
                session.state = State.DECIDE
                session.exits_open = True
            return build_message(
                message=f"Tab operation failed: {exc.bridge_message}",
                result={"ok": False, "error": exc.code, "message": exc.bridge_message, "data": exc.data},
                children=self._build_children_for_state(session),
                was_category_call=True, terminate=False, success=True,
                extra={"rtsi": self._rtsi_meta(session)},
            )

        # Update session tab_id.
        new_tab_id = tab_result.get("tab_id")
        if tool_id == "root--browser--close-tab":
            new_tab_id = tab_result.get("next_tab_id")

        session.tab_id = new_tab_id
        session.state = State.DECIDE
        session.exits_open = False

        # Deliver fresh observation.
        obs = await self._get_observation(session) if session.tab_id else None

        result: dict[str, Any] = {**tab_result}
        if obs is not None:
            result["observation"] = obs
            result["observation_id"] = session.observation_id
        elif session.tab_id is None:
            result["note"] = "No tab is controlled now. Open a tab or terminate."

        extra: dict[str, Any] = {"rtsi": self._rtsi_meta(session), "replaces": "observation"}
        if speak:
            extra["speak"] = speak

        return build_message(
            message=f"Tab operation done.",
            result=result,
            children=self._build_children_for_state(session),
            was_category_call=True, terminate=False, success=True,
            extra=extra,
        )

    async def _do_read(
        self, session: RtsiSession, tool_id: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """READ tool: snapshot, find, read-text."""
        if session.tab_id is None:
            return self._no_tab_error(session)

        method_map = {
            "root--browser--refresh-page": "page.snapshot",
            "root--browser--find-in-page": "page.find",
            "root--browser--read-text": "page.read_text",
        }
        method = method_map.get(tool_id)
        if method is None:
            return self._out_of_state(session, tool_id)

        params = {"tab_id": session.tab_id}
        params.update(self._translate_args(tool_id, arguments))

        try:
            read_result = await self._bridge.call(method, params, timeout=8.0)
        except BridgeError as exc:
            session.exits_open = True
            return self._bridge_error(session, exc)

        session.state = State.DECIDE
        session.exits_open = True

        result: dict[str, Any] = {**read_result}

        # refresh-page delivers a new observation.
        if tool_id == "root--browser--refresh-page":
            text = read_result.get("text", "")
            session.ref_desc = parse_snapshot_refs(text)
            session.observation_generation = read_result.get("generation")
            session.observation_id += 1
            result["observation"] = text
            result["observation_id"] = session.observation_id
            extra: dict[str, Any] = {"rtsi": self._rtsi_meta(session), "replaces": "observation"}
        else:
            extra = {"rtsi": self._rtsi_meta(session)}

        return build_message(
            message="Read complete.",
            result=result,
            children=self._build_children_for_state(session),
            was_category_call=True, terminate=False, success=True,
            extra=extra,
        )

    async def _do_act(
        self, session: RtsiSession, tool_id: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Dispatch an ACT tool (non-tab-selection)."""
        if session.tab_id is None:
            return self._no_tab_error(session)

        # Check step cap.
        if session.step >= self._settings.max_steps:
            await self._end_session(session, "step_limit")
            return self._step_limit_response()

        return await self._do_act_execute(session, tool_id, arguments)

    async def _do_act_execute(
        self, session: RtsiSession, tool_id: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute an ACT tool and route through Compare/Judge or adaptive."""
        method_map = {
            "root--browser--navigate": "tabs.navigate",
            "root--browser--click": "act.click",
            "root--browser--type-text": "act.type",
            "root--browser--press-key": "act.press_key",
            "root--browser--scroll": "act.scroll",
            "root--browser--select-option": "act.select",
            "root--browser--set-checked": "act.set_checked",
            "root--browser--hover": "act.hover",
            "root--browser--fill-form": "act.fill_form",
            "root--browser--wait": "act.wait",
        }
        method = method_map.get(tool_id)
        if method is None:
            return self._out_of_state(session, tool_id)

        params = {"tab_id": session.tab_id}
        params.update(self._translate_args(tool_id, arguments))
        if session.observation_generation is not None and "expected_generation" not in params:
            params["expected_generation"] = session.observation_generation

        timeout = 15.0
        if method == "act.wait":
            timeout = float(params.get("seconds", 5)) + 5.0
        elif method in ("tabs.navigate", "tabs.open"):
            timeout = 25.0

        session.step += 1

        # Build action desc for history.
        ref = arguments.get("ref", "")
        ref_name = session.ref_desc.get(ref, ref) if ref else ""
        action_desc = self._build_action_desc(tool_id, arguments, ref_name)

        try:
            act_result = await self._bridge.call(method, params, timeout=timeout)
        except BridgeError as exc:
            session.failure_streak += 1
            if exc.code == "confirmation_required":
                return await self._handle_confirmation_required(session, tool_id, arguments, exc)

            # Error recovery: fresh observation for stale_ref / not_found.
            result: dict[str, Any] = {
                "ok": False,
                "error": exc.code,
                "message": exc.bridge_message,
                "hint": exc.data.get("hint", ""),
                "data": exc.data,
            }
            if exc.code in ("stale_ref", "not_found", "covered_by"):
                obs = await self._get_observation(session)
                if obs:
                    result["observation"] = obs
                    result["observation_id"] = session.observation_id

            # Check failure streak.
            if session.failure_streak >= 5:
                await self._end_session(session, "failure_limit")
                return self._failure_limit_response()

            session.state = State.DECIDE
            session.exits_open = True
            return build_message(
                message=f"Action failed: {exc.bridge_message}",
                result=result,
                children=self._build_children_for_state(session),
                was_category_call=True, terminate=False, success=True,
                extra={"rtsi": self._rtsi_meta(session)},
            )

        session.failure_streak = 0

        sc = act_result.get("state_change") or act_result  # bridge may nest under state_change
        # Update navigation info.
        if sc.get("navigated"):
            obs = await self._get_observation(session)

        # Repeat guard.
        url_path = _url_path(sc.get("after", {}).get("url", ""))
        gen = session.observation_generation or 0
        sig = self._action_signature(tool_id, arguments, url_path, gen)
        if sc.get("no_visible_change"):
            count = session.repeat_counter.get(sig, 0) + 1
            session.repeat_counter[sig] = count
            if count >= 5:
                await self._end_session(session, "repeat_limit")
                return self._repeat_limit_response()
            if count >= 3:
                sc = dict(sc)
                sc["loop_warning"] = (
                    "You repeated the same action and nothing changed. "
                    "Try a different element or approach, or stop."
                )

        # Record action.
        session.last_action = ActionRecord(
            tool_id=tool_id,
            args=arguments,
            ref_desc=action_desc,
            signature=sig,
        )
        session.last_state_change = sc

        # Update observation generation from state change.
        new_gen = sc.get("after", {}).get("generation") or sc.get("generation")
        if new_gen is not None:
            session.observation_generation = new_gen

        # Policy routing.
        sc_text = self._render_sc(sc, action_desc)
        policy = self._settings.judge_policy

        go_adaptive = False
        if policy == "adaptive":
            go_adaptive = self._is_clean_act(sc)

        force_compare_judge = sc.get("loop_warning") is not None

        if go_adaptive and not force_compare_judge:
            # Skip Compare/Judge — go directly to DECIDE with fresh observation.
            session.state = State.DECIDE
            session.exits_open = True
            obs = await self._get_observation(session)
            result = {
                "state_change_text": sc_text,
                "observation": obs,
                "observation_id": session.observation_id,
            }
            return build_message(
                message="Action done.",
                result=result,
                children=self._build_children_for_state(session),
                was_category_call=True, terminate=False, success=True,
                extra={"rtsi": self._rtsi_meta(session), "replaces": "observation"},
            )

        # MERGE_COMPARE_JUDGE mode not fully implemented in this version;
        # always go to COMPARE -> JUDGE.
        session.state = State.COMPARE

        compare_children = self._build_children_for_state(session)
        result = {
            "state_change_text": sc_text,
            "action": action_desc,
            "instruction": "Write one short comparison of what changed (or that nothing changed).",
        }
        return build_message(
            message="Action done. Compare what changed.",
            result=result,
            children=compare_children,
            was_category_call=True, terminate=False, success=True,
            extra={"rtsi": self._rtsi_meta(session)},
        )

    async def _do_continue(self, session: RtsiSession) -> dict[str, Any]:
        """JUDGE → continue → DECIDE with fresh observation."""
        session.state = State.DECIDE
        session.exits_open = False
        obs = await self._get_observation(session)
        result = {
            "observation": obs,
            "observation_id": session.observation_id,
        }
        return build_message(
            message="Continuing. Here is the current page.",
            result=result,
            children=self._build_children_for_state(session),
            was_category_call=True, terminate=False, success=True,
            extra={"rtsi": self._rtsi_meta(session), "replaces": "observation"},
        )

    async def _do_termination(
        self, session: RtsiSession, tool_id: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle successful-termination or unsuccessful-termination."""
        is_success = tool_id == "root--browser--successful-termination"
        summary_key = "result_summary" if is_success else "reason"
        summary = str(arguments.get(summary_key, "")).strip()[:300]

        outcome_status = "success" if is_success else "failed"

        # Get final page info.
        final_url = ""
        final_title = ""
        if session.tab_id is not None:
            try:
                snap = await self._bridge.call(
                    "page.snapshot",
                    {"tab_id": session.tab_id, "scope": "viewport", "max_chars": 500},
                    timeout=5.0,
                )
                meta = snap.get("observation_meta", {})
                final_url = meta.get("url", "")
                final_title = meta.get("title", "")
            except Exception:
                pass

        controlled_tabs = session.tab_id and [session.tab_id] or []
        recent = session.history[-5:] if session.history else []
        rtsi_outcome = {
            "status": outcome_status,
            "summary": summary,
            "steps": session.step,
            "final_url": final_url,
            "final_title": final_title,
            "controlled_tabs": controlled_tabs,
            "recent_comparisons": [
                {"action": h.action, "comparison": h.comparison}
                for h in recent
            ],
        }

        ends_loop = self._settings.termination_ends_loop
        logger.info(
            "RTSI %s %s in %d steps — %s",
            session.id, outcome_status, session.step, summary[:60]
        )

        await self._end_session(session, outcome_status)

        if ends_loop:
            return build_message(
                message=f"Browser task {'done' if is_success else 'stopped'}.",
                result={"rtsi_outcome": rtsi_outcome},
                children=[],
                was_category_call=False, terminate=True, success=True,
                extra={"rtsi_outcome": rtsi_outcome},
            )
        else:
            # Return root menu for multi-task chaining.
            from quince_mcp.tool_tree import root
            from quince_mcp.server import _describe_children
            root_children = await _describe_children(root)
            root_children.append(terminate_summary)
            return build_message(
                message="Browser task finished.",
                result={"rtsi_outcome": rtsi_outcome},
                children=root_children,
                was_category_call=True, terminate=False, success=True,
            )

    async def _do_cross_question(
        self, session: RtsiSession, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Pause and ask the user a question."""
        question = str(arguments.get("question", "")).strip()[:200]
        pending = PendingUser(
            kind="question",
            tool_id="",
            arguments={},
            token="",
            question=question,
            attempts=0,
            expires_at=time.time() + 120,
        )
        session.pending = pending
        session.state = State.AWAITING_USER

        await_user = {"kind": "question", "question": question, "timeout_s": 120}
        extra = {
            "rtsi": self._rtsi_meta(session),
            "await_user": await_user,
            "speak": question,
        }
        return build_message(
            message="Waiting for the user's answer.",
            result={"question": question},
            children=[],
            was_category_call=True, terminate=False, success=True,
            extra=extra,
        )

    async def _handle_confirmation_required(
        self,
        session: RtsiSession,
        tool_id: str,
        arguments: dict[str, Any],
        exc: BridgeError,
    ) -> dict[str, Any]:
        """Risk gate triggered — pause and ask the user."""
        risk_data = exc.data.get("action", {})
        name = risk_data.get("name", arguments.get("ref", "action"))
        host = risk_data.get("host", "this site")
        token = exc.data.get("pending_token", secrets.token_urlsafe(16))

        question = build_confirmation_question(name, host, tool_id)

        pending = PendingUser(
            kind="confirmation",
            tool_id=tool_id,
            arguments=arguments,
            token=token,
            question=question,
            attempts=0,
            expires_at=time.time() + 120,
        )
        session.pending = pending
        session.state = State.AWAITING_USER

        await_user = {"kind": "confirmation", "question": question, "timeout_s": 60}
        extra = {
            "rtsi": self._rtsi_meta(session),
            "await_user": await_user,
            "speak": question,
        }
        return build_message(
            message="Waiting for the user's confirmation.",
            result={"question": question},
            children=[],
            was_category_call=True, terminate=False, success=True,
            extra=extra,
        )

    # ------------------------------------------------------------------
    # Observation delivery
    # ------------------------------------------------------------------

    async def _get_observation(self, session: RtsiSession) -> str | None:
        if session.tab_id is None:
            return None
        try:
            snap = await self._bridge.call(
                "page.snapshot",
                {
                    "tab_id": session.tab_id,
                    "scope": "viewport",
                    "max_chars": self._settings.snapshot_max_chars,
                },
                timeout=8.0,
            )
            text = snap.get("text", "")
            session.ref_desc = parse_snapshot_refs(text)
            session.observation_generation = snap.get("generation")
            session.observation_id += 1
            return text
        except Exception as exc:
            logger.warning("Snapshot failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_children_for_state(self, session: RtsiSession) -> list[dict[str, Any]]:
        """
        Build the children list from the browser tools.py QuinceTool objects
        filtered to the allowed set for the current state.
        """
        from quince_mcp.tools.browser.tools import browser_tool_tree
        state = session.state
        exits = session.exits_open
        allowed = allowed_tools(state, exits_open=exits)

        children = []
        for tid in sorted(allowed):  # stable order
            tool = browser_tool_tree.get(tid)
            if tool is None:
                continue
            if getattr(tool, "hidden", False):
                continue
            children.append({
                "tool_id": tool.tool_id,
                "description": tool.description,
                "feedback": tool.feedback,
                "kind": tool.kind,
                "arguments": tool.arguments,
                "required_arguments": tool.required_arguments,
            })
        return children

    def _rtsi_meta(self, session: RtsiSession) -> dict[str, Any]:
        max_steps = self._settings.max_steps
        max_hops = max_steps * 3 + 10
        return {
            "session_id": session.id,
            "state": session.state.value,
            "step": session.step,
            "max_steps": max_steps,
            "max_hops": max_hops,
            "observation_id": session.observation_id,
        }

    def _out_of_state(self, session: RtsiSession, tool_id: str) -> dict[str, Any]:
        session.bad_call_counter = getattr(session, "bad_call_counter", 0) + 1
        if session.bad_call_counter >= 3:
            # Force unsuccessful termination.
            session.state = State.ENDED
            session.outcome = "repeated_invalid"
            import asyncio
            asyncio.ensure_future(self._end_session(session, "repeated_invalid"))
            return build_message(
                message="Repeated invalid choices ended the browser task.",
                result={"rtsi_outcome": {"status": "failed", "summary": "Repeated invalid menu choices.", "steps": session.step}},
                children=[terminate_summary, reset_summary],
                was_category_call=True, terminate=False, success=True,
            )
        return build_message(
            message="That option is not available right now. Pick one of the listed options.",
            result={"error": "not_allowed_in_state", "state": session.state.value, "tool_id": tool_id},
            children=self._build_children_for_state(session),
            was_category_call=True, terminate=False, success=True,
            extra={"rtsi": self._rtsi_meta(session)},
        )

    def _bridge_error(self, session: RtsiSession, exc: BridgeError) -> dict[str, Any]:
        return build_message(
            message=exc.bridge_message or exc.code,
            result={"ok": False, "error": exc.code, "message": exc.bridge_message},
            children=self._build_children_for_state(session),
            was_category_call=True, terminate=False, success=True,
            extra={"rtsi": self._rtsi_meta(session)},
        )

    def _no_tab_error(self, session: RtsiSession) -> dict[str, Any]:
        session.state = State.DECIDE
        session.exits_open = True
        return build_message(
            message="No tab is currently controlled. Open a tab first.",
            result={"ok": False, "error": "tab_not_controlled", "message": "Open a tab first."},
            children=self._build_children_for_state(session),
            was_category_call=True, terminate=False, success=True,
            extra={"rtsi": self._rtsi_meta(session)},
        )

    def _render_sc(self, sc: dict[str, Any], action_desc: str) -> str:
        raw = self._settings.return_raw_state_change
        return render_state_change(sc, action_desc=action_desc, ref_desc=session_ref_desc_noop(), raw=raw)

    def _build_action_desc(
        self, tool_id: str, arguments: dict[str, Any], ref_name: str
    ) -> str:
        suffix = tool_id.split("--")[-1]
        ref = arguments.get("ref", "")
        if ref and ref_name:
            ref_part = f"[{ref}] {ref_name}"
        elif ref:
            ref_part = f"[{ref}]"
        else:
            ref_part = ""

        if suffix == "click":
            ct = arguments.get("click_type", "single")
            return f"{ct} click {ref_part}".strip()
        if suffix == "type-text":
            return f"type into {ref_part}".strip()
        if suffix == "press-key":
            return f"press {arguments.get('key','')} {ref_part}".strip()
        if suffix == "scroll":
            return f"scroll {arguments.get('direction','')} {ref_part}".strip()
        if suffix == "select-option":
            return f"select \"{arguments.get('option','')}\" in {ref_part}".strip()
        if suffix == "set-checked":
            return f"set {ref_part} {'on' if arguments.get('checked') else 'off'}".strip()
        if suffix == "hover":
            return f"hover {ref_part}".strip()
        if suffix == "fill-form":
            return f"fill form ({len(arguments.get('refs',[]))} fields)"
        if suffix == "navigate":
            return f"navigate {arguments.get('action','')} {arguments.get('url','')[:60]}".strip()
        if suffix == "wait":
            return f"wait {arguments.get('seconds','')}s"
        return suffix

    def _translate_args(self, tool_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Map MCP tool arguments to bridge protocol params."""
        suffix = tool_id.split("--")[-1]
        out = {}
        if suffix == "open-tab":
            out["url"] = arguments.get("url", "")
            if "active" in arguments:
                out["active"] = arguments["active"]
        elif suffix == "switch-tab":
            out["tab_id"] = arguments.get("tab_id")
        elif suffix == "close-tab":
            out["tab_id"] = arguments.get("tab_id")
        elif suffix == "navigate":
            out["action"] = arguments.get("action", "reload")
            if arguments.get("url"):
                out["url"] = arguments["url"]
        elif suffix == "refresh-page":
            out["scope"] = arguments.get("scope", "viewport")
            out["max_chars"] = self._settings.snapshot_max_chars
        elif suffix == "find-in-page":
            out["query"] = arguments.get("query", "")
            if arguments.get("max_results"):
                out["max_results"] = arguments["max_results"]
        elif suffix == "read-text":
            if arguments.get("ref"):
                out["ref"] = arguments["ref"]
            out["max_chars"] = arguments.get("max_chars", 4000)
        elif suffix == "click":
            out["ref"] = arguments.get("ref", "")
            if arguments.get("click_type"):
                out["click_type"] = arguments["click_type"]
            if arguments.get("confirm_token"):
                out["confirm_token"] = arguments["confirm_token"]
        elif suffix == "type-text":
            out["ref"] = arguments.get("ref", "")
            out["text"] = arguments.get("text", "")
            out["clear_first"] = arguments.get("clear_first", True)
            out["press_enter"] = arguments.get("press_enter", False)
            if arguments.get("confirm_token"):
                out["confirm_token"] = arguments["confirm_token"]
        elif suffix == "press-key":
            out["key"] = arguments.get("key", "")
            if arguments.get("ref"):
                out["ref"] = arguments["ref"]
            if arguments.get("confirm_token"):
                out["confirm_token"] = arguments["confirm_token"]
        elif suffix == "scroll":
            out["direction"] = arguments.get("direction", "down")
            if arguments.get("ref"):
                out["ref"] = arguments["ref"]
        elif suffix == "select-option":
            out["ref"] = arguments.get("ref", "")
            out["option"] = arguments.get("option", "")
        elif suffix == "set-checked":
            out["ref"] = arguments.get("ref", "")
            out["checked"] = arguments.get("checked", False)
            if arguments.get("confirm_token"):
                out["confirm_token"] = arguments["confirm_token"]
        elif suffix == "hover":
            out["ref"] = arguments.get("ref", "")
        elif suffix == "fill-form":
            out["refs"] = arguments.get("refs", [])
            out["values"] = arguments.get("values", [])
        elif suffix == "wait":
            out["seconds"] = arguments.get("seconds", 3)
        return out

    def _action_signature(
        self,
        tool_id: str,
        arguments: dict[str, Any],
        url_path: str,
        generation: int,
    ) -> str:
        norm = json.dumps(
            {k: v for k, v in sorted(arguments.items()) if k not in ("confirm_token", "expected_generation")},
            sort_keys=True,
        )
        raw = f"{tool_id}|{norm}|{url_path}|{generation}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _is_clean_act(self, sc: dict[str, Any]) -> bool:
        """True if the state change is clean (adaptive policy skip condition)."""
        if not sc.get("ok", True):
            return False
        effect = sc.get("effect", "none")
        if effect not in ("dom_changed", "value_set", "navigated", "none"):
            return False
        if effect == "navigated":
            # Only clean for same-origin navigation.
            before_url = sc.get("before", {}).get("url", "")
            after_url = sc.get("after", {}).get("url", "")
            if _origin(before_url) != _origin(after_url):
                return False
        if sc.get("validation_errors"):
            return False
        if sc.get("dialog", {}).get("script_dialog"):
            return False
        if sc.get("no_visible_change"):
            return False
        if sc.get("wait", {}).get("timed_out"):
            return False
        if sc.get("new_tabs"):
            return False
        if sc.get("loop_warning"):
            return False
        return True

    async def _end_session(self, session: RtsiSession, outcome: str) -> None:
        """End the session and call session.end on the extension (best effort)."""
        self._sessions.end(outcome)
        session.state = State.ENDED
        session.outcome = outcome
        try:
            await self._bridge.call(
                "session.end",
                {"session_id": session.id, "outcome": outcome},
                timeout=2.0,
            )
        except Exception:
            pass
        logger.info("RTSI session %s ended: %s", session.id, outcome)

    def _step_limit_response(self) -> dict[str, Any]:
        return build_message(
            message="I hit my step limit before finishing.",
            result={"rtsi_outcome": {"status": "failed", "summary": "I hit my step limit before finishing.", "steps": self._settings.max_steps}},
            children=[terminate_summary, reset_summary],
            was_category_call=True, terminate=False, success=True,
        )

    def _failure_limit_response(self) -> dict[str, Any]:
        return build_message(
            message="Too many consecutive errors; browser task stopped.",
            result={"rtsi_outcome": {"status": "failed", "summary": "Too many consecutive errors.", "steps": 0}},
            children=[terminate_summary, reset_summary],
            was_category_call=True, terminate=False, success=True,
        )

    def _repeat_limit_response(self) -> dict[str, Any]:
        return build_message(
            message="Repeated the same action too many times; browser task stopped.",
            result={"rtsi_outcome": {"status": "failed", "summary": "Repeated the same action 5 times with no effect.", "steps": 0}},
            children=[terminate_summary, reset_summary],
            was_category_call=True, terminate=False, success=True,
        )


def session_ref_desc_noop() -> dict[str, str]:
    return {}


def _url_path(url: str) -> str:
    try:
        p = urllib.parse.urlparse(url)
        return p.path
    except Exception:
        return url


def _origin(url: str) -> str:
    try:
        p = urllib.parse.urlparse(url)
        return f"{p.scheme}://{p.netloc}"
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_machine: RtsiMachine | None = None
_machine_lock = __import__("threading").Lock()


def get_rtsi_machine() -> RtsiMachine:
    global _machine
    with _machine_lock:
        if _machine is None:
            from quince_mcp.bridge.server import start_bridge

            b = start_bridge()

            from quince_mcp.bridge.config import BridgeSettings

            try:
                settings = BridgeSettings.from_env()
            except Exception:
                settings = BridgeSettings()

            _machine = RtsiMachine(bridge=b, settings=settings)
    return _machine
