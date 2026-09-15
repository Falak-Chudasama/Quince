from __future__ import annotations

import colorsys
import math
import threading
from dataclasses import dataclass

from rich.text import Text

from src.ui.theme import console


_STOPS: list[tuple[float, tuple[float, float, float]]] = [
    (0.0, (0xF9 / 255, 0x76 / 255, 0x8C / 255)),
    (0.5, (0xFF / 255, 0xD7 / 255, 0x1C / 255)),
    (0.9, (0x80 / 255, 0xA3 / 255, 0x2C / 255)),
    (1.0, (0xF9 / 255, 0x76 / 255, 0x8C / 255)),
]

_BANNER_LINES = [
    "  ___        _",
    " / _ \\ _   _(_)_ __   ___ ___",
    "| | | | | | | | '_ \\ / __/ _ \\",
    "| |_| | |_| | | | | | (_|  __/",
    " \\__\\_\\\\__,_|_|_| |_|\\___\\___|",
]

_BANNER_WIDTH = max(len(line) for line in _BANNER_LINES)

_BANNER_INFO: dict[str, str] = {
    "hotkey": "",
    "ws_url": "",
    "voice": "",
}

_BANNER_RENDERED = False


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _sample_stops(t: float) -> tuple[float, float, float]:
    t %= 1.0

    for index in range(len(_STOPS) - 1):
        start_pos, start_rgb = _STOPS[index]
        end_pos, end_rgb = _STOPS[index + 1]

        if start_pos <= t <= end_pos:
            span = end_pos - start_pos
            local_t = 0.0 if span == 0 else (t - start_pos) / span

            return (
                _lerp(start_rgb[0], end_rgb[0], local_t),
                _lerp(start_rgb[1], end_rgb[1], local_t),
                _lerp(start_rgb[2], end_rgb[2], local_t),
            )

    return _STOPS[-1][1]


def sample_hex(
    t: float,
    *,
    brightness: float = 1.0,
) -> str:
    r, g, b = _sample_stops(t)

    if brightness != 1.0:
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        l = max(0.0, min(1.0, l * brightness))
        r, g, b = colorsys.hls_to_rgb(h, l, s)

    return (
        f"#{round(r * 255):02x}"
        f"{round(g * 255):02x}"
        f"{round(b * 255):02x}"
    )


def breathe(phase: float) -> float:
    return 0.5 - 0.5 * math.cos(
        2 * math.pi * (phase % 1.0)
    )


def _gradient_banner(
    *,
    phase: float,
    brightness: float = 1.0,
) -> Text:
    art = Text()
    row_count = len(_BANNER_LINES)

    for row, line in enumerate(_BANNER_LINES):
        for col, character in enumerate(line):
            if character == " ":
                art.append(" ")
                continue

            position = (
                (col / _BANNER_WIDTH) * 0.75
                + (row / max(row_count - 1, 1)) * 0.25
            )

            art.append(
                character,
                style=sample_hex(
                    position + phase,
                    brightness=brightness,
                ),
            )

        if row != row_count - 1:
            art.append("\n")

    return art


def _banner_details() -> None:
    console.print(
        Text(
            "  local, voice-to-voice, always listening for you",
            style="quince.secondary italic",
        )
    )

    console.print()

    console.print(
        f"  [quince.dim]hotkey[/]      "
        f"[bold]{_BANNER_INFO['hotkey']}[/]  "
        "(hold to talk — hold again anytime to interrupt and talk)"
    )

    console.print(
        f"  [quince.dim]basket[/]      "
        f"{_BANNER_INFO['ws_url']}"
    )

    console.print(
        f"  [quince.dim]voice[/]       "
        f"{_BANNER_INFO['voice']}"
    )

    console.print()


def print_banner(
    *,
    hotkey: str,
    ws_url: str,
    voice: str,
) -> None:
    global _BANNER_RENDERED

    if _BANNER_RENDERED:
        return

    _BANNER_INFO["hotkey"] = hotkey
    _BANNER_INFO["ws_url"] = ws_url
    _BANNER_INFO["voice"] = voice

    _BANNER_RENDERED = True

    console.print()

    console.print(
        _gradient_banner(
            phase=0.0,
            brightness=1.0,
        )
    )

    _banner_details()


@dataclass
class _StatusSnapshot:
    turn: str = "idle"
    connection: str = "connecting"
    detail: str = ""


_BREATH_ANCHOR = {
    "idle": 0.0,
    "recording": 0.15,
    "thinking": 0.45,
    "speaking": 0.75,
}

_BREATH_PERIOD_S = {
    "idle": 3.2,
    "recording": 1.1,
    "thinking": 1.6,
    "speaking": 1.3,
}

_CONN_GLYPH = {
    "connected": (
        "state.connected",
        "connected",
    ),
    "connecting": (
        "state.connecting",
        "connecting…",
    ),
    "disconnected": (
        "state.disconnected",
        "offline",
    ),
}


class StatusLine:
    def __init__(
        self,
        refresh_per_second: float = 24.0,
    ) -> None:
        self._lock = threading.Lock()
        self._snapshot = _StatusSnapshot()
        self._refresh_per_second = refresh_per_second
        self._start_time = 0.0
        self._started = False

    def start(self) -> None:
        if self._started:
            return

        self._started = True
        self._start_time = __import__("time").monotonic()

    def stop(self) -> None:
        self._started = False

    def set(
        self,
        *,
        turn: str | None = None,
        connection: str | None = None,
        detail: str | None = None,
    ) -> None:
        with self._lock:
            if turn is not None:
                self._snapshot.turn = turn

            if connection is not None:
                self._snapshot.connection = connection

            if detail is not None:
                self._snapshot.detail = detail

            snapshot = _StatusSnapshot(
                **vars(self._snapshot)
            )

        self._print_status(snapshot)

    def _print_status(
        self,
        snapshot: _StatusSnapshot | None = None,
    ) -> None:
        with self._lock:
            snap = snapshot or _StatusSnapshot(
                **vars(self._snapshot)
            )

        anchor = _BREATH_ANCHOR.get(
            snap.turn,
            _BREATH_ANCHOR["idle"],
        )

        dot_color = sample_hex(anchor)

        conn_style, conn_label = _CONN_GLYPH.get(
            snap.connection,
            _CONN_GLYPH["disconnected"],
        )

        labels = {
            "idle": "idle",
            "recording": "listening",
            "thinking": "thinking",
            "speaking": "speaking",
        }

        label = labels.get(
            snap.turn,
            "idle",
        )

        line = Text()

        line.append(
            " ● ",
            style=dot_color,
        )

        line.append(
            label.ljust(10),
            style=dot_color,
        )

        line.append("  ")

        line.append(
            "· ",
            style="quince.muted",
        )

        line.append(
            conn_label,
            style=conn_style,
        )

        if snap.detail:
            line.append("   ")
            line.append(
                snap.detail,
                style="quince.dim",
            )

        console.print(line)