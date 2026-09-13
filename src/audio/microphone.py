from __future__ import annotations

"""
Microphone capture.

Always opened against a pinned device index (typically the laptop's
built-in mic) so that connecting a bluetooth headset never redirects
STT input to the headset's mic. See audio/devices.py for how the
device is chosen.
"""

import queue
import threading

import sounddevice as sd

from src.audio.devices import device_still_matches, resolve_input_device
from src.config import AudioSettings
from src.errors import AudioStreamError
from src.logging_setup import get_logger

logger = get_logger("audio.microphone")


class Microphone:
    def __init__(self, settings: AudioSettings) -> None:
        self._settings = settings
        self.queue: queue.Queue[bytes] = queue.Queue()

        self._enabled = threading.Event()  # gated by push-to-talk state
        self._stream: sd.InputStream | None = None
        self._device_index: int | None = None

    # ------------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------------

    def open(self) -> None:
        self._device_index = resolve_input_device(
            self._settings.input_device,
            self._settings.fallback_to_default_on_missing,
        )

        try:
            self._stream = sd.InputStream(
                samplerate=self._settings.sample_rate,
                channels=self._settings.channels,
                dtype="int16",
                device=self._device_index,
                blocksize=self._settings.blocksize,
                callback=self._callback,
            )
            self._stream.start()

        except Exception as exc:
            raise AudioStreamError(f"Failed to open microphone stream: {exc}") from exc

        logger.info(
            "Microphone ready: %d Hz mono PCM16 (device index=%s)",
            self._settings.sample_rate,
            self._device_index,
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
    # CAPTURE GATE (push-to-talk)
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
        """Discard any buffered audio, e.g. before starting a fresh turn."""
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
            logger.debug("Microphone stream status: %s", status)

        if not self._enabled.is_set():
            return

        self.queue.put(bytes(indata))

    # ------------------------------------------------------------
    # WATCHDOG SUPPORT
    # ------------------------------------------------------------

    def device_still_valid(self) -> bool:
        """True if the pinned device is still what we think it is."""
        return device_still_matches(self._device_index, self._settings.input_device)

    def reopen(self) -> None:
        """Close and reopen against a freshly resolved device index."""
        logger.warning("Reopening microphone stream (device changed or dropped).")
        self.close()
        self.open()
