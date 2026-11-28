from __future__ import annotations

"""
Basket event handling: given a parsed BasketEvent (or a raw binary
audio frame), update the relevant piece of client state and/or push
audio to the player. Kept separate from connection/reconnect logic
and from the hotkey/orchestration logic in client.py.
"""

from typing import Any, Callable

from src.audio.player import PCMPlayer
from src.logging_setup import get_logger
from src.transport.protocol import BasketEvent, parse_event

logger = get_logger("transport.events")


class BasketEventHandler:
    """
    Stateless with respect to the websocket itself — it only touches
    the audio player and a small set of callbacks the orchestrator
    provides for turn-lifecycle bookkeeping (clearing recording /
    pipeline-busy flags, etc). Callback attribute names are kept
    distinct from event-type strings to avoid any name collision.
    """

    def __init__(
        self,
        player: PCMPlayer,
        *,
        on_turn_finished: Callable[[], None],
        on_cancelled: Callable[[], None],
        on_llm_token: Callable[[str], None],
        on_llm_final: Callable[[str], None],
        on_stt_final: Callable[[str], None] | None = None,
        on_rtsi_speak: Callable[[str], None] | None = None,
        on_await_user: Callable[[dict[str, Any]], None] | None = None,
        on_tts_started: Callable[[Any], None] | None = None,
        on_tts_completed: Callable[[], None] | None = None,
    ) -> None:
        self._player = player
        self._turn_finished_cb = on_turn_finished
        self._cancelled_cb = on_cancelled
        self._llm_token_cb = on_llm_token
        self._llm_final_cb = on_llm_final
        self._stt_final_cb = on_stt_final
        self._rtsi_speak_cb = on_rtsi_speak
        self._await_user_cb = on_await_user
        self._tts_started_cb = on_tts_started
        self._tts_completed_cb = on_tts_completed
        self._turn_had_output = False

        # event.type -> log-only handler. Anything with a caller-visible
        # side effect is handled explicitly in _dispatch instead.
        self._log_handlers: dict[str, Callable[[BasketEvent], None]] = {
            "ready": lambda e: logger.info("Basket ready: protocol=%s", e.raw.get("protocol")),
            "started": lambda e: logger.info("Basket started voice turn."),
            "pipeline.started": lambda e: logger.info("Voice pipeline started."),
            "stt.started": lambda e: logger.info("STT started."),
            "stt.partial": lambda e: logger.debug("STT partial: %s", e.data),
            "stt.final": lambda e: logger.info("STT final: %r", e.data),
            "rtsi.ended": lambda e: logger.info("RTSI session ended: %r", e.data),
        }

    # ------------------------------------------------------------
    # ENTRY POINTS
    # ------------------------------------------------------------

    def handle_binary(self, message: bytes, *, playback_interrupted: bool) -> None:
        """Raw PCM16 TTS audio. Dropped silently if playback was interrupted."""

        if playback_interrupted:
            return

        self._player.enqueue(message)
        logger.debug("TTS audio chunk received: %d bytes", len(message))

    def handle_text(self, message: str) -> BasketEvent | None:
        """
        Parse and dispatch a JSON event. Returns the parsed event for
        callers that need to react further (e.g. flipping a
        playback-active flag on "started"), or None if malformed.
        """

        try:
            event = parse_event(message)
        except Exception as exc:
            logger.warning("Ignoring malformed Basket message: %s", exc)
            return None

        self._dispatch(event)
        return event

    # ------------------------------------------------------------
    # DISPATCH
    # ------------------------------------------------------------

    def _dispatch(self, event: BasketEvent) -> None:
        if event.type in ("started", "pipeline.started"):
            self._turn_had_output = False

        if event.type == "stt.final":
            text = str(event.data or "").strip()
            if text and self._stt_final_cb is not None:
                self._stt_final_cb(text)
            logger.info("STT final: %r", event.data)
            return

        if event.type == "llm.token":
            self._turn_had_output = True
            self._llm_token_cb(str(event.data or ""))
            return

        if event.type == "llm.final":
            self._turn_had_output = True
            text = str(event.data or "").strip()
            if text:
                self._llm_final_cb(text)
            logger.info("LLM final.")
            return

        if event.type == "tts.started":
            logger.info("TTS started: %r", event.data)
            if self._tts_started_cb is not None:
                self._tts_started_cb(event.data)
            return

        if event.type == "tts.completed":
            logger.info("TTS completed.")
            if self._tts_completed_cb is not None:
                self._tts_completed_cb()
            return

        if event.type == "rtsi.speak":
            self._turn_had_output = True
            if isinstance(event.data, dict):
                text = str(event.data.get("text") or event.data.get("line") or "").strip()
            else:
                text = str(event.data or event.raw.get("text") or "").strip()
            logger.info("RTSI speak: %r", text)
            if text and self._rtsi_speak_cb is not None:
                self._rtsi_speak_cb(text)
            return

        if event.type == "rtsi.await_user":
            payload = event.data if isinstance(event.data, dict) else dict(event.raw)
            logger.info("RTSI awaiting user: %r", payload)
            if self._await_user_cb is not None:
                self._await_user_cb(payload)
            return

        if event.type == "cancelled":
            self._cancelled_cb()
            logger.info("Basket confirmed cancellation.")
            return

        if event.type == "pipeline.completed":
            self._turn_finished_cb()
            logger.info("Voice pipeline completed.")
            return

        if event.type == "error":
            self._turn_finished_cb()
            code = event.raw.get("code", "pipeline_failed")
            msg = event.raw.get("message", "An unexpected error occurred.")
            logger.error("Basket reported an error: code=%s message=%s", code, msg)
            if not self._turn_had_output:
                self._llm_final_cb(f"[Notice] Basket reported: {msg}")
            return

        # Everything else is log-only.
        handler = self._log_handlers.get(event.type)

        if handler is None:
            logger.debug("Unhandled Basket event type: %s", event.type)
            return

        handler(event)

