"""
RTSI Session dataclass and SessionManager.

Session state lives in memory only — never persisted to disk.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from quince_mcp.rtsi.states import State


@dataclass
class ActionRecord:
    tool_id: str
    args: dict[str, Any]
    ref_desc: str      # program-built string e.g. 'click [e14] button "Send"'
    signature: str     # (tool_id, normalized_args, url_path, generation) hash


@dataclass
class HistoryItem:
    step: int
    action: str           # program-built e.g. 'click [e14] button "Send"'
    summary_line: str     # from state_change.summary_line
    comparison: str | None  # LLM-produced text (or None for READ/tab ops)
    effect: str           # from state_change.effect


@dataclass
class PendingUser:
    kind: str             # "confirmation" | "question"
    tool_id: str          # the action to re-execute on yes (confirmation only)
    arguments: dict[str, Any]
    token: str            # one-shot confirmation token (confirmation only)
    question: str         # the spoken question
    attempts: int
    expires_at: float


@dataclass
class RtsiSession:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: State = State.ENTRY
    exits_open: bool = False
    tab_id: int | None = None
    observation_id: int = 0
    observation_generation: int | None = None
    ref_desc: dict[str, str] = field(default_factory=dict)   # ref -> 'role "name"'
    step: int = 0
    failure_streak: int = 0
    bad_call_counter: int = 0
    history: list[HistoryItem] = field(default_factory=list)
    last_state_change: dict[str, Any] | None = None
    last_action: ActionRecord | None = None
    pending: PendingUser | None = None
    repeat_counter: dict[str, int] = field(default_factory=dict)  # sig -> count
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    outcome: str | None = None

    def touch(self) -> None:
        self.last_activity = time.time()

    def is_expired(self, max_duration_s: int, idle_timeout_s: int) -> tuple[bool, str]:
        now = time.time()
        if now - self.started_at > max_duration_s:
            return True, "duration_limit"
        if now - self.last_activity > idle_timeout_s:
            return True, "expired"
        return False, ""

    def add_history(
        self,
        action: str,
        summary_line: str,
        comparison: str | None,
        effect: str,
    ) -> None:
        self.history.append(HistoryItem(
            step=self.step,
            action=action,
            summary_line=summary_line,
            comparison=comparison,
            effect=effect,
        ))


class SessionManager:
    """
    Holds at most one active RTSI session at a time.
    Thread-safe only for single-threaded asyncio use (no explicit lock needed
    since all MCP calls go through the same asyncio loop).
    """

    def __init__(self) -> None:
        self._session: RtsiSession | None = None

    @property
    def active(self) -> RtsiSession | None:
        return self._session

    def begin(self) -> RtsiSession:
        """Start a new session, ending any existing one."""
        if self._session is not None:
            self._session.outcome = "superseded"
        session = RtsiSession()
        self._session = session
        return session

    def end(self, outcome: str = "ended") -> RtsiSession | None:
        session = self._session
        if session is not None:
            session.outcome = outcome
            self._session = None
        return session

    def get_or_none(self) -> RtsiSession | None:
        return self._session
