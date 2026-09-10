from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from typing import Any

from quince_mcp.menu_node import MenuNode


def _safe_percent(value: float | None) -> float | None:
    try:
        return round(float(value), 1) if value is not None else None
    except (TypeError, ValueError):
        return None


def _read_gpu() -> dict[str, Any]:
    """Read NVIDIA GPU state through nvidia-smi without requiring a Python GPU package."""
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"available": False, "reason": "nvidia-smi not found"}

    query = (
        "name,utilization.gpu,utilization.memory,memory.total,memory.used,"
        "memory.free,temperature.gpu,power.draw,power.limit"
    )
    try:
        result = subprocess.run(
            [executable, "--query-gpu=" + query, "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2.5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "reason": str(exc)}

    if result.returncode != 0 or not result.stdout.strip():
        return {
            "available": False,
            "reason": (result.stderr or "nvidia-smi failed").strip(),
        }

    gpus: list[dict[str, Any]] = []
    fields = [field.strip() for field in query.split(",")]
    for line in result.stdout.splitlines():
        values = [value.strip() for value in line.split(",")]
        if len(values) != len(fields):
            continue

        def num(index: int, integer: bool = False):
            try:
                value = float(values[index])
                return int(value) if integer else round(value, 1)
            except (TypeError, ValueError):
                return None

        gpus.append({
            "name": values[0],
            "gpu_percent": num(1),
            "vram_percent": num(2),
            "vram_total_mb": num(3, integer=True),
            "vram_used_mb": num(4, integer=True),
            "vram_free_mb": num(5, integer=True),
            "temperature_c": num(6, integer=True),
            "power_w": num(7),
            "power_limit_w": num(8),
        })

    return {"available": bool(gpus), "gpus": gpus}


def _read_cpu_temperature() -> dict[str, Any]:
    """Best-effort Windows temperature read; unavailable sensors are not fatal."""
    if os.name != "nt":
        return {"available": False, "reason": "CPU temperature reader is Windows-specific"}

    scripts = [
        (
            "LibreHardwareMonitor",
            "Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor | "
            "Where-Object {$_.SensorType -eq 'Temperature'} | "
            "Select-Object Name,Value | ConvertTo-Json -Compress",
        ),
        (
            "OpenHardwareMonitor",
            "Get-CimInstance -Namespace root/OpenHardwareMonitor -ClassName Sensor | "
            "Where-Object {$_.SensorType -eq 'Temperature'} | "
            "Select-Object Name,Value | ConvertTo-Json -Compress",
        ),
        (
            "ACPI",
            "Get-CimInstance -Namespace root/wmi -Class MSAcpi_ThermalZoneTemperature | "
            "Select-Object InstanceName,CurrentTemperature | ConvertTo-Json -Compress",
        ),
    ]

    for source, script in scripts:
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode != 0 or not result.stdout.strip():
            continue
        try:
            import json
            payload = json.loads(result.stdout)
            if isinstance(payload, dict):
                payload = [payload]
            if not isinstance(payload, list):
                continue
            readings = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                if "Value" in item:
                    value = item.get("Value")
                    try:
                        value = round(float(value), 1)
                    except (TypeError, ValueError):
                        continue
                    readings.append({"name": item.get("Name", "temperature"), "temperature_c": value})
                elif "CurrentTemperature" in item:
                    try:
                        value = round((float(item["CurrentTemperature"]) / 10.0) - 273.15, 1)
                    except (TypeError, ValueError):
                        continue
                    readings.append({"name": item.get("InstanceName", "temperature"), "temperature_c": value})
            if readings:
                return {"available": True, "source": source, "readings": readings}
        except Exception:
            continue

    return {"available": False, "reason": "No supported CPU temperature sensor returned data"}


def _read_psutil() -> dict[str, Any]:
    try:
        import psutil
    except ImportError:
        return {"available": False, "reason": "psutil is not installed"}

    data: dict[str, Any] = {"available": True}
    try:
        data["cpu"] = {
            "usage_percent": _safe_percent(psutil.cpu_percent(interval=0.15)),
            "logical_cores": psutil.cpu_count(logical=True),
            "physical_cores": psutil.cpu_count(logical=False),
            "frequency_mhz": round(psutil.cpu_freq().current, 1) if psutil.cpu_freq() else None,
        }
    except Exception as exc:
        data["cpu_error"] = str(exc)

    try:
        vm = psutil.virtual_memory()
        data["ram"] = {
            "usage_percent": _safe_percent(vm.percent),
            "total_mb": round(vm.total / 1024**2),
            "used_mb": round(vm.used / 1024**2),
            "available_mb": round(vm.available / 1024**2),
        }
    except Exception as exc:
        data["ram_error"] = str(exc)

    try:
        swap = psutil.swap_memory()
        data["swap"] = {
            "usage_percent": _safe_percent(swap.percent),
            "total_mb": round(swap.total / 1024**2),
            "used_mb": round(swap.used / 1024**2),
            "free_mb": round(swap.free / 1024**2),
        }
    except Exception as exc:
        data["swap_error"] = str(exc)

    try:
        disks = {}
        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
            except (OSError, PermissionError):
                continue
            disks[partition.mountpoint] = {
                "usage_percent": _safe_percent(usage.percent),
                "total_gb": round(usage.total / 1024**3, 2),
                "used_gb": round(usage.used / 1024**3, 2),
                "free_gb": round(usage.free / 1024**3, 2),
            }
        data["disks"] = disks
    except Exception as exc:
        data["disk_error"] = str(exc)

    try:
        processes = []
        for proc in psutil.process_iter(["name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                processes.append({
                    "name": info.get("name") or "unknown",
                    "cpu_percent": _safe_percent(info.get("cpu_percent")),
                    "memory_percent": _safe_percent(info.get("memory_percent")),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        data["top_processes"] = sorted(
            processes,
            key=lambda item: (item.get("memory_percent") or 0.0, item.get("cpu_percent") or 0.0),
            reverse=True,
        )[:8]
    except Exception:
        pass

    try:
        data["network"] = {
            "bytes_sent_mb": round(psutil.net_io_counters().bytes_sent / 1024**2, 2),
            "bytes_received_mb": round(psutil.net_io_counters().bytes_recv / 1024**2, 2),
        }
    except Exception:
        pass

    try:
        data["uptime_seconds"] = max(0, int(time.time() - psutil.boot_time()))
    except Exception:
        pass

    try:
        battery = psutil.sensors_battery()
        if battery is not None:
            data["battery"] = {
                "percent": _safe_percent(battery.percent),
                "plugged_in": bool(battery.power_plugged),
            }
    except Exception:
        pass

    return data


def read_system_stats(scope: str = "all") -> dict[str, Any]:
    """Read current Windows system telemetry. Unknown/unavailable sensors return explicit status."""
    scope = (scope or "all").strip().lower()
    allowed = {"all", "cpu", "memory", "ram", "gpu", "vram", "temperature", "storage", "network", "battery", "processes"}
    if scope not in allowed:
        scope = "all"

    ps = _read_psutil()
    result: dict[str, Any] = {
        "ok": True,
        "host": platform.node(),
        "os": platform.platform(),
    }

    if scope in {"all", "cpu", "temperature"}:
        result["cpu"] = ps.get("cpu")
    if scope in {"all", "memory", "ram"}:
        result["ram"] = ps.get("ram")
        result["swap"] = ps.get("swap")
    if scope in {"all", "gpu", "vram", "temperature"}:
        result["gpu"] = _read_gpu()
    if scope in {"all", "temperature"}:
        result["cpu_temperature"] = _read_cpu_temperature()
    if scope in {"all", "storage"}:
        result["disks"] = ps.get("disks", {})
    if scope in {"all", "network"}:
        result["network"] = ps.get("network")
    if scope in {"all", "processes"}:
        result["top_processes"] = ps.get("top_processes", [])
    if scope in {"all", "battery"}:
        result["battery"] = ps.get("battery")
    if not ps.get("available"):
        result["warning"] = ps.get("reason", "psutil unavailable")

    return result


system_root = MenuNode(
    "system",
    "System",
    "Read live computer status such as CPU load, RAM, GPU/VRAM, temperatures, storage, network, battery, and uptime. Use this for vague questions like 'how is my PC doing?', 'how much memory?', 'GPU?', 'temperature?', or 'system stats'. Read-only: never changes system state.",
)

system_root.add_child(MenuNode(
    "stats",
    "System Stats",
    "Read current system telemetry. Use scope='all' for broad/vague status requests; otherwise select cpu, ram, gpu, vram, temperature, storage, network, or battery. Return unavailable sensors honestly instead of failing.",
    handler=read_system_stats,
    parameters={
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "enum": ["all", "cpu", "ram", "gpu", "vram", "temperature", "storage", "network", "battery", "processes"],
                "description": "Telemetry category. Prefer all when the user is vague.",
            }
        },
        "required": [],
    },
))
