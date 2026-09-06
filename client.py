from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from typing import Any

import keyboard
import sounddevice as sd
import websockets
from websockets.asyncio.client import ClientConnection

from config import (
    AUDIO_CHANNELS,
    AUDIO_SAMPLE_RATE,
    BASKET_WS_URL,
    LLM_ABSTRACTED,
    LLM_MESSAGES,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_SEED,
    LLM_STOP,
    LLM_SYSTEM_PROMPT,
    LLM_TEMPERATURE,
    LLM_TOP_P,
    PUSH_TO_TALK_HOTKEY,
    STT_PROMPT,
    STT_STREAM,
    TTS_CHANNELS,
    TTS_SAMPLE_RATE,
    TTS_TEMPERATURE,
    TTS_VOICE,
    WS_MAX_SIZE,
    WS_PING_INTERVAL,
    WS_PING_TIMEOUT,
)


logger = logging.getLogger("quince")


# ============================================================
# AUDIO PLAYER
# ============================================================


class PCMPlayer:
    """
    Continuous PCM16 output stream for TTS playback.

    TTS audio arrives in small binary PCM chunks from Basket.
    Ctrl+Q can interrupt playback without waiting for queued
    chunks to finish.
    """

    def __init__(
        self,
        *,
        sample_rate: int,
        channels: int,
        dtype: str = "int16",
        blocksize: int = 960,
    ) -> None:

        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.blocksize = blocksize

        self._queue: queue.Queue[bytes] = queue.Queue()

        self._lock = threading.Lock()

        self._current_chunk = b""
        self._current_offset = 0

        self._interrupted = threading.Event()
        self._closed = threading.Event()

        self._stream = sd.RawOutputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=self.dtype,
            blocksize=self.blocksize,
            callback=self._callback,
        )

        self._stream.start()

        logger.info(
            "TTS audio player ready: %s Hz mono PCM16",
            self.sample_rate,
        )

    # --------------------------------------------------------
    # CALLBACK
    # --------------------------------------------------------

    def _callback(
        self,
        outdata,
        frames: int,
        time_info,
        status,
    ) -> None:

        if status:
            logger.debug(
                "TTS audio output status: %s",
                status,
            )

        output_bytes = len(outdata)

        if self._interrupted.is_set():
            outdata[:] = b"\x00" * output_bytes
            return

        with self._lock:

            while self._current_offset >= len(
                self._current_chunk
            ):

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

            remaining = (
                len(self._current_chunk)
                - self._current_offset
            )

            copy_size = min(
                remaining,
                output_bytes,
            )

            outdata[:copy_size] = self._current_chunk[
                self._current_offset:
                self._current_offset + copy_size
            ]

            self._current_offset += copy_size

            if copy_size < output_bytes:
                outdata[copy_size:] = (
                    b"\x00"
                    * (output_bytes - copy_size)
                )

    # --------------------------------------------------------
    # QUEUE
    # --------------------------------------------------------

    def enqueue(
        self,
        audio: bytes,
    ) -> None:

        if not audio:
            return

        if self._closed.is_set():
            return

        if self._interrupted.is_set():
            return

        self._queue.put(
            bytes(audio)
        )

    # --------------------------------------------------------
    # INTERRUPT
    # --------------------------------------------------------

    def interrupt(self) -> None:
        """
        Immediately silence the output and remove buffered audio.
        """

        self._interrupted.set()

        with self._lock:

            self._current_chunk = b""
            self._current_offset = 0

            while True:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break

        logger.info(
            "TTS playback interrupted."
        )

    # --------------------------------------------------------
    # RESUME
    # --------------------------------------------------------

    def resume(self) -> None:

        if self._closed.is_set():
            return

        self._interrupted.clear()

    # --------------------------------------------------------
    # STATE
    # --------------------------------------------------------

    @property
    def interrupted(self) -> bool:
        return self._interrupted.is_set()

    # --------------------------------------------------------
    # CLOSE
    # --------------------------------------------------------

    def close(self) -> None:

        if self._closed.is_set():
            return

        self._closed.set()

        self._interrupted.set()

        try:
            self._stream.abort()
        except Exception:
            pass

        try:
            self._stream.close()
        except Exception:
            pass

        with self._lock:

            self._current_chunk = b""
            self._current_offset = 0

            while True:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break

        logger.info(
            "TTS audio player closed."
        )


# ============================================================
# QUINCE CLIENT
# ============================================================


class QuinceClient:
    """
    Quince <-> Basket realtime voice client.

    Quince only talks to Basket.

    Responsibilities:
        - microphone capture
        - push-to-talk
        - WebSocket transport
        - local TTS playback
        - Ctrl+Q interruption
    """

    def __init__(self) -> None:

        self.loop: asyncio.AbstractEventLoop | None = None
        self.websocket: ClientConnection | None = None

        # ----------------------------------------------------
        # Audio
        # ----------------------------------------------------

        self.microphone_queue: queue.Queue[bytes] = queue.Queue()

        self.input_stream: sd.InputStream | None = None

        self.player = PCMPlayer(
            sample_rate=TTS_SAMPLE_RATE,
            channels=TTS_CHANNELS,
            blocksize=960,
        )

        # ----------------------------------------------------
        # State
        # ----------------------------------------------------

        self.recording = threading.Event()
        self.pipeline_busy = threading.Event()
        self.playback_started = threading.Event()

        # Once interrupted, we intentionally ignore all future
        # TTS chunks until the next user turn starts.
        self.playback_interrupted = threading.Event()

        self.shutdown_event = threading.Event()

        self._state_lock = threading.Lock()

        self._hotkey_latched = False
        self._hotkey_mode: str | None = None

        # ----------------------------------------------------
        # Pipeline text
        # ----------------------------------------------------

        self.llm_text_parts: list[str] = []

    # ========================================================
    # MICROPHONE
    # ========================================================

    def _microphone_callback(
        self,
        indata,
        frames: int,
        time_info,
        status,
    ) -> None:

        if status:
            logger.debug(
                "Microphone status: %s",
                status,
            )

        if not self.recording.is_set():
            return

        self.microphone_queue.put(
            bytes(indata)
        )

    def _open_microphone(self) -> None:

        logger.info(
            "Opening microphone..."
        )

        self.input_stream = sd.InputStream(
            samplerate=AUDIO_SAMPLE_RATE,
            channels=AUDIO_CHANNELS,
            dtype="int16",
            callback=self._microphone_callback,
            blocksize=960,
        )

        self.input_stream.start()

        logger.info(
            "Microphone ready: %s Hz mono PCM16",
            AUDIO_SAMPLE_RATE,
        )

    def _close_microphone(self) -> None:

        if self.input_stream is None:
            return

        try:
            self.input_stream.stop()
        except Exception:
            pass

        try:
            self.input_stream.close()
        except Exception:
            pass

        self.input_stream = None

    # ========================================================
    # QUEUE MANAGEMENT
    # ========================================================

    def _clear_microphone_queue(self) -> None:

        while True:
            try:
                self.microphone_queue.get_nowait()
            except queue.Empty:
                break

    # ========================================================
    # ASYNC BRIDGE
    # ========================================================

    def _schedule(
        self,
        coroutine,
    ) -> None:

        loop = self.loop

        if loop is None:
            return

        if loop.is_closed():
            return

        future = asyncio.run_coroutine_threadsafe(
            coroutine,
            loop,
        )

        def _done(fut) -> None:
            try:
                fut.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception(
                    "Scheduled Quince operation failed."
                )

        future.add_done_callback(
            _done
        )

    # ========================================================
    # HOTKEY
    # ========================================================

    def _keyboard_handler(
        self,
        event,
    ) -> None:

        name = (
            str(event.name)
            .lower()
            .strip()
        )

        ctrl_names = {
            "ctrl",
            "left ctrl",
            "right ctrl",
        }

        # ----------------------------------------------------
        # KEY DOWN
        # ----------------------------------------------------

        if event.event_type == "down":

            if name != "q":
                return

            if self._hotkey_latched:
                return

            if not keyboard.is_pressed("ctrl"):
                return

            self._hotkey_latched = True

            # ------------------------------------------------
            # Quince currently speaking / pipeline active
            # ------------------------------------------------

            if (
                self.pipeline_busy.is_set()
                and (
                    self.playback_started.is_set()
                    or not self.recording.is_set()
                )
            ):

                self._hotkey_mode = "interrupt"

                self._schedule(
                    self.interrupt_current_turn()
                )

                return

            # ------------------------------------------------
            # Start recording
            # ------------------------------------------------

            if not self.pipeline_busy.is_set():

                self._hotkey_mode = "record"

                self._schedule(
                    self.start_recording()
                )

                return

            self._hotkey_mode = "ignore"

            return

        # ----------------------------------------------------
        # KEY UP
        # ----------------------------------------------------

        if event.event_type != "up":
            return

        if name not in (
            {"q"}
            | ctrl_names
        ):
            return

        mode = self._hotkey_mode

        self._hotkey_mode = None
        self._hotkey_latched = False

        if mode != "record":
            return

        if self.recording.is_set():

            self._schedule(
                self.stop_recording()
            )

    # ========================================================
    # REGISTER HOTKEY
    # ========================================================

    def _install_keyboard_hook(self) -> None:

        keyboard.hook(
            self._keyboard_handler,
            suppress=False,
        )

    # ========================================================
    # START RECORDING
    # ========================================================

    async def start_recording(self) -> None:

        if self.recording.is_set():
            return

        if self.pipeline_busy.is_set():
            logger.info(
                "Cannot start recording: previous voice turn is still active."
            )
            return

        websocket = self.websocket

        if websocket is None:
            return

        self._clear_microphone_queue()

        self.llm_text_parts.clear()

        # New turn can play audio again.
        self.playback_interrupted.clear()
        self.player.resume()

        self.playback_started.clear()

        payload = {
            "type": "start",

            "prompt": STT_PROMPT,

            "stream": STT_STREAM,

            "sample_rate": AUDIO_SAMPLE_RATE,

            "llm": {
                "model": LLM_MODEL,
                "messages": LLM_MESSAGES,
                "temperature": LLM_TEMPERATURE,
                "top_p": LLM_TOP_P,
                "max_tokens": LLM_MAX_TOKENS,
                "stop": LLM_STOP,
                "seed": LLM_SEED,
                "system_prompt": LLM_SYSTEM_PROMPT,
                "abstracted": LLM_ABSTRACTED,
            },

            "tts": {
                "voice": TTS_VOICE,
                "temperature": TTS_TEMPERATURE,
            },
        }

        logger.info(
            "Sending START to Basket: %s",
            json.dumps(
                payload,
                ensure_ascii=False,
            ),
        )

        await websocket.send(
            json.dumps(payload)
        )

        self.pipeline_busy.set()
        self.recording.set()

        logger.info(
            "Recording started — release Ctrl+Q to stop."
        )

    # ========================================================
    # STOP RECORDING
    # ========================================================

    async def stop_recording(self) -> None:

        if not self.recording.is_set():
            return

        websocket = self.websocket

        self.recording.clear()

        logger.info(
            "Stopping microphone capture..."
        )

        if websocket is None:
            return

        await websocket.send(
            json.dumps(
                {
                    "type": "stop",
                }
            )
        )

        logger.info(
            "STOP sent to Basket — processing voice turn."
        )

    # ========================================================
    # INTERRUPT
    # ========================================================

    async def interrupt_current_turn(self) -> None:
        """
        Hard local playback interrupt.

        The local speaker becomes silent immediately.
        The cancel event is also sent to Basket.
        """

        if not self.pipeline_busy.is_set():
            return

        logger.info(
            "Ctrl+Q pressed during Quince response — interrupting."
        )

        self.playback_interrupted.set()

        self.playback_started.clear()

        self.player.interrupt()

        websocket = self.websocket

        if websocket is not None:

            try:
                await websocket.send(
                    json.dumps(
                        {
                            "type": "cancel",
                        }
                    )
                )

                logger.info(
                    "CANCEL sent to Basket."
                )

            except Exception:
                logger.exception(
                    "Failed to send CANCEL to Basket."
                )

    # ========================================================
    # MICROPHONE SENDER
    # ========================================================

    async def microphone_sender(
        self,
    ) -> None:

        logger.info(
            "Microphone -> WebSocket sender started"
        )

        while not self.shutdown_event.is_set():

            try:

                chunk = await asyncio.to_thread(
                    self.microphone_queue.get
                )

            except asyncio.CancelledError:
                raise

            if not self.recording.is_set():
                continue

            websocket = self.websocket

            if websocket is None:
                continue

            try:
                await websocket.send(
                    chunk
                )
            except Exception:
                logger.exception(
                    "Failed to send microphone audio."
                )
                return

    # ========================================================
    # RECEIVE LOOP
    # ========================================================

    async def receive_loop(
        self,
    ) -> None:

        websocket = self.websocket

        if websocket is None:
            return

        logger.info(
            "Basket receive loop started"
        )

        async for message in websocket:

            # ------------------------------------------------
            # BINARY TTS AUDIO
            # ------------------------------------------------

            if isinstance(
                message,
                bytes,
            ):

                if self.playback_interrupted.is_set():
                    continue

                self.player.enqueue(
                    message
                )

                self.playback_started.set()

                logger.debug(
                    "TTS binary audio received: %d bytes",
                    len(message),
                )

                continue

            # ------------------------------------------------
            # JSON
            # ------------------------------------------------

            try:

                event = json.loads(
                    message
                )

            except json.JSONDecodeError:

                logger.warning(
                    "Ignoring invalid Basket JSON message."
                )

                continue

            if not isinstance(
                event,
                dict,
            ):
                continue

            event_type = str(
                event.get(
                    "type",
                    "",
                )
            )

            data = event.get(
                "data"
            )

            # ------------------------------------------------
            # READY
            # ------------------------------------------------

            if event_type == "ready":

                logger.info(
                    "Basket READY: protocol=%s",
                    event.get(
                        "protocol"
                    ),
                )

                continue

            # ------------------------------------------------
            # STARTED
            # ------------------------------------------------

            if event_type == "started":

                logger.info(
                    "Basket STARTED voice turn"
                )

                continue

            # ------------------------------------------------
            # PIPELINE START
            # ------------------------------------------------

            if event_type == "pipeline.started":

                logger.info(
                    "VOICE PIPELINE STARTED"
                )

                continue

            # ------------------------------------------------
            # STT
            # ------------------------------------------------

            if event_type == "stt.started":

                logger.info(
                    "STT STARTED"
                )

                continue

            if event_type == "stt.partial":

                logger.info(
                    "STT PARTIAL: %s",
                    data,
                )

                continue

            if event_type == "stt.final":

                logger.info(
                    "STT FINAL: %r",
                    data,
                )

                continue

            # ------------------------------------------------
            # LLM
            # ------------------------------------------------

            if event_type == "llm.token":

                token = str(
                    data
                    or ""
                )

                self.llm_text_parts.append(
                    token
                )

                continue

            if event_type == "llm.final":

                final_text = str(
                    data
                    or ""
                ).strip()

                if final_text:
                    print(final_text)

                logger.info(
                    "LLM FINAL"
                )

                continue

            # ------------------------------------------------
            # TTS
            # ------------------------------------------------

            if event_type == "tts.started":

                logger.info(
                    "TTS STARTED: %r",
                    data,
                )

                continue

            if event_type == "tts.completed":

                logger.info(
                    "TTS COMPLETED"
                )

                continue

            # ------------------------------------------------
            # CANCELLED
            # ------------------------------------------------

            if event_type == "cancelled":

                logger.info(
                    "Basket confirmed cancellation."
                )

                self.recording.clear()
                self.pipeline_busy.clear()
                self.playback_started.clear()

                continue

            # ------------------------------------------------
            # PIPELINE COMPLETE
            # ------------------------------------------------

            if event_type == "pipeline.completed":

                self.recording.clear()
                self.pipeline_busy.clear()
                self.playback_started.clear()

                if self.playback_interrupted.is_set():

                    logger.info(
                        "VOICE PIPELINE COMPLETED after interruption."
                    )

                else:

                    logger.info(
                        "VOICE PIPELINE COMPLETED"
                    )

                continue

            # ------------------------------------------------
            # ERROR
            # ------------------------------------------------

            if event_type == "error":

                logger.error(
                    "Basket error: code=%s message=%s",
                    event.get(
                        "code"
                    ),
                    event.get(
                        "message"
                    ),
                )

                continue

            logger.debug(
                "Unhandled Basket event: %s",
                event,
            )

    # ========================================================
    # MAIN
    # ========================================================

    async def run(self) -> None:

        self.loop = asyncio.get_running_loop()

        self._open_microphone()

        self._install_keyboard_hook()

        logger.info(
            "Connecting to Basket: %s",
            BASKET_WS_URL,
        )

        try:

            async with websockets.connect(
                BASKET_WS_URL,
                ping_interval=WS_PING_INTERVAL,
                ping_timeout=WS_PING_TIMEOUT,
                max_size=WS_MAX_SIZE,
            ) as websocket:

                self.websocket = websocket

                logger.info(
                    "WebSocket connected."
                )

                logger.info(
                    "Push-to-talk active: hold %s",
                    PUSH_TO_TALK_HOTKEY,
                )

                sender_task = asyncio.create_task(
                    self.microphone_sender()
                )

                try:

                    await self.receive_loop()

                finally:

                    sender_task.cancel()

                    try:
                        await sender_task
                    except asyncio.CancelledError:
                        pass

        except KeyboardInterrupt:
            pass

        except Exception:
            logger.exception(
                "Quince WebSocket terminated."
            )

        finally:

            self.shutdown_event.set()

            self.recording.clear()
            self.pipeline_busy.clear()

            self.player.close()

            self._close_microphone()

            self.websocket = None


# ============================================================
# ENTRY POINT
# ============================================================


async def run_quince() -> None:

    client = QuinceClient()

    await client.run()