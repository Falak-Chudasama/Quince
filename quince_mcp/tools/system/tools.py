from quince_mcp.schemas.tool import QuinceTool
from .handlers import (
    _get_cpu_usage,
    _get_ram_usage,
    _get_gpu_stats,
    _get_battery_level,
)

get_cpu_usage = QuinceTool(
    tool_id="root.system.get_cpu_usage",
    description=(
        "Returns current CPU usage/utilization as a percentage — not RAM or GPU. "
        "Use for 'CPU usage', 'processor usage', 'how busy is my CPU', 'CPU load'. "
        "If the user says 'RAM' or 'memory', use get_ram_usage instead; if they say "
        "'GPU' or 'VRAM', use get_gpu_stats instead."
    ),
    handler=_get_cpu_usage
)

get_ram_usage = QuinceTool(
    tool_id="root.system.get_ram_usage",
    description=(
        "Returns current SYSTEM RAM usage (used, available, total) — not GPU memory. "
        "Use for 'RAM', 'main memory', 'how much memory do I have'. If the user says "
        "'VRAM', 'graphics memory', or names the GPU, use get_gpu_stats instead."
    ),
    handler=_get_ram_usage
)

get_gpu_stats = QuinceTool(
    tool_id="root.system.get_gpu_stats",
    description=(
        "Returns GPU utilization, VRAM used/total, and temperature — GPU memory only, "
        "not system RAM (use get_ram_usage for that). Default gpu_name to 'all' unless "
        "the user explicitly names a GPU or says 'dedicated'/'main' GPU."
    ),
    handler=_get_gpu_stats,
    arguments={
        "gpu_name": {
            "type": "string",
            "description": (
                "Which GPU to query. Use 'all' whenever the question is generic "
                "('how's my GPU doing', 'GPU temp') — do not guess a specific name "
                "from an unspecific question. Only pass the exact GPU name if the "
                "user explicitly named it or said 'dedicated'/'main'."
            ),
            "enum": ["NVIDIA GeForce RTX 3050 Laptop GPU", "all"]
        }
    },
    required_arguments=["gpu_name"]
)

get_battery_level = QuinceTool(
    tool_id="root.system.get_battery_level",
    description=(
        "Returns battery percentage, charging/plugged-in state, and estimated time "
        "remaining if unplugged. Use only for battery/power questions specifically."
    ),
    handler=_get_battery_level
)

system = QuinceTool(
    tool_id="root.system",
    description=(
        "Use only for live hardware telemetry from THIS computer: current RAM usage, "
        "GPU usage/VRAM/temperature, or battery level/charging state. Not for general "
        "computer questions, installed software, or files. CPU, disk, and network usage "
        "have no tool yet — say so rather than picking one of these for them."
    ),
    kind="category",
    children=[get_ram_usage, get_gpu_stats, get_battery_level, get_cpu_usage]
)

system_tool_tree = {
    "root.system": system,
    "root.system.get_cpu_usage": get_cpu_usage,
    "root.system.get_ram_usage": get_ram_usage,
    "root.system.get_gpu_stats": get_gpu_stats,
    "root.system.get_battery_level": get_battery_level,
}