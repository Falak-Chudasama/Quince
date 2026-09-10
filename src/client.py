from __future__ import annotations
import asyncio
import json
import queue
import threading
import websockets
from rich.markup import escape

from src.audio.microphone import Microphone
from src.audio.player import PCMPlayer
from src.audio.watchdog import run_device_watchdog
from src.config import Settings
from src.errors import AudioStreamError, ConnectionLostError
from src.input.hotkey import PushToTalkHotkey
from src.logging_setup import get_logger
from src.transport.connection import BasketConnection
from src.transport.event_handler import BasketEventHandler
from src.transport.protocol import build_cancel_message, build_start_message, build_stop_message
from src.ui.status import StatusLine, print_banner
from src.ui.theme import console
from quince_mcp.root_mcp import build_root
from quince_mcp.server import MCPServer

logger = get_logger("client")


class QuinceClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

        self._loop: asyncio.AbstractEventLoop | None = None

        self.microphone = Microphone(settings.audio)
        self.player = PCMPlayer(settings.tts, settings.audio)
        self.connection = BasketConnection(settings.basket)
        self.status = StatusLine()
        self.mcp_server = MCPServer(
            build_root(settings.basket.api_url),
            host=settings.mcp.host,
            port=settings.mcp.port,
        )

        # ----------------------------------------------------
        # Turn state
        # ----------------------------------------------------
        self._recording = threading.Event()
        self._pipeline_busy = threading.Event()
        self._playback_active = threading.Event()
        self._playback_interrupted = threading.Event()
        self._shutdown = asyncio.Event()

        self._turn_token = 0
        self._pending_cancel_token: int | None = None

        self._llm_text_parts: list[str] = []

        self.event_handler = BasketEventHandler(
            self.player,
            on_turn_finished=self._on_turn_finished,
            on_cancelled=self._on_cancelled,
            on_llm_token=self._llm_text_parts.append,
            on_llm_final=self._on_llm_final,
        )

        self.hotkey = PushToTalkHotkey(
            record_key=self._settings.input.push_to_talk_hotkey.split("+")[-1].strip(),
            on_should_start_recording=lambda: self._schedule(self._start_recording()),
            on_should_stop_recording=lambda: self._schedule(self._stop_recording()),
            on_should_interrupt_and_record=lambda: self._schedule(self._interrupt_and_start_recording()),
            is_pipeline_busy=self._pipeline_busy.is_set,
            is_playback_active=self._playback_active.is_set,
            is_recording=self._recording.is_set,
        )

    # ================================================================
    # ASYNC BRIDGE (hotkey callbacks fire on a non-asyncio thread)
    # ================================================================

    def _schedule(self, coroutine) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        future = asyncio.run_coroutine_threadsafe(coroutine, loop)

        def _log_if_failed(fut) -> None:
            try:
                fut.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Scheduled Quince operation failed.")

        future.add_done_callback(_log_if_failed)

    # ================================================================
    # TURN LIFECYCLE
    # ================================================================

    async def _start_recording(self) -> None:
        if self._recording.is_set() or self._pipeline_busy.is_set():
            logger.info("Ignoring start: already recording or previous turn still active.")
            return

        if not self.connection.is_connected:
            logger.warning("Cannot start recording: not connected to Basket.")
            return

        self._turn_token += 1
        turn_token = self._turn_token

        self.microphone.enable()
        self._llm_text_parts.clear()
        self._playback_interrupted.clear()
        self.player.resume()
        self._playback_active.clear()

        message = build_start_message(
            stt=self._settings.stt,
            llm=self._settings.llm,
            tts=self._settings.tts,
            sample_rate=self._settings.audio.sample_rate,
        )

        try:
            await self.connection.send(json.dumps(message))
        except ConnectionLostError:
            logger.warning("Lost connection to Basket while starting a turn.")
            self.microphone.disable()
            return

        if turn_token != self._turn_token:
            # Superseded by a newer interrupt-and-record press while
            # this send was in flight; let the newer turn own the state.
            return

        self._pipeline_busy.set()
        self._recording.set()
        self.status.set(turn="recording")
        logger.info("TURN START token=%d")
        logger.info("Recording — release %s to stop.", self._settings.input.push_to_talk_hotkey)

    async def _stop_recording(self) -> None:
        if not self._recording.is_set():
            return

        self._recording.clear()
        self.microphone.disable()

        try:
            await self.connection.send(json.dumps(build_stop_message()))
            self.status.set(turn="thinking")
            logger.info("TURN AUDIO COMPLETE — Basket processing")
        except ConnectionLostError:
            logger.warning("Lost connection to Basket while stopping a turn.")
            self._pipeline_busy.clear()
            self.status.set(turn="idle")

    async def _interrupt_and_start_recording(self) -> None:
        """
        One press-and-hold, two effects: whatever Quince is doing right
        now (speaking or still mid-pipeline) is cut off immediately,
        and the mic starts capturing the new prompt in the same motion
        — no need to release and press again.

        Turn state is reset locally and synchronously rather than
        waiting for Basket's "cancelled" acknowledgement, so the new
        recording starts the instant the key goes down instead of
        after a network round trip. The cancel message is still sent
        so Basket drops the old turn server-side too.
        """

        if self._pipeline_busy.is_set():
            logger.info("Interrupting current Quince turn to start a new one.")
            self._playback_interrupted.set()
            self.player.interrupt()
            self._pending_cancel_token = self._turn_token

            try:
                await self.connection.send(json.dumps(build_cancel_message()))
            except ConnectionLostError:
                logger.debug("Could not send cancel (already disconnected).")

            # Mirror _on_turn_finished's cleanup immediately instead of
            # waiting for the server's "cancelled" event, so the guard
            # at the top of _start_recording doesn't block the new turn.
            self._recording.clear()
            self._pipeline_busy.clear()
            self._playback_active.clear()
            self.microphone.disable()

        await self._start_recording()

    def _on_turn_finished(self) -> None:
        self._recording.clear()
        self._pipeline_busy.clear()
        self._playback_active.clear()
        self.microphone.disable()
        self.status.set(turn="idle")

    def _on_cancelled(self) -> None:
        # A "cancelled" ack can arrive after the user has already
        # pressed-and-held again, which locally starts a brand new
        # turn without waiting for this ack (see
        # _interrupt_and_start_recording). By that point self._turn_token
        # has already advanced, so a token captured when the cancel was
        # *sent* tells us whether this ack is for a turn that's still
        # current or one that's since been superseded.
        if self._pending_cancel_token is not None and self._pending_cancel_token != self._turn_token:
            logger.debug("Ignoring stale cancellation for a superseded turn.")
            self._pending_cancel_token = None
            return
        self._pending_cancel_token = None
        self._on_turn_finished()

    def _on_llm_final(self, text: str) -> None:
        # The spoken output is the actual TTS audio arriving as binary
        # frames; this is printed purely for visibility/debugging.
        # Escaped because `text` is arbitrary LLM output and may itself
        # contain bracket sequences that would otherwise be parsed as
        # (and potentially break on) Rich markup.
        console.print(f"  [quince.secondary]▸[/] [quince.dim]{escape(text)}[/]")

    # ================================================================
    # MICROPHONE -> BASKET
    # ================================================================

    async def _microphone_sender(self) -> None:
        logger.info("MICROPHONE STREAM START")

        while not self._shutdown.is_set():
            try:
                chunk = await asyncio.to_thread(self.microphone.queue.get, True, 0.5)
            except queue.Empty:
                continue  # nothing captured in this window; re-check shutdown and retry

            if not self.microphone.is_enabled or not self.connection.is_connected:
                continue

            try:
                await self.connection.send(chunk)
            except ConnectionLostError:
                logger.warning("Lost connection to Basket while sending microphone audio.")
                # Do not return: the outer reconnect loop will re-establish
                # the connection and this task will resume sending once
                # is_connected is true again.
                continue

    # ================================================================
    # BASKET -> CLIENT
    # ================================================================

    async def _receive_loop(self) -> None:
        socket = self.connection.socket
        if socket is None:
            return

        logger.info("Basket receive loop started.")

        try:
            async for message in socket:
                if isinstance(message, bytes):
                    logger.debug("AUDIO RX bytes=%d", len(message))
                    self.event_handler.handle_binary(
                        message,
                        playback_interrupted=self._playback_interrupted.is_set(),
                    )
                    if not self._playback_interrupted.is_set():
                        if not self._playback_active.is_set():
                            self.status.set(turn="speaking")
                        self._playback_active.set()
                    continue

                logger.debug("EVENT RX %r", message)
                event = self.event_handler.handle_text(message)

                if event is not None and event.type == "started":
                    self._playback_active.clear()

        except websockets.exceptions.ConnectionClosed as exc:
            raise ConnectionLostError(f"Basket connection closed: {exc}") from exc

        # The async iterator also ends silently (no exception) on a
        # clean, server-initiated close — e.g. Basket restarting or
        # closing the socket normally. That is still a disconnection
        # from the client's point of view and must trigger the same
        # reconnect path as an abrupt drop, not be mistaken for a
        # locally-requested shutdown.
        if not self._shutdown.is_set():
            raise ConnectionLostError("Basket closed the connection.")

    # ================================================================
    # ONE CONNECTED SESSION
    # ================================================================

    async def _run_session(self) -> None:
        """
        Runs the sender + receiver for exactly one live connection.
        Returns normally on clean shutdown, raises ConnectionLostError
        if the socket drops so the caller can reconnect.

        The receive loop blocks on the socket and will not wake up on
        its own when a shutdown is requested, so it is raced against
        the shutdown event here; whichever finishes first decides the
        outcome, and the loser is cancelled.
        """

        sender_task = asyncio.create_task(self._microphone_sender())
        receive_task = asyncio.create_task(self._receive_loop())
        shutdown_task = asyncio.create_task(self._shutdown.wait())

        try:
            done, pending = await asyncio.wait(
                {receive_task, shutdown_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            if shutdown_task in done and receive_task not in done:
                # Shutdown was requested while still connected: close the
                # socket ourselves so nothing is left half-open, and
                # return normally (this is not a disconnection).
                await self.connection.close()
                return

            # receive_task finished first: propagate whatever it raised
            # (ConnectionLostError) or its normal return (shutdown was
            # already set by the time it noticed).
            receive_task.result()

        finally:
            sender_task.cancel()
            try:
                await sender_task
            except asyncio.CancelledError:
                pass

            # A dropped connection mid-turn should not leave the UI
            # thinking Quince is still recording or speaking.
            self._recording.clear()
            self._pipeline_busy.clear()
            self._playback_active.clear()
            self.microphone.disable()
            self.status.set(turn="idle")

    # ================================================================
    # MAIN LOOP
    # ================================================================

    async def run(self) -> None:
        self._loop = asyncio.get_running_loop()

        print_banner(
            hotkey=self._settings.input.push_to_talk_hotkey,
            ws_url=self._settings.basket.ws_url,
            voice=self._settings.tts.voice,
        )

        try:
            self.microphone.open()
            self.player.open()
            await self.mcp_server.start()
            logger.info("MCP SERVER STARTED host=%s port=%d", self._settings.mcp.host, self._settings.mcp.port)
        except AudioStreamError:
            logger.exception("Fatal audio setup failure; Quince cannot start.")
            return

        self.hotkey.install()
        self.status.start()
        self.status.set(turn="idle", connection="connecting")

        watchdog_task = asyncio.create_task(
            run_device_watchdog(self.microphone, self.player, self._settings.audio, self._shutdown)
        )

        try:
            while not self._shutdown.is_set():
                self.status.set(connection="connecting")
                socket = await self.connection.connect_with_retry(self._shutdown)

                if socket is None:
                    self.status.set(connection="disconnected")
                    logger.error("Could not connect to Basket; Quince is shutting down.")
                    break

                self.status.set(connection="connected")
                logger.info("Push-to-talk active: hold %s", self._settings.input.push_to_talk_hotkey)

                try:
                    await self._run_session()
                    # _run_session only returns cleanly on shutdown.
                    break

                except ConnectionLostError as exc:
                    self.status.set(turn="idle", connection="disconnected")
                    logger.warning("%s — attempting to reconnect.", exc)
                    await self.connection.close()
                    if not self._settings.basket.reconnect:
                        break
                    continue

        finally:
            self._shutdown.set()
            watchdog_task.cancel()
            try:
                await watchdog_task
            except asyncio.CancelledError:
                pass

            self.hotkey.uninstall()
            await self.mcp_server.stop()
            await self.connection.close()
            self.player.close()
            self.microphone.close()
            self.status.set(turn="idle", connection="disconnected")
            self.status.stop()
            logger.info("Quince client shut down cleanly.")

    def request_shutdown(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._shutdown.set)
