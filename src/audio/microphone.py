from __future__ import annotations

import queue
import threading

import sounddevice as sd

from src.audio.devices import device_still_matches, resolve_input_device
from src.config import AudioSettings
from src.errors import AudioStreamError
from src.logging_setup import get_logger

logger = get_logger("audio.microphone")


class Microphone:
    """
    Low-latency, bit-faithful PCM16 microphone capture.

    For Qwen3-ASR the target is:
        16,000 Hz
        mono
        signed 16-bit PCM

    No AGC, normalization, EQ, noise suppression, or resampling is applied
    in application code. This preserves the waveform and avoids changing the
    acoustic characteristics the ASR model sees.
    """

    def __init__(self, settings: AudioSettings) -> None:
        self._settings = settings
        self.queue: queue.Queue[bytes] = queue.Queue()

        self._enabled = threading.Event()
        self._stream: sd.RawInputStream | None = None
        self._device_index: int | None = None

        self._wasapi_settings = None

    def _make_wasapi_settings(self):
        if not hasattr(sd, "WasapiSettings"):
            return None

        return sd.WasapiSettings(
            exclusive=self._settings.wasapi_exclusive,
            auto_convert=self._settings.wasapi_auto_convert,
        )

    # ------------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------------

    def open(self) -> None:
        host_api = self._settings.input_host_api or self._settings.host_api

        self._device_index = resolve_input_device(
            self._settings.input_device,
            self._settings.fallback_to_default_on_missing,
            host_api,
        )

        self._wasapi_settings = self._make_wasapi_settings()

        kwargs = dict(
            samplerate=self._settings.sample_rate,
            channels=self._settings.channels,
            dtype="int16",
            device=self._device_index,
            blocksize=self._settings.blocksize,
            latency=self._settings.input_latency,
            callback=self._callback,
            clip_off=False,
            dither_off=True,
        )

        if self._wasapi_settings is not None and host_api:
            kwargs["extra_settings"] = self._wasapi_settings

        stream_opened = False
        last_error = None

        # Attempt 1: Configured device with extra settings (WASAPI auto-convert)
        try:
            self._stream = sd.RawInputStream(**kwargs)
            self._stream.start()
            stream_opened = True
        except Exception as exc:
            last_error = exc
            logger.warning("Microphone start attempt 1 failed on device %s: %s", self._device_index, exc)

        # Attempt 2: Same device without extra_settings
        if not stream_opened and "extra_settings" in kwargs:
            try:
                kwargs.pop("extra_settings", None)
                self._stream = sd.RawInputStream(**kwargs)
                self._stream.start()
                stream_opened = True
                logger.info("Microphone opened on device %s without extra_settings.", self._device_index)
            except Exception as exc:
                last_error = exc
                logger.warning("Microphone start attempt 2 failed on device %s: %s", self._device_index, exc)

        # Attempt 3: Fallback to system default input device
        if not stream_opened and (self._device_index is not None or self._settings.fallback_to_default_on_missing):
            try:
                kwargs["device"] = None
                kwargs.pop("extra_settings", None)
                self._stream = sd.RawInputStream(**kwargs)
                self._stream.start()
                self._device_index = None
                stream_opened = True
                logger.info("Microphone opened on system default input device.")
            except Exception as exc:
                last_error = exc
                logger.warning("Microphone fallback to default input failed: %s", exc)

        if not stream_opened:
            raise AudioStreamError(f"Failed to open microphone stream: {last_error}") from last_error

        logger.info(
            "Microphone ready: %d Hz mono PCM16 (device index=%s, host_api=%s, blocksize=%d)",
            self._settings.sample_rate,
            self._device_index,
            host_api,
            self._settings.blocksize,
        )

    def close(self) -> None:
        if self._stream is None:
            return

        try:
            self._stream.stop()
        except Exception:
            logger.debug("Error stopping microphone stream (ignored).", exc_info=True)

        try:
            self._stream.close()
        except Exception:
            logger.debug("Error closing microphone stream (ignored).", exc_info=True)

        self._stream = None

    # ------------------------------------------------------------
    # CAPTURE GATE
    # ------------------------------------------------------------

    def enable(self) -> None:
        self.drain()
        self._enabled.set()

    def disable(self) -> None:
        self._enabled.clear()

    @property
    def is_enabled(self) -> bool:
        return self._enabled.is_set()

    def drain(self) -> None:
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

    # ------------------------------------------------------------
    # CALLBACK
    # ------------------------------------------------------------

    def _callback(self, indata, frames: int, time_info, status) -> None:
        if status:
            logger.warning("Microphone stream status: %s", status)

        if not self._enabled.is_set():
            return

        audio = bytes(indata)
        if not audio:
            return

        self.queue.put(audio)

    # ------------------------------------------------------------
    # WATCHDOG SUPPORT
    # ------------------------------------------------------------

    def device_still_valid(self) -> bool:
        host_api = self._settings.input_host_api or self._settings.host_api
        return device_still_matches(
            self._device_index,
            self._settings.input_device,
            host_api,
        )

    def reopen(self) -> None:
        logger.warning("Reopening microphone stream (device changed or dropped).")
        self.close()
        self.open()
