import ctypes
import json
import os
import platform
import shutil
import socket
import subprocess
import time
import urllib.request
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
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
        return {"available": False, "battery_available": False}

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


# ------------------------------------------------------------
# APPS & WINDOWS
# ------------------------------------------------------------

def _launch_app(app_name: str, arguments: str | None = None) -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("App launching requires Windows")

    app_map = {
        "calc": "calc.exe",
        "calculator": "calc.exe",
        "notepad": "notepad.exe",
        "editor": "notepad.exe",
        "code": "code",
        "vscode": "code",
        "chrome": "chrome.exe",
        "browser": "chrome.exe",
        "explorer": "explorer.exe",
        "files": "explorer.exe",
        "cmd": "cmd.exe",
        "terminal": "wt.exe",
        "powershell": "powershell.exe",
        "paint": "mspaint.exe",
        "task manager": "taskmgr.exe",
        "taskmgr": "taskmgr.exe",
        "settings": "ms-settings:",
        "control panel": "control.exe",
        "spotify": "spotify.exe",
    }

    target = app_map.get(app_name.lower().strip(), app_name.strip())

    try:
        if arguments:
            subprocess.Popen(f'"{target}" {arguments}', shell=True)
        else:
            try:
                os.startfile(target)
            except Exception:
                subprocess.Popen(f'"{target}"', shell=True)

        return {
            "launched": True,
            "app": app_name,
            "target": target,
            "arguments": arguments,
        }
    except Exception as exc:
        return {
            "launched": False,
            "app": app_name,
            "error": str(exc),
        }


def _kill_process(name_or_pid: str) -> dict[str, Any]:
    name_or_pid = name_or_pid.strip()
    killed = []

    if name_or_pid.isdigit():
        pid = int(name_or_pid)
        try:
            p = psutil.Process(pid)
            p_name = p.name()
            p.terminate()
            killed.append({"pid": pid, "name": p_name})
        except Exception as exc:
            return {"success": False, "error": f"Failed to terminate PID {pid}: {exc}"}
    else:
        target = name_or_pid.lower()
        target_exe = target if target.endswith(".exe") else target + ".exe"

        for proc in psutil.process_iter(attrs=["pid", "name"]):
            try:
                p_name = str(proc.info.get("name") or "").lower()
                if p_name in (target, target_exe):
                    proc.terminate()
                    killed.append({"pid": proc.info["pid"], "name": proc.info["name"]})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    return {
        "success": bool(killed),
        "target": name_or_pid,
        "terminated_count": len(killed),
        "processes": killed,
    }


def _get_active_window() -> dict[str, Any]:
    if os.name != "nt":
        return {"title": "", "error": "Windows only"}

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"title": "", "active": False}

    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)

    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process_name = ""
    try:
        process_name = psutil.Process(pid.value).name()
    except Exception:
        pass

    return {
        "title": buffer.value,
        "pid": pid.value,
        "process_name": process_name,
        "active": True,
    }


def _list_open_windows() -> dict[str, Any]:
    if os.name != "nt":
        return {"windows": [], "error": "Windows only"}

    user32 = ctypes.windll.user32
    windows = []

    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                title = buffer.value.strip()
                if title:
                    pid = ctypes.wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    pname = ""
                    try:
                        pname = psutil.Process(pid.value).name()
                    except Exception:
                        pass
                    windows.append({
                        "title": title,
                        "pid": pid.value,
                        "process_name": pname,
                    })
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

    return {
        "count": len(windows),
        "windows": windows,
    }


# ------------------------------------------------------------
# DISPLAY & SCREENSHOT
# ------------------------------------------------------------

def _take_screenshot(filename: str | None = None) -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("Screenshot requires Windows")

    pictures_dir = Path(os.environ.get("USERPROFILE", ".")) / "Pictures" / "Screenshots"
    pictures_dir.mkdir(parents=True, exist_ok=True)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
    else:
        filename = Path(filename).name
        if not filename.lower().endswith(".png"):
            filename += ".png"

    dest_path = pictures_dir / filename
    safe_dest = str(dest_path.resolve()).replace("'", "''")

    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
        "$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
        "$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height; "
        "$g = [System.Drawing.Graphics]::FromImage($bmp); "
        "$g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size); "
        f"$bmp.Save('{safe_dest}', [System.Drawing.Imaging.ImageFormat]::Png); "
        "$g.Dispose(); $bmp.Dispose(); "
        "$bounds.Width.ToString() + 'x' + $bounds.Height.ToString()"
    )

    res = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
        capture_output=True,
        text=True,
        timeout=10,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    res_str = res.stdout.strip()
    return {
        "success": dest_path.exists(),
        "path": str(dest_path),
        "resolution": res_str,
        "size_bytes": dest_path.stat().st_size if dest_path.exists() else 0,
    }


def _minimize_all_windows() -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("Minimize all requires Windows")

    subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", "(New-Object -ComObject Shell.Application).MinimizeAll()"],
        capture_output=True,
        timeout=5,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return {"minimized": True, "action": "show_desktop"}


def _get_display_info() -> dict[str, Any]:
    if os.name != "nt":
        return {"error": "Windows only"}

    user32 = ctypes.windll.user32
    w = user32.GetSystemMetrics(0)   # SM_CXSCREEN
    h = user32.GetSystemMetrics(1)   # SM_CYSCREEN
    monitors = user32.GetSystemMetrics(80)  # SM_CMONITORS
    vw = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
    vh = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN

    return {
        "primary_width": w,
        "primary_height": h,
        "monitor_count": monitors,
        "virtual_width": vw,
        "virtual_height": vh,
    }


# ------------------------------------------------------------
# POWER & SESSION
# ------------------------------------------------------------

def _lock_workstation() -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("Lock requires Windows")
    ctypes.windll.user32.LockWorkStation()
    return {"action": "lock_workstation", "locked": True}


def _sleep_system() -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("Sleep requires Windows")
    subprocess.Popen(
        ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return {"action": "sleep_system", "initiated": True}


def _get_system_uptime() -> dict[str, Any]:
    boot_time = psutil.boot_time()
    uptime_seconds = int(time.time() - boot_time)
    days, rem = divmod(uptime_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    return {
        "boot_time": datetime.fromtimestamp(boot_time).strftime("%Y-%m-%d %H:%M:%S"),
        "uptime_seconds": uptime_seconds,
        "uptime_human": f"{days}d {hours}h {minutes}m {seconds}s",
    }


def _get_os_info() -> dict[str, Any]:
    uname = platform.uname()
    return {
        "os": uname.system,
        "release": uname.release,
        "version": uname.version,
        "machine": uname.machine,
        "processor": uname.processor,
        "computer_name": os.environ.get("COMPUTERNAME", uname.node),
        "username": os.environ.get("USERNAME", ""),
    }


# ------------------------------------------------------------
# NETWORK & CONNECTIVITY
# ------------------------------------------------------------

def _get_ip_info() -> dict[str, Any]:
    hostname = socket.gethostname()
    local_ips = []
    try:
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ip not in local_ips and not ip.startswith("127."):
                local_ips.append(ip)
    except Exception:
        pass

    public_ip = "unavailable"
    try:
        req = urllib.request.Request("https://api.ipify.org?format=json", headers={"User-Agent": "Quince"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            public_ip = data.get("ip", "unavailable")
    except Exception:
        pass

    return {
        "hostname": hostname,
        "local_ips": local_ips,
        "public_ip": public_ip,
    }


def _ping_host(host: str, count: int = 3) -> dict[str, Any]:
    host = host.strip()
    res = subprocess.run(
        ["ping", "-n", str(count), host],
        capture_output=True,
        text=True,
        timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return {
        "host": host,
        "reachable": res.returncode == 0,
        "raw_output": res.stdout.strip(),
    }


def _check_internet() -> dict[str, Any]:
    endpoints = [("1.1.1.1", 53), ("8.8.8.8", 53)]
    reachable = False
    latency_ms = None

    for host, port in endpoints:
        try:
            t0 = time.perf_counter()
            s = socket.create_connection((host, port), timeout=2.5)
            s.close()
            latency_ms = round((time.perf_counter() - t0) * 1000, 1)
            reachable = True
            break
        except Exception:
            continue

    return {
        "internet_connected": reachable,
        "latency_ms": latency_ms,
    }


# ------------------------------------------------------------
# RUN COMMAND & ENVIRONMENT
# ------------------------------------------------------------

def _run_command(command: str, timeout_seconds: int = 15) -> dict[str, Any]:
    command = command.strip()
    if not command:
        return {"error": "Empty command"}

    try:
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return {
            "command": command,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip(),
            "return_code": res.returncode,
            "success": res.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "error": f"Command timed out after {timeout_seconds} seconds.",
            "success": False,
        }
    except Exception as exc:
        return {
            "command": command,
            "error": str(exc),
            "success": False,
        }


def _get_env_var(name: str) -> dict[str, Any]:
    name = name.strip()
    val = os.environ.get(name)
    return {
        "name": name,
        "value": val,
        "exists": val is not None,
    }


def _empty_recycle_bin() -> dict[str, Any]:
    """Empty the Windows Recycle Bin."""
    if os.name != "nt":
        return {"error": "Empty recycle bin requires Windows"}

    cmd = "Clear-RecycleBin -Confirm:$false -Force -ErrorAction SilentlyContinue"
    res = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cmd],
        capture_output=True,
        text=True,
        timeout=10,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return {
        "success": res.returncode == 0,
        "message": "Recycle Bin emptied successfully" if res.returncode == 0 else "Failed to empty Recycle Bin",
    }


def _get_wifi_status() -> dict[str, Any]:
    """Get active Wi-Fi connection info and nearby networks."""
    if os.name != "nt":
        return {"error": "Wi-Fi status requires Windows"}

    try:
        if_res = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if_text = if_res.stdout

        info: dict[str, Any] = {"connected": False}
        for line in if_text.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip()
                if k == "State":
                    info["state"] = v
                    info["connected"] = (v.lower() == "connected")
                elif k == "SSID":
                    info["ssid"] = v
                elif k == "Signal":
                    info["signal"] = v
                elif k == "Radio type":
                    info["radio_type"] = v
                elif k == "Band":
                    info["band"] = v
                elif k == "Channel":
                    info["channel"] = v
                elif k == "Receive rate (Mbps)":
                    info["receive_rate_mbps"] = v
                elif k == "Transmit rate (Mbps)":
                    info["transmit_rate_mbps"] = v

        # Nearby visible networks
        net_res = subprocess.run(
            ["netsh", "wlan", "show", "networks"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        ssids = []
        for line in net_res.stdout.splitlines():
            line_str = line.strip()
            if line_str.startswith("SSID") and ":" in line_str:
                ssid_name = line_str.split(":", 1)[1].strip()
                if ssid_name and ssid_name not in ssids:
                    ssids.append(ssid_name)

        info["nearby_networks"] = ssids
        return info
    except Exception as exc:
        return {"error": f"Failed to get Wi-Fi status: {exc}"}


def _set_volume_level(level: int) -> dict[str, Any]:
    """Set Windows master volume to a percentage (0 to 100)."""
    if os.name != "nt":
        return {"error": "Volume control requires Windows"}

    target = max(0, min(int(level), 100))
    user32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002
    VK_VOLUME_DOWN = 0xAE
    VK_VOLUME_UP = 0xAF

    # Zero out volume first (50 steps of 2%)
    for _ in range(50):
        user32.keybd_event(VK_VOLUME_DOWN, 0, 0, 0)
        user32.keybd_event(VK_VOLUME_DOWN, 0, KEYEVENTF_KEYUP, 0)

    # Step up to target (target // 2 steps)
    steps_up = target // 2
    for _ in range(steps_up):
        user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
        user32.keybd_event(VK_VOLUME_UP, 0, KEYEVENTF_KEYUP, 0)

    return {
        "target_volume_percent": target,
        "success": True,
    }


