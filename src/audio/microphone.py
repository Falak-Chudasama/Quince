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

        try:
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

            self._stream = sd.RawInputStream(**kwargs)
            self._stream.start()

        except Exception as exc:
            raise AudioStreamError(f"Failed to open microphone stream: {exc}") from exc

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
