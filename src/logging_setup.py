from __future__ import annotations

"""
Logging setup, called once from run.py before anything else starts.

Renders through Rich on the shared Quince console so every log line
picks up the brand theme (colored by level) instead of plain
logging.basicConfig text. Call sites are unchanged - this only swaps
the handler and formatter, so all existing logger.info/.warning/etc.
calls across the codebase get the new look for free.

Falls back to plain logging if rich isn't installed, so a missing
dependency degrades gracefully instead of preventing startup.
"""

import logging

_LEVEL_STYLE = {
    logging.DEBUG: "log.debug",
    logging.INFO: "log.info",
    logging.WARNING: "log.warning",
    logging.ERROR: "log.error",
    logging.CRITICAL: "log.critical",
}


def configure_logging(level: str = "INFO") -> None:
    resolved_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(resolved_level)

    # Idempotent: re-running configure_logging (e.g. in tests) shouldn't
    # stack duplicate handlers and double-print every line.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    try:
        root.addHandler(_rich_handler(resolved_level))
    except ImportError:
        logging.basicConfig(
            level=resolved_level,
            format="%(asctime)s %(levelname)-8s %(name)-22s %(message)s",
        )

    # Third-party libraries are noisy at INFO/DEBUG; keep them quiet
    # unless the user explicitly wants DEBUG on everything.
    if level.upper() != "DEBUG":
        logging.getLogger("websockets").setLevel(logging.WARNING)


def _rich_handler(level: int) -> logging.Handler:
    from rich.logging import RichHandler
    from rich.text import Text

    from src.ui.theme import console

    class _QuinceRichHandler(RichHandler):
        def render_message(self, record, message):
            style = _LEVEL_STYLE.get(record.levelno, "log.info")
            return Text(message, style=style)

    handler = _QuinceRichHandler(
        console=console,
        level=level,
        show_time=True,
        show_path=False,
        markup=False,
        rich_tracebacks=True,
        log_time_format="[%X]",
    )
    handler.setFormatter(logging.Formatter("%(name)-22s %(message)s"))
    return handler


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"quince.{name}")
