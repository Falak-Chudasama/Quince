from __future__ import annotations

"""
Terminal presentation for Quince: a startup banner and a single-line
live status indicator that reflects the turn state machine already
owned by QuinceClient (idle / recording / thinking / speaking) plus
the connection state.

This module only renders. It has no opinion about *when* state
changes — callers call `StatusLine.set(...)` whenever client.py's
existing state transitions happen, so the state machine in client.py
remains the single source of truth.

Deliberately dependency-light: if stdout isn't a real terminal (piped
output, some CI runner), rich degrades to plain text automatically —
nothing here needs to special-case that.
"""

import threading
from dataclasses import dataclass

from rich.live import Live
from rich.text import Text

from src.ui.theme import console

_BANNER = r"""
   ____        _
  / __ \ _   _(_)_ __   ___ ___
 / / _` | | | | | '_ \ / __/ _ \
| | (_| | |_| | | | | | (_|  __/
 \_\__, |\__,_|_|_| |_|\___\___|
    __/ |
   |___/
""".strip("\n")

_STATE_GLYPH = {
    "idle": ("●", "state.idle", "idle"),
    "recording": ("●", "state.recording", "listening"),
    "thinking": ("●", "state.thinking", "thinking"),
    "speaking": ("●", "state.speaking", "speaking"),
}

_CONN_GLYPH = {
    "connected": ("state.connected", "connected"),
    "connecting": ("state.connecting", "connecting…"),
    "disconnected": ("state.disconnected", "offline"),
}


def print_banner(*, hotkey: str, ws_url: str, voice: str) -> None:
    """Rendered once at startup. Not part of the live-updating status line."""

    console.print()
    console.print(Text(_BANNER, style="quince.brand"))
    console.print(
        Text("  your voice, on call", style="quince.secondary italic")
    )
    console.print()

    console.print(f"  [quince.dim]hotkey[/]      [bold]{hotkey}[/]  (hold to talk — hold again anytime to interrupt and talk)")
    console.print(f"  [quince.dim]basket[/]      {ws_url}")
    console.print(f"  [quince.dim]voice[/]       {voice}")
    console.print()


@dataclass
class _StatusSnapshot:
    turn: str = "idle"
    connection: str = "connecting"
    detail: str = ""


class StatusLine:
    """
    A single line at the bottom of the terminal that always reflects
    current turn + connection state, redrawn in place rather than
    scrolling the log. Thread-safe: hotkey callbacks and asyncio tasks
    on different threads may update it concurrently.

    Usage:
        status = StatusLine()
        status.start()
        ...
        status.set(turn="recording")
        ...
        status.stop()
    """

    def __init__(self, refresh_per_second: float = 12.0) -> None:
        self._lock = threading.Lock()
        self._snapshot = _StatusSnapshot()
        self._live: Live | None = None
        self._refresh_per_second = refresh_per_second

    # ------------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------------

    def start(self) -> None:
        if self._live is not None:
            return
        self._live = Live(
            self._render(),
            console=console,
            refresh_per_second=self._refresh_per_second,
            transient=False,
        )
        self._live.start()

    def stop(self) -> None:
        if self._live is None:
            return
        try:
            self._live.stop()
        finally:
            self._live = None

    # ------------------------------------------------------------
    # STATE UPDATES
    # ------------------------------------------------------------

    def set(self, *, turn: str | None = None, connection: str | None = None, detail: str | None = None) -> None:
        with self._lock:
            if turn is not None:
                self._snapshot.turn = turn
            if connection is not None:
                self._snapshot.connection = connection
            if detail is not None:
                self._snapshot.detail = detail
            snapshot = _StatusSnapshot(**vars(self._snapshot))

        if self._live is not None:
            self._live.update(self._render(snapshot), refresh=True)

    # ------------------------------------------------------------
    # RENDER
    # ------------------------------------------------------------

    def _render(self, snapshot: _StatusSnapshot | None = None) -> Text:
        snap = snapshot or self._snapshot

        glyph, style, label = _STATE_GLYPH.get(snap.turn, _STATE_GLYPH["idle"])
        conn_style, conn_label = _CONN_GLYPH.get(snap.connection, _CONN_GLYPH["disconnected"])

        line = Text()
        line.append(" " + glyph + " ", style=style)
        line.append(label.ljust(10), style=style)
        line.append("  ")
        line.append("· ", style="quince.muted")
        line.append(conn_label, style=conn_style)

        if snap.detail:
            line.append("   ")
            line.append(snap.detail, style="quince.dim")

        return line
