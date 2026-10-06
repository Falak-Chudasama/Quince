from quince_mcp.schemas.tool import QuinceTool

from .handlers import (
    _clear_clipboard,
    _get_clipboard_text,
    _get_cpu_usage,
    _get_cpu_temp,
    _get_ram_usage,
    _get_gpu_stats,
    _get_battery_level,
    _get_disk_usage,
    _get_network_status,
    _get_datetime,
    _get_running_processes,
    _next_track,
    _previous_track,
    _restart_system,
    _send_notification,
    _set_clipboard_text,
    _shut_down_system,
    _stop_media,
    _toggle_mute,
    _toggle_playback,
    _volume_down,
    _volume_up,
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

get_clipboard = QuinceTool(
    tool_id=f"{base_tool_id}--clipboard--get-clipboard",
    description=(
        "READ THE CURRENT WINDOWS TEXT CLIPBOARD. "
        "Use only when the user asks what is currently copied, what is on the clipboard, "
        "or asks Quince to read the clipboard contents. "
        "Do not use for clipboard history, files, or application content."
    ),
    handler=_get_clipboard_text
)

set_clipboard = QuinceTool(
    tool_id=f"{base_tool_id}--clipboard--set-clipboard",
    description=(
        "WRITE TEXT TO THE CURRENT WINDOWS CLIPBOARD. "
        "Use when the user explicitly asks to copy text, put text on the clipboard, "
        "or replace the clipboard contents with specified text. "
        "Only place the exact text that the user wants copied into the text argument."
    ),
    handler=_set_clipboard_text,
    arguments={
        "text": {
            "type": "string",
            "description": (
                "The exact text that should be placed on the Windows clipboard. "
                "Do not include quotation marks, explanations, or conversational framing."
            )
        }
    },
    required_arguments=["text"]
)

clear_clipboard = QuinceTool(
    tool_id=f"{base_tool_id}--clipboard--clear-clipboard",
    description=(
        "CLEAR THE CURRENT WINDOWS CLIPBOARD. "
        "Use only when the user explicitly asks to clear, empty, or erase the clipboard. "
        "Do not use for deleting files, notes, memories, or browser history."
    ),
    handler=_clear_clipboard
)

clipboard = QuinceTool(
    tool_id=f"{base_tool_id}--clipboard",
    description=(
        "WINDOWS CLIPBOARD CONTROL. "
        "Use for reading the current clipboard text, copying text to the clipboard, "
        "or clearing the clipboard. Do not use for clipboard history or unrelated computer data."
    ),
    kind="category",
    children=[
        get_clipboard,
        set_clipboard,
        clear_clipboard,
    ]
)

toggle_playback = QuinceTool(
    tool_id=f"{base_tool_id}--media--toggle-playback",
    description=(
        "TOGGLE THE CURRENT SYSTEM MEDIA PLAYBACK BETWEEN PLAYING AND PAUSED. "
        "Use when the user explicitly asks to play, pause, resume, or toggle the music/video/media currently controlled by Windows. "
        "Use this only for playback control, not for opening an application or searching for media."
    ),
    handler=_toggle_playback
)

next_track = QuinceTool(
    tool_id=f"{base_tool_id}--media--next-track",
    description=(
        "SKIP TO THE NEXT TRACK OR MEDIA ITEM USING THE WINDOWS MEDIA CONTROL. "
        "Use only when the user asks to play the next song, next track, next media item, or skip forward to the next item."
    ),
    handler=_next_track
)

previous_track = QuinceTool(
    tool_id=f"{base_tool_id}--media--previous-track",
    description=(
        "SKIP TO THE PREVIOUS TRACK OR MEDIA ITEM USING THE WINDOWS MEDIA CONTROL. "
        "Use only when the user asks for the previous song, previous track, previous media item, or go back to the prior item."
    ),
    handler=_previous_track
)

stop_media = QuinceTool(
    tool_id=f"{base_tool_id}--media--stop",
    description=(
        "SEND THE WINDOWS MEDIA STOP COMMAND. "
        "Use only when the user explicitly asks to stop the currently playing media. "
        "Do not use for closing an application or stopping a Windows process."
    ),
    handler=_stop_media
)

volume_up = QuinceTool(
    tool_id=f"{base_tool_id}--media--volume-up",
    description=(
        "INCREASE SYSTEM MEDIA VOLUME USING THE WINDOWS VOLUME CONTROL. "
        "Use only when the user explicitly asks to increase, raise, or turn up the system volume."
    ),
    handler=_volume_up
)

volume_down = QuinceTool(
    tool_id=f"{base_tool_id}--media--volume-down",
    description=(
        "DECREASE SYSTEM MEDIA VOLUME USING THE WINDOWS VOLUME CONTROL. "
        "Use only when the user explicitly asks to decrease, lower, or turn down the system volume."
    ),
    handler=_volume_down
)

toggle_mute = QuinceTool(
    tool_id=f"{base_tool_id}--media--toggle-mute",
    description=(
        "TOGGLE SYSTEM AUDIO MUTE USING THE WINDOWS VOLUME CONTROL. "
        "Use only when the user explicitly asks to mute, unmute, or toggle system audio mute."
    ),
    handler=_toggle_mute
)

media = QuinceTool(
    tool_id=f"{base_tool_id}--media",
    description=(
        "WINDOWS MEDIA AND AUDIO CONTROL. "
        "Use for explicit playback commands such as play/pause/resume, next track, previous track, stop media, "
        "increase or decrease system volume, or mute/unmute system audio. "
        "Do not use for opening media applications, searching media, or controlling unrelated application functions."
    ),
    kind="category",
    children=[
        toggle_playback,
        next_track,
        previous_track,
        stop_media,
        volume_up,
        volume_down,
        toggle_mute,
    ]
)

send_notification = QuinceTool(
    tool_id=f"{base_tool_id}--notifications--send-notification",
    description=(
        "SHOW A WINDOWS DESKTOP NOTIFICATION TO THE USER IMMEDIATELY. "
        "Use only when the user explicitly asks Quince to show, send, display, or pop up a notification. "
        "Do not use this tool as a substitute for a timer, reminder, email, or chat message. "
        "This tool sends the notification now; it does not schedule one for later."
    ),
    handler=_send_notification,
    arguments={
        "title": {
            "type": "string",
            "description": "Short notification title. Use only the title text, without quotation marks or extra framing."
        },
        "message": {
            "type": "string",
            "description": "Exact notification body to display. Do not add conversational framing."
        }
    },
    required_arguments=["title", "message"]
)

notifications = QuinceTool(
    tool_id=f"{base_tool_id}--notifications",
    description=(
        "WINDOWS DESKTOP NOTIFICATION CONTROL. "
        "Use only for immediate on-screen notifications explicitly requested by the user. "
        "Do not use for timers, reminders, messages, email, or alerts that should occur later."
    ),
    kind="category",
    children=[send_notification]
)

restart_system = QuinceTool(
    tool_id=f"{base_tool_id}--restart-system",
    description=(
        "IMMEDIATELY RESTART THIS WINDOWS COMPUTER. "
        "CALL THIS TOOL ONLY WHEN THE USER'S CURRENT REQUEST EXPLICITLY TELLS QUINCE TO RESTART OR REBOOT THE SYSTEM, PC, COMPUTER, OR WINDOWS. "
        "Do not call for restarting an application, service, process, session, or server. "
        "Do not call from vague requests such as 'start fresh', 'reset everything', 'fix the PC', or 'refresh'. "
        "The user must explicitly request a system or computer restart/reboot."
    ),
    handler=_restart_system,
    choice="required"
)

shut_down_system = QuinceTool(
    tool_id=f"{base_tool_id}--shut-down-system",
    description=(
        "IMMEDIATELY SHUT DOWN THIS WINDOWS COMPUTER. "
        "CALL THIS TOOL ONLY WHEN THE USER'S CURRENT REQUEST EXPLICITLY TELLS QUINCE TO SHUT DOWN, POWER OFF, OR TURN OFF THE SYSTEM, PC, COMPUTER, OR WINDOWS. "
        "Do not call for closing an application, stopping a process, logging out, sleeping, locking, or suspending the computer. "
        "Do not call from vague requests such as 'turn everything off' unless the user clearly refers to the computer/system. "
        "The user must explicitly request a system or computer shutdown/power-off."
    ),
    handler=_shut_down_system,
    choice="required"
)

system = QuinceTool(
    tool_id=base_tool_id,
    description=(
        "USE FOR DIRECT INTERACTION WITH THIS WINDOWS COMPUTER. "
        "Includes hardware telemetry such as CPU, RAM, GPU, VRAM, battery, disk, time, and running processes, "
        "plus clipboard control, media playback/audio control, desktop notifications, and explicit system restart or shutdown. "
        "Do not use for files, notes, web knowledge, Wikipedia, general internet information, or application-specific APIs. "
        "For restart and shutdown, require an explicit current user request to restart/reboot or shut down/power off the computer."
    ),
    kind="category",
    children=[
        clipboard,
        media,
        notifications,
        restart_system,
        shut_down_system,
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

    f"{base_tool_id}--clipboard": clipboard,
    f"{base_tool_id}--clipboard--get-clipboard": get_clipboard,
    f"{base_tool_id}--clipboard--set-clipboard": set_clipboard,
    f"{base_tool_id}--clipboard--clear-clipboard": clear_clipboard,

    f"{base_tool_id}--media": media,
    f"{base_tool_id}--media--toggle-playback": toggle_playback,
    f"{base_tool_id}--media--next-track": next_track,
    f"{base_tool_id}--media--previous-track": previous_track,
    f"{base_tool_id}--media--stop": stop_media,
    f"{base_tool_id}--media--volume-up": volume_up,
    f"{base_tool_id}--media--volume-down": volume_down,
    f"{base_tool_id}--media--toggle-mute": toggle_mute,

    f"{base_tool_id}--notifications": notifications,
    f"{base_tool_id}--notifications--send-notification": send_notification,

    f"{base_tool_id}--restart-system": restart_system,
    f"{base_tool_id}--shut-down-system": shut_down_system,

    f"{base_tool_id}--get-cpu-usage": get_cpu_usage,
    f"{base_tool_id}--get-cpu-temp": get_cpu_temp,
    f"{base_tool_id}--get-ram-usage": get_ram_usage,
    f"{base_tool_id}--get-gpu-stats": get_gpu_stats,
    f"{base_tool_id}--get-battery-level": get_battery_level,
    f"{base_tool_id}--get-disk-usage": get_disk_usage,
    f"{base_tool_id}--get-datetime": get_datetime,
    f"{base_tool_id}--get-running-processes": get_running_processes,
}
