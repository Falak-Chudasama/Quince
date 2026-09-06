from __future__ import annotations

"""
WebSocket connection to Basket.

The original client opened one connection and died the moment it
dropped. BasketConnection instead exposes connect()/reconnect_forever()
so the caller can keep the client alive across drops: on any
disconnect it retries with exponential backoff (capped) until either
it reconnects or the caller gives up.
"""

import asyncio

import websockets
from websockets.asyncio.client import ClientConnection

from src.config import BasketSettings
from src.errors import ConnectionFailedError, ConnectionLostError
from src.logging_setup import get_logger

logger = get_logger("transport.connection")


class BasketConnection:
    """Owns exactly one live websocket at a time, plus reconnect policy."""

    def __init__(self, settings: BasketSettings) -> None:
        self._settings = settings
        self._socket: ClientConnection | None = None

    @property
    def socket(self) -> ClientConnection | None:
        return self._socket

    @property
    def is_connected(self) -> bool:
        return self._socket is not None

    # ------------------------------------------------------------
    # SINGLE CONNECTION ATTEMPT
    # ------------------------------------------------------------

    async def connect_once(self) -> ClientConnection:
        """One connection attempt. Raises ConnectionFailedError on failure."""

        try:
            socket = await asyncio.wait_for(
                websockets.connect(
                    self._settings.ws_url,
                    ping_interval=self._settings.ping_interval,
                    ping_timeout=self._settings.ping_timeout,
                    max_size=self._settings.max_size,
                ),
                timeout=self._settings.connect_timeout,
            )

        except asyncio.TimeoutError as exc:
            raise ConnectionFailedError(
                f"Timed out connecting to Basket at {self._settings.ws_url}"
            ) from exc

        except OSError as exc:
            # Covers connection-refused, DNS failure, unreachable host, etc.
            raise ConnectionFailedError(f"Could not reach Basket: {exc}") from exc

        except websockets.exceptions.WebSocketException as exc:
            raise ConnectionFailedError(f"WebSocket handshake with Basket failed: {exc}") from exc

        self._socket = socket
        logger.info("Connected to Basket at %s", self._settings.ws_url)
        return socket

    # ------------------------------------------------------------
    # RECONNECT LOOP
    # ------------------------------------------------------------

    async def connect_with_retry(self, stop_event: asyncio.Event) -> ClientConnection | None:
        """
        Keep attempting to connect with exponential backoff until either
        it succeeds, stop_event is set, or reconnect_max_attempts is hit
        (0 means unlimited). Returns None if it gave up.
        """

        delay = self._settings.reconnect_initial_delay
        attempt = 0

        while not stop_event.is_set():
            attempt += 1

            try:
                return await self.connect_once()

            except ConnectionFailedError as exc:
                max_attempts = self._settings.reconnect_max_attempts

                if max_attempts and attempt >= max_attempts:
                    logger.error(
                        "Giving up connecting to Basket after %d attempts: %s",
                        attempt,
                        exc,
                    )
                    return None

                logger.warning(
                    "Basket connection attempt %d failed (%s). Retrying in %.1fs.",
                    attempt,
                    exc,
                    delay,
                )

                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=delay)
                    return None  # stop was requested while waiting
                except asyncio.TimeoutError:
                    pass  # normal backoff wait elapsed, try again

                delay = min(delay * self._settings.reconnect_backoff_factor, self._settings.reconnect_max_delay)

        return None

    # ------------------------------------------------------------
    # SEND / CLOSE
    # ------------------------------------------------------------

    async def send(self, message: str | bytes) -> None:
        """Send on the current socket. Raises ConnectionLostError on failure."""

        socket = self._socket
        if socket is None:
            raise ConnectionLostError("Attempted to send with no active Basket connection.")

        try:
            await socket.send(message)
        except websockets.exceptions.ConnectionClosed as exc:
            self._socket = None
            raise ConnectionLostError(f"Basket connection closed during send: {exc}") from exc

    async def close(self) -> None:
        socket, self._socket = self._socket, None
        if socket is not None:
            try:
                await socket.close()
            except Exception:
                logger.debug("Error closing Basket socket (ignored).", exc_info=True)
