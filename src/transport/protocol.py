from __future__ import annotations

"""
Basket wire protocol.

Outgoing messages are plain dicts serialised to JSON by the caller.
Incoming messages are either binary (raw PCM16 TTS audio) or JSON
text (control/status events). BasketEvent gives the rest of the
client a typed, validated shape instead of raw dicts, so a malformed
message from the server can't propagate as a silent no-op.
"""

import json
from dataclasses import dataclass
from typing import Any

from src.config import LlmSettings, SttSettings, TtsSettings
from src.errors import ProtocolError


# ============================================================
# OUTGOING
# ============================================================


def build_start_message(
    *,
    stt: SttSettings,
    llm: LlmSettings,
    tts: TtsSettings,
    sample_rate: int,
) -> dict[str, Any]:
    """The message that kicks off a voice turn."""
    return {
        "type": "start",
        "prompt": stt.prompt,
        "stream": stt.stream,
        "sample_rate": sample_rate,
        "llm": {
            "model": llm.model,
            "messages": llm.messages,
            "temperature": llm.temperature,
            "top_p": llm.top_p,
            "max_tokens": llm.max_tokens,
            "stop": llm.stop,
            "seed": llm.seed,
            "system_prompt": llm.system_prompt,
            "abstracted": llm.abstracted,
        },
        "tts": {
            "voice": tts.voice,
            "temperature": tts.temperature,
        },
    }


def build_stop_message() -> dict[str, Any]:
    return {"type": "stop"}


def build_cancel_message() -> dict[str, Any]:
    return {"type": "cancel"}


# ============================================================
# INCOMING
# ============================================================

# Every event type Basket is expected to send. Anything else is
# logged and ignored rather than raising, so a Basket-side addition
# doesn't crash the client — only a malformed *known* event does.
KNOWN_EVENT_TYPES = {
    "ready",
    "started",
    "pipeline.started",
    "stt.started",
    "stt.partial",
    "stt.final",
    "llm.token",
    "llm.final",
    "tts.started",
    "tts.completed",
    "cancelled",
    "pipeline.completed",
    "error",
}


@dataclass(frozen=True)
class BasketEvent:
    type: str
    data: Any
    raw: dict[str, Any]


def parse_event(message: str) -> BasketEvent:
    """
    Parse a JSON text message from Basket into a BasketEvent.

    Raises ProtocolError on anything that isn't a well-formed JSON
    object with a string "type" field — callers should catch this,
    log it, and continue rather than crash the receive loop.
    """

    try:
        parsed = json.loads(message)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"Basket sent invalid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ProtocolError(f"Basket event was not a JSON object: {type(parsed).__name__}")

    event_type = parsed.get("type")
    if not isinstance(event_type, str) or not event_type:
        raise ProtocolError(f"Basket event missing a valid 'type' field: {parsed!r}")

    return BasketEvent(type=event_type, data=parsed.get("data"), raw=parsed)
