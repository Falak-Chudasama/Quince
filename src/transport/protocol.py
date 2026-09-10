from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any
from datetime import datetime, timezone

from src.config import LlmSettings, SttSettings, TtsSettings, APPLICATION
from src.errors import ProtocolError


# ============================================================
# OUTGOING
# ============================================================


def build_message() -> dict[str, Any]:
    return {
        "application": APPLICATION,
        "datetime": datetime.now(timezone.utc).isoformat(),
    }

def build_start_message(
    *,
    stt: SttSettings,
    llm: LlmSettings,
    tts: TtsSettings,
    sample_rate: int,
) -> dict[str, Any]:
    """The message that kicks off a voice turn."""
    message = build_message()
    return {
        **message,
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
    message = build_message()
    return {
        **message,
        "type": "stop",
    }


def build_cancel_message() -> dict[str, Any]:
    message = build_message()
    return {
        **message,
        "type": "cancel",
    }


# ============================================================
# INCOMING
# ============================================================

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
