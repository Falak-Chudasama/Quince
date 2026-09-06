from __future__ import annotations

"""
Exception hierarchy for Quince.

Every error the client can raise on purpose is one of these, so
callers can catch narrowly instead of bare `except Exception`.
"""


class QuinceError(Exception):
    """Base class for all Quince client errors."""


# ============================================================
# AUDIO
# ============================================================


class AudioDeviceError(QuinceError):
    """A requested audio device could not be found or opened."""


class AudioStreamError(QuinceError):
    """The mic input stream or speaker output stream failed at runtime."""


# ============================================================
# TRANSPORT
# ============================================================


class ConnectionFailedError(QuinceError):
    """Could not establish a WebSocket connection to Basket."""


class ConnectionLostError(QuinceError):
    """An established WebSocket connection dropped unexpectedly."""


class ProtocolError(QuinceError):
    """Basket sent a message that violates the expected protocol shape."""
