from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Any
from dotenv import load_dotenv

from src.prompts.system_prompt import DEFAULT_SYSTEM_PROMPT

load_dotenv()


def _env_str(name: str, default: str | None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _env_int(name: str, default: int | None) -> int | None:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float | None) -> float | None:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class BasketSettings:
    ws_url: str = field(default_factory=lambda: _env_str("BASKET_WS_URL", "ws://127.0.0.1:7000/ws"))
    api_url: str = field(default_factory=lambda: _env_str("BASKET_API_URL", "http://127.0.0.1:7000"))
    ping_interval: int = field(default_factory=lambda: _env_int("WS_PING_INTERVAL", 20))
    ping_timeout: int = field(default_factory=lambda: _env_int("WS_PING_TIMEOUT", 20))
    max_size: int | None = field(default_factory=lambda: _env_int("WS_MAX_SIZE", None))
    connect_timeout: float = field(default_factory=lambda: _env_float("WS_CONNECT_TIMEOUT", 8.0))

    reconnect: bool = field(default_factory=lambda: _env_bool("WS_RECONNECT", True))
    reconnect_initial_delay: float = field(default_factory=lambda: _env_float("WS_RECONNECT_INITIAL_DELAY", 1.0))
    reconnect_max_delay: float = field(default_factory=lambda: _env_float("WS_RECONNECT_MAX_DELAY", 30.0))
    reconnect_backoff_factor: float = field(default_factory=lambda: _env_float("WS_RECONNECT_BACKOFF", 2.0))
    reconnect_max_attempts: int = field(default_factory=lambda: _env_int("WS_RECONNECT_MAX_ATTEMPTS", 0))  # 0 = infinite


@dataclass(frozen=True)
class AudioSettings:
    sample_rate: int = field(default_factory=lambda: _env_int("AUDIO_SAMPLE_RATE", 16_000))
    channels: int = field(default_factory=lambda: _env_int("AUDIO_CHANNELS", 1))
    sample_width: int = field(default_factory=lambda: _env_int("AUDIO_SAMPLE_WIDTH", 2))  # PCM16
    blocksize: int = field(default_factory=lambda: _env_int("AUDIO_BLOCKSIZE", 960))

    input_device: str | None = field(default_factory=lambda: _env_str("AUDIO_INPUT_DEVICE", None))
    output_device: str | None = field(default_factory=lambda: _env_str("AUDIO_OUTPUT_DEVICE", None))

    fallback_to_default_on_missing: bool = field(
        default_factory=lambda: _env_bool("AUDIO_FALLBACK_TO_DEFAULT", True)
    )

    device_watchdog_interval: float = field(
        default_factory=lambda: _env_float("AUDIO_DEVICE_WATCHDOG_INTERVAL", 5.0)
    )


@dataclass(frozen=True)
class SttSettings:
    prompt: str | None = field(default_factory=lambda: _env_str("STT_PROMPT", "You are named Quince"))
    stream: bool = field(default_factory=lambda: _env_bool("STT_STREAM", True))


@dataclass(frozen=True)
class LlmSettings:
    model: str | None = field(default_factory=lambda: _env_str("LLM_MODEL", None))
    messages: list[dict[str, Any]] = field(default_factory=list)
    temperature: float | None = field(default_factory=lambda: _env_float("LLM_TEMPERATURE", 0.6))
    top_p: float | None = field(default_factory=lambda: _env_float("LLM_TOP_P", 1.0))
    max_tokens: int | None = field(default_factory=lambda: _env_int("LLM_MAX_TOKENS", 180))
    stop: Any | None = None
    seed: int | None = field(default_factory=lambda: _env_int("LLM_SEED", None))
    system_prompt: str = field(default_factory=lambda: _env_str("LLM_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT))
    abstracted: bool = field(default_factory=lambda: _env_bool("LLM_ABSTRACTED", True))


@dataclass(frozen=True)
class TtsSettings:
    voice: str = field(default_factory=lambda: _env_str("TTS_VOICE", "jane"))
    temperature: float = field(default_factory=lambda: _env_float("TTS_TEMPERATURE", 0.5))
    sample_rate: int = field(default_factory=lambda: _env_int("TTS_SAMPLE_RATE", 24_000))
    channels: int = field(default_factory=lambda: _env_int("TTS_CHANNELS", 1))
    sample_width: int = field(default_factory=lambda: _env_int("TTS_SAMPLE_WIDTH", 2))


@dataclass(frozen=True)
class InputSettings:
    push_to_talk_hotkey: str = field(default_factory=lambda: _env_str("PUSH_TO_TALK_HOTKEY", "ctrl+q"))


@dataclass(frozen=True)
class McpSettings:
    host: str = field(default_factory=lambda: _env_str("MCP_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("MCP_PORT", 7100))


@dataclass(frozen=True)
class Settings:
    basket: BasketSettings = field(default_factory=BasketSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    stt: SttSettings = field(default_factory=SttSettings)
    llm: LlmSettings = field(default_factory=LlmSettings)
    tts: TtsSettings = field(default_factory=TtsSettings)
    input: InputSettings = field(default_factory=InputSettings)
    mcp: McpSettings = field(default_factory=McpSettings)
    log_level: str = field(default_factory=lambda: _env_str("LOG_LEVEL", "INFO"))


APPLICATION = os.getenv("APPLICATION", "quince")

settings = Settings()