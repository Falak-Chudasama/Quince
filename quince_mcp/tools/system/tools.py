from quince_mcp.schemas.tool import QuinceTool

from .handlers import (
    _get_cpu_usage,
    _get_cpu_temp,
    _get_ram_usage,
    _get_gpu_stats,
    _get_battery_level,
    _get_disk_usage,
    _get_network_status,
    _get_datetime,
    _get_running_processes,
)


base_tool_id = "root--system"


get_cpu_usage = QuinceTool(
    tool_id=f"{base_tool_id}--get-cpu-usage",
    description=(
        "Returns current CPU usage/utilization as a percentage and CPU core count. "
        "Use for CPU usage, processor usage, CPU load, or how busy the CPU is. "
        "Do not use for CPU temperature, RAM, GPU, or VRAM."
    ),
    handler=_get_cpu_usage
)

get_cpu_temp = QuinceTool(
    tool_id=f"{base_tool_id}--get-cpu-temp",
    description=(
        "Returns the current CPU temperature in Celsius. "
        "Use only when the user asks about CPU temperature, processor temperature, "
        "CPU thermals, or how hot the CPU is. Do not use for CPU usage."
    ),
    handler=_get_cpu_temp
)

get_ram_usage = QuinceTool(
    tool_id=f"{base_tool_id}--get-ram-usage",
    description=(
        "Returns current SYSTEM RAM usage including used, available, total, and usage percentage. "
        "Use for RAM, system memory, main memory, available memory, or how much memory the computer has. "
        "Do not use for VRAM or GPU memory."
    ),
    handler=_get_ram_usage
)

get_gpu_stats = QuinceTool(
    tool_id=f"{base_tool_id}--get-gpu-stats",
    description=(
        "Returns GPU utilization, GPU temperature, VRAM usage, VRAM capacity, and GPU memory utilization. "
        "Use for GPU usage, GPU temperature, VRAM, graphics memory, or GPU memory questions. "
        "Use 'all' for generic GPU questions and use the exact GPU name only when the user explicitly identifies a GPU."
    ),
    handler=_get_gpu_stats,
    arguments={
        "gpu_name": {
            "type": "string",
            "description": (
                "Which GPU to query. Use 'all' for generic GPU questions such as GPU usage, "
                "GPU temperature, or VRAM usage. Use the exact GPU name only when the user "
                "explicitly identifies a GPU or requests the dedicated/main GPU."
            ),
            "enum": ["NVIDIA GeForce RTX 3050 Laptop GPU", "all"]
        }
    },
    required_arguments=["gpu_name"]
)

get_battery_level = QuinceTool(
    tool_id=f"{base_tool_id}--get-battery-level",
    description=(
        "Returns current battery percentage, charging or plugged-in state, and estimated "
        "remaining battery time when available. Use only for battery level, battery status, "
        "charging, plugged-in, or remaining battery questions."
    ),
    handler=_get_battery_level
)

get_disk_usage = QuinceTool(
    tool_id=f"{base_tool_id}--get-disk-usage",
    description=(
        "Returns disk usage for a drive including total, used, free, and usage percentage. "
        "Use when the user asks about storage space, disk space, free space, used space, "
        "or how much space remains on a drive."
    ),
    handler=_get_disk_usage,
    arguments={
        "drive": {
            "type": "string",
            "description": (
                "Drive or filesystem path to inspect, such as 'C:\\\\' or 'D:\\\\'. "
                "If the user does not specify a drive, use the system drive."
            )
        }
    },
    required_arguments=[]
)

get_datetime = QuinceTool(
    tool_id=f"{base_tool_id}--get-datetime",
    description=(
        "Returns the current local date, time, timezone, UTC offset, and ISO timestamp of this computer. "
        "Use when the user asks for the current date, current time, local time, timezone, or today's date."
    ),
    handler=_get_datetime
)

get_running_processes = QuinceTool(
    tool_id=f"{base_tool_id}--get-running-processes",
    description=(
        "Returns currently running processes on this computer including process ID, name, and status. "
        "Use when the user asks what programs or processes are running, whether a process is running, "
        "or asks to find a specific running process."
    ),
    handler=_get_running_processes,
    arguments={
        "filter_name": {
            "type": "string",
            "description": (
                "Optional case-insensitive process name filter. Use it when the user asks "
                "about a specific process or application; otherwise omit it."
            )
        }
    },
    required_arguments=[]
)

system = QuinceTool(
    tool_id=base_tool_id,
    description=(
        "Use for live system and hardware telemetry from THIS computer, including CPU usage, "
        "CPU temperature, RAM usage, GPU usage, GPU temperature, VRAM usage, battery status, "
        "disk usage, network interface status, current date and time, and running processes. "
        "Do not use for files, installed applications, application control, web information, or general computer questions."
    ),
    kind="category",
    children=[
        get_ram_usage,
        get_gpu_stats,
        get_battery_level,
        get_cpu_usage,
        get_cpu_temp,
        get_disk_usage,
        get_datetime,
        get_running_processes
    ]
)

system_tool_tree = {
    f"{base_tool_id}": system,

    f"{base_tool_id}--get-cpu-usage": get_cpu_usage,
    f"{base_tool_id}--get-cpu-temp": get_cpu_temp,
    f"{base_tool_id}--get-ram-usage": get_ram_usage,
    f"{base_tool_id}--get-gpu-stats": get_gpu_stats,
    f"{base_tool_id}--get-battery-level": get_battery_level,
    f"{base_tool_id}--get-disk-usage": get_disk_usage,
    f"{base_tool_id}--get-datetime": get_datetime,
    f"{base_tool_id}--get-running-processes": get_running_processes,
}