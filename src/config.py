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
    ping_interval: int = field(default_factory=lambda: _env_int("WS_PING_INTERVAL", 20))
    ping_timeout: int = field(default_factory=lambda: _env_int("WS_PING_TIMEOUT", 20))
    max_size: int | None = field(default_factory=lambda: _env_int("WS_MAX_SIZE", None))
    connect_timeout: float = field(default_factory=lambda: _env_float("WS_CONNECT_TIMEOUT", 8.0))

    reconnect: bool = field(default_factory=lambda: _env_bool("WS_RECONNECT", True))
    reconnect_initial_delay: float = field(default_factory=lambda: _env_float("WS_RECONNECT_INITIAL_DELAY", 1.0))
    reconnect_max_delay: float = field(default_factory=lambda: _env_float("WS_RECONNECT_MAX_DELAY", 30.0))
    reconnect_backoff_factor: float = field(default_factory=lambda: _env_float("WS_RECONNECT_BACKOFF", 2.0))
    reconnect_max_attempts: int = field(default_factory=lambda: _env_int("WS_RECONNECT_MAX_ATTEMPTS", 0))


@dataclass(frozen=True)
class AudioSettings:
    # Qwen3-ASR expects mono 16 kHz audio. The official processor converts
    # audio to mono 16 kHz float32 internally; sending clean PCM16 at 16 kHz
    # avoids an unnecessary application-side conversion step.
    sample_rate: int = field(default_factory=lambda: _env_int("AUDIO_SAMPLE_RATE", 16_000))
    channels: int = field(default_factory=lambda: _env_int("AUDIO_CHANNELS", 1))
    sample_width: int = field(default_factory=lambda: _env_int("AUDIO_SAMPLE_WIDTH", 2))

    # 40 ms blocks: low enough latency for a local voice pipeline while
    # avoiding excessive callback/WebSocket overhead.
    blocksize: int = field(default_factory=lambda: _env_int("AUDIO_BLOCKSIZE", 640))

    input_device: str | None = field(default_factory=lambda: _env_str("AUDIO_INPUT_DEVICE", None))
    output_device: str | None = field(default_factory=lambda: _env_str("AUDIO_OUTPUT_DEVICE", None))

    # Force the modern Windows audio path instead of accidentally selecting
    # the first MME/DirectSound duplicate of the same Bluetooth device.
    host_api: str | None = field(default_factory=lambda: _env_str("AUDIO_HOST_API", "Windows WASAPI"))
    input_host_api: str | None = field(default_factory=lambda: _env_str("AUDIO_INPUT_HOST_API", None))
    output_host_api: str | None = field(default_factory=lambda: _env_str("AUDIO_OUTPUT_HOST_API", None))

    # Bluetooth devices can temporarily disappear/re-enumerate. For Quince,
    # failing loudly is safer than silently switching to the laptop mic.
    fallback_to_default_on_missing: bool = field(
        default_factory=lambda: _env_bool("AUDIO_FALLBACK_TO_DEFAULT", False)
    )

    # WASAPI shared mode with auto-conversion lets Windows bridge the requested
    # 16/24 kHz stream to the device's actual shared-mode format when needed.
    wasapi_exclusive: bool = field(default_factory=lambda: _env_bool("AUDIO_WASAPI_EXCLUSIVE", False))
    wasapi_auto_convert: bool = field(default_factory=lambda: _env_bool("AUDIO_WASAPI_AUTO_CONVERT", True))

    input_latency: str = field(default_factory=lambda: _env_str("AUDIO_INPUT_LATENCY", "low"))
    output_latency: str = field(default_factory=lambda: _env_str("AUDIO_OUTPUT_LATENCY", "low"))

    # Capture remains bit-faithful by default. Do not normalize every frame:
    # doing so would raise the noise floor and can make ASR less reliable.
    input_gain: float = field(default_factory=lambda: _env_float("AUDIO_INPUT_GAIN", 1.0))

    device_watchdog_interval: float = field(
        default_factory=lambda: _env_float("AUDIO_DEVICE_WATCHDOG_INTERVAL", 5.0)
    )


@dataclass(frozen=True)
class SttSettings:
    prompt: str | None = field(
        default_factory=lambda: _env_str(
            "STT_PROMPT",
            "Your name is Quince, Transcribe the spoken audio accurately in English. Return only the words that were spoken. Do not translate, summarize, or invent words.",
        )
    )
    stream: bool = field(default_factory=lambda: _env_bool("STT_STREAM", True))


@dataclass(frozen=True)
class LlmSettings:
    model: str | None = field(default_factory=lambda: _env_str("LLM_MODEL", None))
    messages: list[dict[str, Any]] = field(default_factory=list)
    temperature: float | None = field(default_factory=lambda: _env_float("LLM_TEMPERATURE", 0.05))
    top_p: float | None = field(default_factory=lambda: _env_float("LLM_TOP_P", 1.0))
    max_tokens: int | None = field(default_factory=lambda: _env_int("LLM_MAX_TOKENS", 1000))
    stop: Any | None = None
    seed: int | None = field(default_factory=lambda: _env_int("LLM_SEED", None))
    system_prompt: str = field(default_factory=lambda: _env_str("LLM_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT))
    abstracted: bool = field(default_factory=lambda: _env_bool("LLM_ABSTRACTED", True))


@dataclass(frozen=True)
class TtsSettings:
    voice: str = field(default_factory=lambda: _env_str("TTS_VOICE", "eve"))
    temperature: float = field(default_factory=lambda: _env_float("TTS_TEMPERATURE", 0.75))

    # Pocket TTS natively generates 24 kHz mono 16-bit PCM/WAV. Keep that
    # format intact through Basket and Quince instead of downsampling it.
    sample_rate: int = field(default_factory=lambda: _env_int("TTS_SAMPLE_RATE", 24_000))
    channels: int = field(default_factory=lambda: _env_int("TTS_CHANNELS", 1))
    sample_width: int = field(default_factory=lambda: _env_int("TTS_SAMPLE_WIDTH", 2))


@dataclass(frozen=True)
class InputSettings:
    push_to_talk_hotkey: str = field(default_factory=lambda: _env_str("PUSH_TO_TALK_HOTKEY", "ctrl+q"))


@dataclass(frozen=True)
class Settings:
    basket: BasketSettings = field(default_factory=BasketSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    stt: SttSettings = field(default_factory=SttSettings)
    llm: LlmSettings = field(default_factory=LlmSettings)
    tts: TtsSettings = field(default_factory=TtsSettings)
    input: InputSettings = field(default_factory=InputSettings)
    log_level: str = field(default_factory=lambda: _env_str("LOG_LEVEL", "INFO"))


APPLICATION = os.getenv("APPLICATION", "quince")
settings = Settings()
