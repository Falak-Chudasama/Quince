from __future__ import annotations

"""
TTS playback.

Always opened against a pinned device index (typically a bluetooth
headset) independent of whatever device the microphone is pinned to
and independent of the input stream entirely — the two streams do not
have to be the same device or even the same host API.
"""

import queue
import threading

import sounddevice as sd

from src.audio.devices import device_still_matches, resolve_output_device
from src.config import AudioSettings, TtsSettings
from src.errors import AudioStreamError
from src.logging_setup import get_logger

logger = get_logger("audio.player")


class PCMPlayer:
    """
    Continuous PCM16 output stream for TTS playback.

    Audio arrives in small binary chunks and is queued; interrupt()
    silences output immediately and drops anything still queued,
    without tearing down the underlying stream.
    """

    def __init__(self, tts_settings: TtsSettings, audio_settings: AudioSettings) -> None:
        self._tts_settings = tts_settings
        self._audio_settings = audio_settings

        self._queue: queue.Queue[bytes] = queue.Queue()
        self._lock = threading.Lock()

        self._current_chunk = b""
        self._current_offset = 0

        self._interrupted = threading.Event()
        self._closed = threading.Event()

        self._stream: sd.RawOutputStream | None = None
        self._device_index: int | None = None

    # ------------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------------

    def open(self) -> None:
        self._device_index = resolve_output_device(
            self._audio_settings.output_device,
            self._audio_settings.fallback_to_default_on_missing,
        )

        try:
            self._stream = sd.RawOutputStream(
                samplerate=self._tts_settings.sample_rate,
                channels=self._tts_settings.channels,
                dtype="int16",
                device=self._device_index,
                blocksize=self._audio_settings.blocksize,
                callback=self._callback,
            )
            self._stream.start()

        except Exception as exc:
            raise AudioStreamError(f"Failed to open TTS playback stream: {exc}") from exc

        logger.info(
            "TTS playback ready: %d Hz mono PCM16 (device index=%s)",
            self._tts_settings.sample_rate,
            self._device_index,
        )

    def close(self) -> None:
        if self._closed.is_set():
            return

        self._closed.set()
        self._interrupted.set()

        if self._stream is not None:
            try:
                self._stream.abort()
            except Exception:
                logger.debug("Error aborting playback stream (ignored).", exc_info=True)
            try:
                self._stream.close()
            except Exception:
                logger.debug("Error closing playback stream (ignored).", exc_info=True)
            self._stream = None

        self._clear_queue()
        logger.info("TTS playback closed.")

    # ------------------------------------------------------------
    # CALLBACK
    # ------------------------------------------------------------

    def _callback(self, outdata, frames: int, time_info, status) -> None:
        if status:
            logger.debug("TTS output stream status: %s", status)

        output_bytes = len(outdata)

        if self._interrupted.is_set():
            outdata[:] = b"\x00" * output_bytes
            return

        with self._lock:
            while self._current_offset >= len(self._current_chunk):
                try:
                    self._current_chunk = self._queue.get_nowait()
                    self._current_offset = 0
                except queue.Empty:
                    self._current_chunk = b""
                    self._current_offset = 0
                    break

            if not self._current_chunk:
                outdata[:] = b"\x00" * output_bytes
                return

            remaining = len(self._current_chunk) - self._current_offset
            copy_size = min(remaining, output_bytes)

            outdata[:copy_size] = self._current_chunk[
                self._current_offset : self._current_offset + copy_size
            ]
            self._current_offset += copy_size

            if copy_size < output_bytes:
                outdata[copy_size:] = b"\x00" * (output_bytes - copy_size)

    # ------------------------------------------------------------
    # QUEUE CONTROL
    # ------------------------------------------------------------

    def enqueue(self, audio: bytes) -> None:
        if not audio or self._closed.is_set() or self._interrupted.is_set():
            return
        self._queue.put(bytes(audio))

    def interrupt(self) -> None:
        """Immediately silence output and drop anything queued."""
        self._interrupted.set()
        with self._lock:
            self._current_chunk = b""
            self._current_offset = 0
        self._clear_queue()
        logger.info("TTS playback interrupted.")

    def resume(self) -> None:
        if not self._closed.is_set():
            self._interrupted.clear()

    def _clear_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    @property
    def interrupted(self) -> bool:
        return self._interrupted.is_set()

    # ------------------------------------------------------------
    # WATCHDOG SUPPORT
    # ------------------------------------------------------------

    def device_still_valid(self) -> bool:
        return device_still_matches(self._device_index, self._audio_settings.output_device)

    def reopen(self) -> None:
        """Tear down the underlying stream and open it again, same settings."""
        logger.warning("Reopening TTS playback stream (device changed or dropped).")

        if self._stream is not None:
            try:
                self._stream.abort()
                self._stream.close()
            except Exception:
                logger.debug("Error tearing down playback stream before reopen (ignored).", exc_info=True)
            self._stream = None

        self._closed.clear()
        self._interrupted.clear()
        self.open()
