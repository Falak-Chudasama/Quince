from __future__ import annotations

import asyncio

from src.client import QuinceClient
from src.config import settings


if __name__ == "__main__":
    asyncio.run(QuinceClient(settings).run())
