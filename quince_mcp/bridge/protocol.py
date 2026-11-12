"""
Bridge protocol helpers: message builders, parsers, and error codes.

NEVER write to stdout from this module.
"""
from __future__ import annotations

import uuid
from typing import Any


PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 2 * 1024 * 1024  # 2 MB


# ---------------------------------------------------------------------------
# Error codes — exact strings from Appendix A
# ---------------------------------------------------------------------------

class BridgeError(Exception):
    """Structured error from the bridge or extension."""

    def __init__(
        self,
        code: str,
        message: str = "",
        *,
        retryable: bool = False,
        data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or code)
        self.code = code
        self.bridge_message = message
        self.retryable = retryable
        self.data = data or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.bridge_message,
            "retryable": self.retryable,
            "data": self.data,
        }


# Retryable error codes
RETRYABLE_CODES = {
    "extension_not_connected",
    "bridge_timeout",
    "bridge_disconnected",
    "stale_ref",
    "offscreen",
}

# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------

def new_id() -> str:
    return str(uuid.uuid4())


def make_request(method: str, params: dict[str, Any], timeout_ms: int = 15000) -> dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "type": "request",
        "id": new_id(),
        "method": method,
        "params": params,
        "timeout_ms": timeout_ms,
    }


def make_response_ok(request_id: str, result: Any) -> dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "type": "response",
        "id": request_id,
        "ok": True,
        "result": result,
    }


def make_response_error(request_id: str, error: BridgeError) -> dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "type": "response",
        "id": request_id,
        "ok": False,
        "error": error.to_dict(),
    }


def make_ping(ts: int) -> dict[str, Any]:
    return {"v": PROTOCOL_VERSION, "type": "ping", "t": ts}


def make_pong(ts: int) -> dict[str, Any]:
    return {"v": PROTOCOL_VERSION, "type": "pong", "t": ts}


def make_hello_ack() -> dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "type": "hello_ack",
        "server": "quince-bridge",
        "protocol": PROTOCOL_VERSION,
        "session_policy": {"max_frame_bytes": MAX_FRAME_BYTES},
    }


# ---------------------------------------------------------------------------
# Parsing / validation
# ---------------------------------------------------------------------------

def parse_message(raw: str) -> dict[str, Any]:
    """Parse a JSON text frame. Raises BridgeError on format errors."""
    import json
    try:
        msg = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise BridgeError("invalid_message", f"JSON parse error: {exc}") from exc
    if not isinstance(msg, dict):
        raise BridgeError("invalid_message", "Message must be a JSON object")
    if msg.get("v") != PROTOCOL_VERSION:
        raise BridgeError(
            "version_mismatch",
            f"Protocol version mismatch: expected {PROTOCOL_VERSION}, got {msg.get('v')}",
        )
    return msg


def parse_error_from_response(response: dict[str, Any]) -> BridgeError:
    """Extract a BridgeError from a non-ok response."""
    err = response.get("error", {})
    if not isinstance(err, dict):
        err = {}
    code = err.get("code", "unknown_error")
    return BridgeError(
        code=code,
        message=err.get("message", ""),
        retryable=err.get("retryable", code in RETRYABLE_CODES),
        data=err.get("data") or {},
    )
