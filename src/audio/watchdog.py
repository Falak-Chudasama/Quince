from __future__ import annotations

"""
Device pinning is only useful if it survives the session. Windows can
still change what's plugged in after Quince has already opened its
streams (headset reconnects, USB mic replugged). This watchdog polls
both streams periodically and reopens whichever one has drifted off
its pinned device, so the mic-vs-output split holds for the whole run,
not just at startup.
"""

import asyncio

from src.audio.microphone import Microphone
from src.audio.player import PCMPlayer
from src.config import AudioSettings
from src.logging_setup import get_logger

logger = get_logger("audio.watchdog")


async def run_device_watchdog(
    microphone: Microphone,
    player: PCMPlayer,
    settings: AudioSettings,
    stop_event: asyncio.Event,
) -> None:
    """Runs until stop_event is set. Safe to cancel at any point."""

    interval = settings.device_watchdog_interval

    if interval <= 0:
        logger.info("Device watchdog disabled (interval <= 0).")
        return

    logger.info("Device watchdog started (checking every %.1fs).", interval)

    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break  # stop_event was set
        except asyncio.TimeoutError:
            pass  # normal tick, fall through to the check below

        try:
            if not microphone.device_still_valid():
                microphone.reopen()
        except Exception:
            logger.exception("Failed to recover microphone device.")

        try:
            if not player.device_still_valid():
                player.reopen()
        except Exception:
            logger.exception("Failed to recover TTS playback device.")

    logger.info("Device watchdog stopped.")
