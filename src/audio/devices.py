from __future__ import annotations

import sounddevice as sd

from src.errors import AudioDeviceError
from src.logging_setup import get_logger

logger = get_logger("audio.devices")


def list_devices() -> list[dict]:
    return list(sd.query_devices())


def _host_api_name(device: dict) -> str:
    host_api_index = device.get("hostapi")
    if host_api_index is None:
        return ""

    try:
        return str(sd.query_hostapis(host_api_index).get("name", ""))
    except Exception:
        return ""


def _matches(device: dict, name_substring: str) -> bool:
    return name_substring.strip().lower() in str(device.get("name", "")).lower()


def _matches_host_api(device: dict, host_api_substring: str | None) -> bool:
    if not host_api_substring:
        return True

    return host_api_substring.strip().lower() in _host_api_name(device).lower()


def find_input_device(name_substring: str, host_api: str | None = None) -> int:
    matches: list[tuple[int, dict]] = []

    for index, device in enumerate(list_devices()):
        if device.get("max_input_channels", 0) <= 0:
            continue
        if not _matches(device, name_substring):
            continue
        if not _matches_host_api(device, host_api):
            continue
        matches.append((index, device))

    if not matches:
        raise AudioDeviceError(
            f"No input device matching name={name_substring!r}, host_api={host_api!r} was found."
        )

    index, device = matches[0]
    logger.info(
        "Resolved input device #%d: name=%r host_api=%r",
        index,
        device.get("name"),
        _host_api_name(device),
    )
    return index


def find_output_device(name_substring: str, host_api: str | None = None) -> int:
    matches: list[tuple[int, dict]] = []

    for index, device in enumerate(list_devices()):
        if device.get("max_output_channels", 0) <= 0:
            continue
        if not _matches(device, name_substring):
            continue
        if not _matches_host_api(device, host_api):
            continue
        matches.append((index, device))

    if not matches:
        raise AudioDeviceError(
            f"No output device matching name={name_substring!r}, host_api={host_api!r} was found."
        )

    index, device = matches[0]
    logger.info(
        "Resolved output device #%d: name=%r host_api=%r",
        index,
        device.get("name"),
        _host_api_name(device),
    )
    return index


def resolve_input_device(
    name_substring: str | None,
    fallback_to_default: bool,
    host_api: str | None = None,
) -> int | None:
    if not name_substring:
        logger.info("No input device pinned; using system default input.")
        return None

    try:
        return find_input_device(name_substring, host_api)
    except AudioDeviceError:
        if fallback_to_default:
            logger.warning(
                "Configured input device %r / host API %r not found; falling back to system default.",
                name_substring,
                host_api,
            )
            return None
        raise


def resolve_output_device(
    name_substring: str | None,
    fallback_to_default: bool,
    host_api: str | None = None,
) -> int | None:
    if not name_substring:
        logger.info("No output device pinned; using system default output.")
        return None

    try:
        return find_output_device(name_substring, host_api)
    except AudioDeviceError:
        if fallback_to_default:
            logger.warning(
                "Configured output device %r / host API %r not found; falling back to system default.",
                name_substring,
                host_api,
            )
            return None
        raise


def device_still_matches(
    device_index: int | None,
    name_substring: str | None,
    host_api: str | None = None,
) -> bool:
    if device_index is None or not name_substring:
        return True

    devices = list_devices()

    if device_index >= len(devices):
        return False

    device = devices[device_index]
    return _matches(device, name_substring) and _matches_host_api(device, host_api)
