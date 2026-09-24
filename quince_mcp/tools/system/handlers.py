import psutil
import pynvml
from typing import Any

# CPU
def _get_cpu_usage():
    usage = psutil.cpu_percent()

    return {
        "cpu_usage": usage,
        "cpu_name": "Ryzen 7 5800H",
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True)
    }

def _get_cpu_temp():
    # temp = psutil.cpu_stats()
    pass

# GPU
def _get_gpu_stats(gpu_name: str):
    pynvml.nvmlInit()

    try:
        gpu_count = pynvml.nvmlDeviceGetCount()
        gpus: list[dict[str, Any]] = []

        for i in range(gpu_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)

            name = pynvml.nvmlDeviceGetName(handle)

            if not (gpu_name == name or gpu_name == "all"):
                continue

            if isinstance(name, bytes):
                name = name.decode('utf-8', errors="replace")

            temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)

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
    pass

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