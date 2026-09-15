from __future__ import annotations

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
    Low-latency PCM16 playback for Pocket TTS.

    Pocket TTS natively produces 24 kHz mono PCM. We keep that source format
    untouched through the WebSocket and hand it directly to PortAudio as
    int16. On Windows WASAPI shared mode, PortAudio can use the system mixer
    conversion only when the physical endpoint requires it.
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
        self._wasapi_settings = None

    def _make_wasapi_settings(self):
        if not hasattr(sd, "WasapiSettings"):
            return None

        return sd.WasapiSettings(
            exclusive=self._audio_settings.wasapi_exclusive,
            auto_convert=self._audio_settings.wasapi_auto_convert,
        )

    # ------------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------------

    def open(self) -> None:
        host_api = self._audio_settings.output_host_api or self._audio_settings.host_api

        self._device_index = resolve_output_device(
            self._audio_settings.output_device,
            self._audio_settings.fallback_to_default_on_missing,
            host_api,
        )

        self._wasapi_settings = self._make_wasapi_settings()

        try:
            kwargs = dict(
                samplerate=self._tts_settings.sample_rate,
                channels=self._tts_settings.channels,
                dtype="int16",
                device=self._device_index,
                blocksize=self._audio_settings.blocksize,
                latency=self._audio_settings.output_latency,
                callback=self._callback,
                clip_off=False,
                dither_off=True,
            )

            if self._wasapi_settings is not None and host_api:
                kwargs["extra_settings"] = self._wasapi_settings

            self._stream = sd.RawOutputStream(**kwargs)
            self._stream.start()

        except Exception as exc:
            raise AudioStreamError(f"Failed to open TTS playback stream: {exc}") from exc

        logger.info(
            "TTS playback ready: %d Hz mono PCM16 (device index=%s, host_api=%s, blocksize=%d)",
            self._tts_settings.sample_rate,
            self._device_index,
            host_api,
            self._audio_settings.blocksize,
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
            logger.warning("TTS output stream status: %s", status)

        output_bytes = len(outdata)

        if self._interrupted.is_set():
            outdata[:] = b"\x00" * output_bytes
            return

        with self._lock:
            remaining_output = output_bytes
            output_offset = 0

            while remaining_output > 0:
                while self._current_offset >= len(self._current_chunk):
                    try:
                        self._current_chunk = self._queue.get_nowait()
                        self._current_offset = 0
                    except queue.Empty:
                        self._current_chunk = b""
                        self._current_offset = 0
                        break

                if not self._current_chunk:
                    outdata[output_offset:] = b"\x00" * remaining_output
                    break

                remaining_chunk = len(self._current_chunk) - self._current_offset
                copy_size = min(remaining_chunk, remaining_output)

                outdata[output_offset:output_offset + copy_size] = self._current_chunk[
                    self._current_offset:self._current_offset + copy_size
                ]

                self._current_offset += copy_size
                output_offset += copy_size
                remaining_output -= copy_size

    # ------------------------------------------------------------
    # QUEUE CONTROL
    # ------------------------------------------------------------

    def enqueue(self, audio: bytes) -> None:
        if not audio or self._closed.is_set() or self._interrupted.is_set():
            return
        self._queue.put(audio)

    def interrupt(self) -> None:
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
        host_api = self._audio_settings.output_host_api or self._audio_settings.host_api
        return device_still_matches(
            self._device_index,
            self._audio_settings.output_device,
            host_api,
        )

    def reopen(self) -> None:
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
