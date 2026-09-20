from quince_mcp.schemas.tool import QuinceTool
from quince_mcp.tools.util import terminate, reset, chat
from quince_mcp.tools.system.open_app import open_app


open_app_tool = QuinceTool(
    tool_id="root.open_app",
    kind="leaf",
    description=(
        "Open an installed application on Windows by name. By default the "
        "app opens in the background and does NOT take over the screen or "
        "steal focus - this is the correct choice almost every time, "
        "including when the user just says 'open X'. Only set "
        "bring_to_front=true if the user explicitly asks to see, switch to, "
        "or bring forward the app (e.g. 'open Chrome and show it to me', "
        "'switch to WhatsApp')."
    ),
    handler=open_app,
    arguments={
        "app_name": {
            "type": "string",
            "description": (
                "Name of the application to open, as close as possible to "
                "its real name (e.g. 'WhatsApp', 'Google Chrome'). If the "
                "tool result reports the name was ambiguous or not found, "
                "ask the user to clarify rather than guessing again."
            ),
        },
        "window": {
            "type": "string",
            "description": (
                "Optional. Text expected to appear in the app's window "
                "title, used ONLY to confirm the app actually launched. "
                "This does NOT bring the window forward by itself - it has "
                "no visible effect on the user's screen. To actually show "
                "the window to the user, set bring_to_front=true as well."
            ),
        },
        "bring_to_front": {
            "type": "boolean",
            "description": (
                "Whether to bring the app's window to the foreground so "
                "the user sees it. Defaults to false (stealth/background "
                "open). Only set this to true when the user has clearly "
                "asked to see or switch to the app - not for a plain "
                "'open X' request."
            ),
        },
    },
    required_arguments=["app_name"],
)


root = QuinceTool(
    tool_id="root",
    kind="category",
    description="",
    children=[
        chat,
        open_app_tool,
    ],
)


TOOL_TREE = {
    "root": root,
    "terminate": terminate,
    "reset": reset,
    "root.chat": chat,
    "root.open_app": open_app_tool,
}