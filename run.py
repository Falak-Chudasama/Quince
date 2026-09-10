from __future__ import annotations
import asyncio
import sys

from src.client import QuinceClient
from src.config import settings
from src.logging_setup import configure_logging, get_logger

logger = get_logger("run")


def main() -> None:
    configure_logging(settings.log_level)

    client = QuinceClient(settings)

    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user; shutting down.")
    except Exception:
        logger.exception("Quince exited due to an unhandled error.")
        sys.exit(1)


if __name__ == "__main__":
    main()
