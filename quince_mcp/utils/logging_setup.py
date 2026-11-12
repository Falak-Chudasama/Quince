"""
Logging setup for quince_mcp.

CRITICAL: All output goes to stderr and/or a rotating log file.
NEVER use stdout — the MCP server speaks JSON-RPC over stdio and
a single stray print() will corrupt the protocol.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(
    name: str = "quince_mcp",
    level: int = logging.INFO,
    log_file: Path | None = None,
) -> logging.Logger:
    """
    Configure and return a logger that writes to stderr (and optionally a file).
    Safe to call multiple times (idempotent — checks for existing handlers).
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        # Already configured; return as-is.
        return logger

    logger.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # stderr handler — always present
    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setFormatter(fmt)
    logger.addHandler(stderr_handler)

    # Optional file handler — off by default; enabled when log_file is given.
    if log_file is not None:
        try:
            from logging.handlers import RotatingFileHandler

            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=2 * 1024 * 1024,  # 2 MB
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(fmt)
            logger.addHandler(file_handler)
        except OSError as exc:
            logger.warning("Could not open log file %s: %s", log_file, exc)

    # Prevent propagation to the root logger (which might go to stdout in some
    # environments).
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the quince_mcp hierarchy."""
    return logging.getLogger(f"quince_mcp.{name}")


# Module-level setup on first import — stderr only, INFO level.
setup_logging()
