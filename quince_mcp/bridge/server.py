"""
ExtensionBridge — WebSocket server that the Chrome extension connects to.

Design constraints:
- Runs in a DAEMON thread with its OWN asyncio event loop (never the MCP loop).
- The MCP loop calls bridge.call() which bridges across loops via asyncio.run_coroutine_threadsafe.
- Binds to 127.0.0.1 ONLY.
- Only one extension connection at a time; new authenticated connection replaces old.
- NEVER writes to stdout.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import threading
import time
from asyncio import AbstractEventLoop, Future
from typing import Any, Callable

from websockets.asyncio.server import ServerConnection, serve

from quince_mcp.bridge.config import BridgeSettings
from quince_mcp.bridge.protocol import (
    BridgeError,
    MAX_FRAME_BYTES,
    PROTOCOL_VERSION,
    make_hello_ack,
    make_ping,
    make_pong,
    make_request,
    parse_error_from_response,
    parse_message,
)
from quince_mcp.utils.logging_setup import get_logger

logger = get_logger("bridge")

# Default per-method timeout_ms values
_DEFAULT_TIMEOUTS: dict[str, int] = {
    "session.begin": 5000,
    "session.end": 5000,
    "tabs.list": 20000,
    "tabs.open": 20000,
    "tabs.switch": 20000,
    "tabs.use_current": 20000,
    "tabs.close": 20000,
    "tabs.navigate": 20000,
    "page.snapshot": 8000,
    "page.find": 8000,
    "page.read_text": 8000,
    "act.click": 15000,
    "act.type": 15000,
    "act.press_key": 15000,
    "act.scroll": 15000,
    "act.select": 15000,
    "act.set_checked": 15000,
    "act.hover": 15000,
    "act.fill_form": 15000,
    "bridge.status": 5000,
}


class ExtensionBridge:
    """
    Manages the WebSocket server and the single active extension connection.
    """

    def __init__(self) -> None:
        self._settings: BridgeSettings | None = None
        self._loop: AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # State
        self.state: str = "not_started"  # starting|listening|connected|unavailable:<reason>
        self._connection: ServerConnection | None = None
        self._connection_lock: asyncio.Lock | None = None  # created on the bridge loop

        self.connected_info: dict[str, Any] = {}
        self.paused: bool = False
        self.controlled_tab_ids: list[int] = []

        # Pending call futures keyed by request id
        self._pending: dict[str, Future[dict[str, Any]]] = {}

        # Event callbacks: name -> list of callables
        self._event_callbacks: dict[str, list[Callable[..., Any]]] = {}

    # ------------------------------------------------------------------
    # Public API (called from the MCP loop)
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self.state == "connected"

    def on_event(self, name: str, fn: Callable[..., Any]) -> None:
        self._event_callbacks.setdefault(name, []).append(fn)

    async def call(self, method: str, params: dict[str, Any], *, timeout: float = 15.0) -> dict[str, Any]:
        """
        Call a method on the extension and await the result.
        Bridges the MCP asyncio loop to the bridge loop.
        """
        if not self.is_connected:
            raise BridgeError("extension_not_connected", "The browser extension isn't connected.")

        if self._loop is None:
            raise BridgeError("bridge_unavailable", "Bridge loop is not running.")

        fut = asyncio.run_coroutine_threadsafe(
            self._call(method, params, timeout),
            self._loop,
        )
        try:
            return await asyncio.wrap_future(fut)
        except BridgeError:
            raise
        except Exception as exc:
            raise BridgeError("internal_error", str(exc)) from exc

    # ------------------------------------------------------------------
    # Internal: bridge loop side
    # ------------------------------------------------------------------

    async def _call(self, method: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
        if self._connection is None:
            raise BridgeError("extension_not_connected", "No extension connected.")

        timeout_ms = _DEFAULT_TIMEOUTS.get(method, int(timeout * 1000))
        if method == "act.wait":
            timeout_ms = int(params.get("seconds", 5)) * 1000 + 5000

        msg = make_request(method, params, timeout_ms=timeout_ms)
        request_id = msg["id"]

        loop = asyncio.get_running_loop()
        fut: Future[dict[str, Any]] = loop.create_future()
        self._pending[request_id] = fut

        try:
            raw = json.dumps(msg)
            if len(raw.encode()) > MAX_FRAME_BYTES:
                raise BridgeError("invalid_argument", "Request frame too large.")
            await self._connection.send(raw)
            return await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            raise BridgeError(
                "bridge_timeout",
                "The browser didn't answer in time. Try again or choose another approach.",
                retryable=True,
            )
        except BridgeError:
            self._pending.pop(request_id, None)
            raise
        except Exception as exc:
            self._pending.pop(request_id, None)
            raise BridgeError("internal_error", str(exc)) from exc

    def _fail_pending(self, reason: str) -> None:
        """Fail all pending futures with bridge_disconnected (called on bridge loop)."""
        err = BridgeError("bridge_disconnected", "The browser connection dropped.", retryable=True)
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(err)
        self._pending.clear()

    async def _send_raw(self, data: dict[str, Any]) -> None:
        if self._connection is not None:
            try:
                await self._connection.send(json.dumps(data))
            except Exception:
                pass

    async def _dispatch_event(self, event_name: str, params: dict[str, Any]) -> None:
        cbs = self._event_callbacks.get(event_name, [])
        for cb in cbs:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(params)
                else:
                    cb(params)
            except Exception as exc:
                logger.warning("Event callback error for %s: %s", event_name, exc)

    # ------------------------------------------------------------------
    # WebSocket handler (one per connection, on bridge loop)
    # ------------------------------------------------------------------

    async def _handle_connection(self, ws: ServerConnection) -> None:
        # Step 1: Validate Origin header.
        origin = ws.request.headers.get("Origin", "")
        if not origin.startswith("chrome-extension://"):
            logger.warning("Rejected connection: bad Origin %r", origin)
            await ws.close(4401, "Unauthorized: invalid origin")
            return

        ext_id = self._settings.extension_id if self._settings else ""
        if ext_id and origin != f"chrome-extension://{ext_id}":
            logger.warning("Rejected connection: extension id mismatch %r", origin)
            await ws.close(4401, "Unauthorized: extension id mismatch")
            return

        # Step 2: Await hello within 5 s.
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Rejected connection: hello timeout")
            await ws.close(4401, "Unauthorized: hello timeout")
            return

        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            hello = json.loads(raw)
        except Exception:
            await ws.close(4401, "Unauthorized: bad hello")
            return

        if hello.get("type") != "hello" or hello.get("v") != PROTOCOL_VERSION:
            # Check for version mismatch specifically.
            if hello.get("v") != PROTOCOL_VERSION:
                await ws.close(4426, "Upgrade required")
                return
            await ws.close(4401, "Unauthorized: bad hello type")
            return

        # Step 3: Validate token (constant-time).
        token_env = self._settings.token if self._settings else ""
        token_in = hello.get("token", "")
        if not hmac.compare_digest(token_env.encode(), token_in.encode()):
            logger.warning("Rejected connection: token mismatch (source not logged)")
            await ws.close(4401, "Unauthorized: token mismatch")
            return

        # Step 4: Replace existing connection.
        async with self._connection_lock:  # type: ignore[union-attr]
            old = self._connection
            if old is not None:
                logger.info("Replacing existing extension connection")
                self._fail_pending("replaced")
                try:
                    await old.close(4001, "replaced")
                except Exception:
                    pass
            self._connection = ws
            self.state = "connected"
            self.connected_info = {
                "version": hello.get("version", ""),
                "browser": hello.get("browser", ""),
                "capabilities": hello.get("capabilities", []),
                "since": time.time(),
            }

        logger.info(
            "Extension connected: version=%s browser=%s",
            hello.get("version", "?"),
            hello.get("browser", "?"),
        )

        # Step 5: Send hello_ack.
        await ws.send(json.dumps(make_hello_ack()))

        # Step 6: Emit bridge.ready event.
        await self._dispatch_event("bridge.ready", {"version": hello.get("version", "")})

        # Step 7: Track last received time for server-side ping.
        last_recv = time.time()
        server_ping_interval = 30.0
        server_ping_timeout = 10.0
        pending_ping_ts: float | None = None

        async def _server_ping_task() -> None:
            nonlocal last_recv, pending_ping_ts
            while True:
                await asyncio.sleep(5.0)
                now = time.time()
                if pending_ping_ts is not None:
                    # Waiting for pong.
                    if now - pending_ping_ts > server_ping_timeout:
                        logger.warning("Extension ping timeout; closing connection")
                        await ws.close(1011, "ping timeout")
                        return
                elif now - last_recv > server_ping_interval:
                    pending_ping_ts = now
                    await self._send_raw(make_ping(int(now * 1000)))

        ping_task = asyncio.create_task(_server_ping_task())

        try:
            async for raw_msg in ws:
                if isinstance(raw_msg, bytes):
                    raw_msg = raw_msg.decode("utf-8")

                last_recv = time.time()

                if len(raw_msg.encode("utf-8")) > MAX_FRAME_BYTES:
                    logger.warning("Oversized frame from extension (%d bytes); closing", len(raw_msg.encode()))
                    await ws.close(1009, "frame too large")
                    break

                try:
                    msg = json.loads(raw_msg)
                except Exception:
                    logger.warning("Bad JSON from extension; ignoring")
                    continue

                msg_type = msg.get("type")

                if msg_type == "pong":
                    pending_ping_ts = None
                    continue

                if msg_type == "ping":
                    await self._send_raw(make_pong(msg.get("t", 0)))
                    continue

                if msg_type == "response":
                    request_id = msg.get("id")
                    fut = self._pending.pop(request_id, None) if request_id else None
                    if fut and not fut.done():
                        if msg.get("ok"):
                            fut.set_result(msg.get("result", {}))
                        else:
                            fut.set_exception(parse_error_from_response(msg))
                    continue

                if msg_type == "event":
                    event_name = msg.get("event", "")
                    event_params = msg.get("params", {})
                    logger.debug("Event from extension: %s", event_name)
                    asyncio.create_task(self._dispatch_event(event_name, event_params))
                    continue

                logger.debug("Unknown message type %r from extension; ignoring", msg_type)

        except Exception as exc:
            logger.info("Extension connection closed: %s", exc)
        finally:
            ping_task.cancel()
            async with self._connection_lock:  # type: ignore[union-attr]
                if self._connection is ws:
                    self._connection = None
                    self.state = "listening"
                    self._fail_pending("disconnected")
                    self.connected_info = {}
            logger.info("Extension disconnected; bridge back to listening")
            await self._dispatch_event("bridge.disconnected", {})

    # ------------------------------------------------------------------
    # Server lifecycle (bridge loop)
    # ------------------------------------------------------------------

    async def _run_server(self, settings: BridgeSettings) -> None:
        self._settings = settings
        self._connection_lock = asyncio.Lock()

        try:
            ws_server = await serve(
                self._handle_connection,
                settings.host,
                settings.port,
                max_size=MAX_FRAME_BYTES,
                ping_interval=None,   # we do application-level pings
                close_timeout=2,
                open_timeout=10,
            )
            self.state = "listening"
            logger.info(
                "Bridge listening on ws://%s:%d/ (token_source=%s, risk_gate=%s)",
                settings.host,
                settings.port,
                "env" if "QUINCE_BRIDGE_TOKEN" in __import__("os").environ else "file",
                settings.risk_gate,
            )
            await ws_server.serve_forever()
        except OSError as exc:
            if "address already in use" in str(exc).lower() or exc.errno in (98, 10048):
                reason = "port_in_use"
            else:
                reason = f"os_error:{exc.errno}"
            self.state = f"unavailable:{reason}"
            logger.warning("Bridge could not start: %s — %s", reason, exc)

    def _run_loop(self, settings: BridgeSettings) -> None:
        """Entry point for the bridge daemon thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        max_restarts = 5
        restart_window = 60.0
        restart_times: list[float] = []

        while True:
            try:
                loop.run_until_complete(self._run_server(settings))
            except Exception as exc:
                logger.error("Bridge loop crashed: %s", exc, exc_info=True)

            now = time.time()
            restart_times = [t for t in restart_times if now - t < restart_window]
            if len(restart_times) >= max_restarts:
                logger.error("Bridge exceeded %d restarts/minute; giving up", max_restarts)
                self.state = "unavailable:too_many_restarts"
                break
            restart_times.append(now)
            logger.info("Bridge restarting in 2 s...")
            time.sleep(2)

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def start(self, settings: BridgeSettings) -> None:
        with self._lock:
            if self._thread is not None:
                return  # already started
            self.state = "starting"
            t = threading.Thread(
                target=self._run_loop,
                args=(settings,),
                daemon=True,
                name="QuinceBridgeThread",
            )
            self._thread = t
            t.start()

    def stop(self) -> None:
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)


# ---------------------------------------------------------------------------
# Module-level singleton + start_bridge()
# ---------------------------------------------------------------------------

bridge = ExtensionBridge()
_start_lock = threading.Lock()
_started = False


def start_bridge() -> ExtensionBridge:
    """
    Idempotent: call once at import time of handlers.py.
    Starts the bridge in a daemon thread if not already running.
    """
    global _started
    with _start_lock:
        if _started:
            return bridge

        try:
            from quince_mcp.bridge.config import BridgeSettings
            settings = BridgeSettings.from_env()
        except Exception as exc:
            logger.error("Bridge settings error: %s — bridge will be unavailable", exc)
            bridge.state = "unavailable:config_error"
            _started = True
            return bridge

        if not settings.enabled:
            logger.info("Bridge disabled by QUINCE_BRIDGE_ENABLED=false")
            bridge.state = "unavailable:disabled"
            _started = True
            return bridge

        bridge.start(settings)
        _started = True
        return bridge
