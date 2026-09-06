from __future__ import annotations

from typing import Any


# ============================================================
# BASKET
# ============================================================

BASKET_WS_URL = "ws://127.0.0.1:7000/ws"


# ============================================================
# AUDIO
# ============================================================

AUDIO_SAMPLE_RATE = 16_000
AUDIO_CHANNELS = 1
AUDIO_SAMPLE_WIDTH = 2  # PCM16 = 2 bytes


# ============================================================
# STT
# ============================================================

STT_PROMPT: str | None = "You are named Quince"
STT_STREAM = True


# ============================================================
# LLM
# ============================================================

LLM_MODEL: str | None = None

LLM_MESSAGES: list[dict[str, Any]] = []

LLM_TEMPERATURE: float | None = 0.7
LLM_TOP_P: float | None = 1.0
LLM_MAX_TOKENS: int | None = None
LLM_STOP: Any | None = None
LLM_SEED: int | None = None

LLM_SYSTEM_PROMPT: str | None = (
    "Your name is Quince, a helpful local AI assistant. Do not generate verbose responses and never use emojis."
)

LLM_ABSTRACTED = True


# ============================================================
# TTS
# ============================================================

TTS_VOICE = "jane"
TTS_TEMPERATURE = 0.5
TTS_SAMPLE_RATE = 24_000
TTS_CHANNELS = 1
TTS_SAMPLE_WIDTH = 2


# ============================================================
# INPUT
# ============================================================

PUSH_TO_TALK_HOTKEY = "ctrl+q"

WS_PING_INTERVAL = 20
WS_PING_TIMEOUT = 20
WS_MAX_SIZE = None