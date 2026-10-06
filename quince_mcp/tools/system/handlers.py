import ctypes
import os
import shutil
import subprocess
from ctypes import wintypes
from datetime import datetime
from typing import Any

import psutil
import pynvml
import wmi

# CPU
def _get_cpu_usage():
    usage = psutil.cpu_percent(interval=0.1)

    return {
        "cpu_usage": usage,
        "cpu_name": "Ryzen 7 5800H",
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True)
    }

def _get_cpu_temp():
    hwmon = wmi.WMI(namespace=r"root\LibreHardwareMonitor")

    sensors = hwmon.Sensor(SensorType="Temperature")

    temperatures = []

    for sensor in sensors:
        parent = str(getattr(sensor, "Parent", "") or "")
        name = str(getattr(sensor, "Name", "") or "")
        value = getattr(sensor, "Value", None)

        if value is None:
            continue

        if "amdcpu" not in parent.lower():
            continue

        temperatures.append({
            "name": name,
            "temperature_c": float(value)
        })

    preferred_names = (
        "Core (Tctl/Tdie)",
        "Core (Tdie)",
        "Core (Tctl)",
    )

    primary = None

    for preferred_name in preferred_names:
        for sensor in temperatures:
            if sensor["name"] == preferred_name:
                primary = sensor
                break

        if primary is not None:
            break

    return {
        "available": bool(temperatures),
        "temperature_c": primary["temperature_c"] if primary else None,
        "sensor": primary["name"] if primary else None,
        "sensors": temperatures
    }

# GPU
def _get_gpu_stats(gpu_name: str):
    pynvml.nvmlInit()

    try:
        gpu_count = pynvml.nvmlDeviceGetCount()
        gpus: list[dict[str, Any]] = []

        for i in range(gpu_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)

            name = pynvml.nvmlDeviceGetName(handle)

            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")

            if not (gpu_name == name or gpu_name == "all"):
                continue

            temperature = pynvml.nvmlDeviceGetTemperature(
                handle,
                pynvml.NVML_TEMPERATURE_GPU
            )

            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)

            memory = pynvml.nvmlDeviceGetMemoryInfo(handle)

            gpus.append({
                "gpu_name": name,
                "gpu_temperature": temperature,
                "gpu_usage_percent": utilization.gpu,
                "gpu_memory_percent": utilization.memory,
                "vram_total_bytes": memory.total,
                "vram_used_bytes": memory.used,
                "vram_free_bytes": memory.free,
                "vram_usage_percent": (
                    memory.used / memory.total * 100
                    if memory.total
                    else 0.0
                ),
            })

        return {
            "gpu_count": gpu_count,
            "gpus": gpus
        }

    finally:
        pynvml.nvmlShutdown()

# MEMORY
def _get_ram_usage():
    memory = psutil.virtual_memory()

    return {
        "total_bytes": memory.total,
        "used_bytes": memory.used,
        "available_bytes": memory.available,
        "usage_percent": memory.percent
    }

# NETWORK
def _get_network_status():
    interface_stats = psutil.net_if_stats()
    interface_addresses = psutil.net_if_addrs()

    interfaces = []

    for name, stats in interface_stats.items():
        addresses = []

        for address in interface_addresses.get(name, []):
            addresses.append({
                "family": str(address.family),
                "address": address.address,
                "netmask": address.netmask,
                "broadcast": address.broadcast
            })

        interfaces.append({
            "name": name,
            "is_up": stats.isup,
            "speed_mbps": stats.speed,
            "mtu": stats.mtu,
            "addresses": addresses
        })

    return {
        "interfaces": interfaces
    }

# BATTERY
def _get_battery_level():
    battery = psutil.sensors_battery()

    if battery is None:
        return { "battery_available": False }

    seconds_left = battery.secsleft

    if seconds_left in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN):
        seconds_left = None

    return {
        "available": True,
        "percent": battery.percent,
        "plugged_in": battery.power_plugged,
        "seconds_left": seconds_left,
    }

# DISK
def _get_disk_usage(drive: str | None = None):
    if not drive:
        drive = os.environ.get("SystemDrive", "C:") + "\\"

    usage = psutil.disk_usage(drive)

    return {
        "path": drive,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "usage_percent": usage.percent
    }

# DATETIME
def _get_datetime():
    now = datetime.now().astimezone()

    return {
        "iso": now.isoformat(),
        "date": now.date().isoformat(),
        "time": now.strftime("%H:%M:%S"),
        "timezone": now.tzname(),
        "utc_offset": now.strftime("%z")
    }

# PROCESSES
def _get_running_processes(filter_name: str | None = None):
    filter_normalized = filter_name.lower() if filter_name else None

    processes = []

    for process in psutil.process_iter(
        attrs=["pid", "name", "status"],
        ad_value=None
    ):
        info = process.info
        name = info.get("name")

        if filter_normalized:
            if not name or filter_normalized not in name.lower():
                continue

        processes.append({
            "pid": info.get("pid"),
            "name": name,
            "status": info.get("status")
        })

    return {
        "processes": processes,
        "count": len(processes),
        "filter": filter_name
    }


def _open_clipboard():
    if os.name != "nt":
        raise RuntimeError("Clipboard tools require Windows")

    user32 = ctypes.windll.user32

    for _ in range(10):
        if user32.OpenClipboard(None):
            return user32
        ctypes.windll.kernel32.Sleep(50)

    raise OSError("Unable to open the Windows clipboard")


def _get_clipboard_text():
    user32 = _open_clipboard()
    kernel32 = ctypes.windll.kernel32

    try:
        CF_UNICODETEXT = 13
        handle = user32.GetClipboardData(CF_UNICODETEXT)

        if not handle:
            return {
                "text": "",
                "has_text": False
            }

        ptr = kernel32.GlobalLock(handle)

        if not ptr:
            raise OSError("Unable to lock clipboard data")

        try:
            text = ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)

        return {
            "text": text,
            "has_text": bool(text)
        }
    finally:
        user32.CloseClipboard()


def _set_clipboard_text(text: str):
    if os.name != "nt":
        raise RuntimeError("Clipboard tools require Windows")

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    data = text.encode("utf-16-le") + b"\x00\x00"
    handle = None

    user32 = _open_clipboard()

    try:
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))

        if not handle:
            raise MemoryError("Unable to allocate clipboard memory")

        ptr = kernel32.GlobalLock(handle)

        if not ptr:
            raise OSError("Unable to lock clipboard memory")

        try:
            ctypes.memmove(ptr, data, len(data))
        finally:
            kernel32.GlobalUnlock(handle)

        if not user32.EmptyClipboard():
            raise OSError("Unable to clear the existing clipboard")

        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            raise OSError("Unable to set clipboard data")

        handle = None

        return {
            "copied": True,
            "characters": len(text)
        }
    finally:
        if handle:
            kernel32.GlobalFree(handle)
        user32.CloseClipboard()


def _clear_clipboard():
    user32 = _open_clipboard()

    try:
        if not user32.EmptyClipboard():
            raise OSError("Unable to clear the clipboard")

        return {
            "cleared": True
        }
    finally:
        user32.CloseClipboard()


def _send_media_key(virtual_key: int, action: str):
    if os.name != "nt":
        raise RuntimeError("Media controls require Windows")

    user32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002

    user32.keybd_event(virtual_key, 0, 0, 0)
    user32.keybd_event(virtual_key, 0, KEYEVENTF_KEYUP, 0)

    return {
        "action": action,
        "sent": True
    }


def _toggle_playback():
    return _send_media_key(0xB3, "toggle_playback")


def _next_track():
    return _send_media_key(0xB0, "next")


def _previous_track():
    return _send_media_key(0xB1, "previous")


def _stop_media():
    return _send_media_key(0xB2, "stop")


def _volume_up():
    return _send_media_key(0xAF, "volume_up")


def _volume_down():
    return _send_media_key(0xAE, "volume_down")


def _toggle_mute():
    return _send_media_key(0xAD, "toggle_mute")


def _send_notification(title: str, message: str):
    if os.name != "nt":
        raise RuntimeError("Notifications require Windows")

    powershell = shutil.which("powershell.exe") or shutil.which("powershell")

    if not powershell:
        raise RuntimeError("Windows PowerShell was not found")

    safe_title = title.replace("'", "''").replace("\r", " ").replace("\n", " ")
    safe_message = message.replace("'", "''").replace("\r", " ").replace("\n", " ")

    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        "$n.Visible = $true; "
        f"$n.BalloonTipTitle = '{safe_title}'; "
        f"$n.BalloonTipText = '{safe_message}'; "
        "$n.ShowBalloonTip(5000); "
        "Start-Sleep -Milliseconds 5500; "
        "$n.Visible = $false; "
        "$n.Dispose()"
    )

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    subprocess.Popen(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-WindowStyle",
            "Hidden",
            "-Command",
            script
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags
    )

    return {
        "sent": True,
        "title": title,
        "message": message
    }


def _restart_system():
    if os.name != "nt":
        raise RuntimeError("System restart requires Windows")

    subprocess.Popen(
        ["shutdown", "/r", "/t", "0", "/f"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )

    return {
        "action": "restart_system",
        "initiated": True
    }


def _shut_down_system():
    if os.name != "nt":
        raise RuntimeError("System shutdown requires Windows")

    subprocess.Popen(
        ["shutdown", "/s", "/t", "0", "/f"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )

    return {
        "action": "shut_down_system",
        "initiated": True
    }
