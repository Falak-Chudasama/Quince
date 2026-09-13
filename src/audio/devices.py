from __future__ import annotations
import sounddevice as sd

from src.errors import AudioDeviceError
from src.logging_setup import get_logger

logger = get_logger("audio.devices")


def list_devices() -> list[dict]:
    return list(sd.query_devices())


def _matches(device: dict, name_substring: str) -> bool:
    return name_substring.strip().lower() in str(device.get("name", "")).lower()


def find_input_device(name_substring: str) -> int:
    """
    Return the device index of the first input-capable device whose
    name contains `name_substring`. Raises AudioDeviceError if none
    match, so callers can decide whether to fall back or fail loudly.
    """

    for index, device in enumerate(list_devices()):
        if device.get("max_input_channels", 0) > 0 and _matches(device, name_substring):
            return index

    raise AudioDeviceError(f"No input device matching {name_substring!r} was found.")


def find_output_device(name_substring: str) -> int:
    """Same as find_input_device, but for output-capable devices."""

    for index, device in enumerate(list_devices()):
        if device.get("max_output_channels", 0) > 0 and _matches(device, name_substring):
            return index

    raise AudioDeviceError(f"No output device matching {name_substring!r} was found.")


def resolve_input_device(name_substring: str | None, fallback_to_default: bool) -> int | None:
    """
    Resolve which device index to hand to sd.InputStream.

    Returns None to mean "let PortAudio use the system default" — this
    is only chosen deliberately, either because no pin was configured
    or because the pin failed and fallback is allowed.
    """

    if not name_substring:
        logger.info("No input device pinned; using system default input.")
        return None

    try:
        index = find_input_device(name_substring)
        logger.info("Pinned microphone input to device #%d (%r).", index, name_substring)
        return index

    except AudioDeviceError:
        if fallback_to_default:
            logger.warning(
                "Configured input device %r not found; falling back to system default.",
                name_substring,
            )
            return None
        raise


def resolve_output_device(name_substring: str | None, fallback_to_default: bool) -> int | None:
    """Same as resolve_input_device, but for the TTS playback device."""

    if not name_substring:
        logger.info("No output device pinned; using system default output.")
        return None

    try:
        index = find_output_device(name_substring)
        logger.info("Pinned TTS playback to device #%d (%r).", index, name_substring)
        return index

    except AudioDeviceError:
        if fallback_to_default:
            logger.warning(
                "Configured output device %r not found; falling back to system default.",
                name_substring,
            )
            return None
        raise


def device_still_matches(device_index: int | None, name_substring: str | None) -> bool:
    """
    Used by the watchdog to detect that a pinned device index no longer
    points at the device we expect (it was unplugged and the OS reused
    the index for something else, or the device list shifted).
    """

    if device_index is None or not name_substring:
        return True

    devices = list_devices()

    if device_index >= len(devices):
        return False

    return _matches(devices[device_index], name_substring)
