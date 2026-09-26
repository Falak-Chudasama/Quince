import os
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