from __future__ import annotations

"""
Basket event handling: given a parsed BasketEvent (or a raw binary
audio frame), update the relevant piece of client state and/or push
audio to the player. Kept separate from connection/reconnect logic
and from the hotkey/orchestration logic in client.py.
"""

from typing import Callable

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
    ) -> None:
        self._player = player
        self._turn_finished_cb = on_turn_finished
        self._cancelled_cb = on_cancelled
        self._llm_token_cb = on_llm_token
        self._llm_final_cb = on_llm_final

        # event.type -> log-only handler. Anything with a caller-visible
        # side effect is handled explicitly in _dispatch instead.
        self._log_handlers: dict[str, Callable[[BasketEvent], None]] = {
            "ready": lambda e: logger.info("Basket ready: protocol=%s", e.raw.get("protocol")),
            "started": lambda e: logger.info("Basket started voice turn."),
            "pipeline.started": lambda e: logger.info("Voice pipeline started."),
            "stt.started": lambda e: logger.info("STT started."),
            "stt.partial": lambda e: logger.debug("STT partial: %s", e.data),
            "stt.final": lambda e: logger.info("STT final: %r", e.data),
            "tts.started": lambda e: logger.info("TTS started: %r", e.data),
            "tts.completed": lambda e: logger.info("TTS completed."),
            "error": lambda e: logger.error(
                "Basket reported an error: code=%s message=%s",
                e.raw.get("code"),
                e.raw.get("message"),
            ),
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
        # Events with real side effects, handled explicitly.
        if event.type == "llm.token":
            self._llm_token_cb(str(event.data or ""))
            return

        if event.type == "llm.final":
            text = str(event.data or "").strip()
            if text:
                self._llm_final_cb(text)
            logger.info("LLM final.")
            return

        if event.type == "cancelled":
            self._cancelled_cb()
            logger.info("Basket confirmed cancellation.")
            return

        if event.type == "pipeline.completed":
            self._turn_finished_cb()
            logger.info("Voice pipeline completed.")
            return

        # Everything else is log-only.
        handler = self._log_handlers.get(event.type)

        if handler is None:
            logger.debug("Unhandled Basket event type: %s", event.type)
            return

        handler(event)
