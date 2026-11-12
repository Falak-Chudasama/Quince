"""
Browser tool handlers.

All browser actions are delegated to the RTSI machine via navigate_impl.
This file exists for the handlers that would be invoked if navigate() called
tool.execute() on a browser tool — but that never happens because server.py
intercepts root--browser* before reaching the generic leaf executor.

The RTSI machine is the actual handler; these are stubs that raise clearly
if somehow called directly (which would indicate a bug in the routing).

NEVER writes to stdout.
"""
from __future__ import annotations


async def _browser_tool_stub(**kwargs):
    raise RuntimeError(
        "Browser tool handler called directly — this is a bug. "
        "All root--browser* calls must be routed through RtsiMachine.handle()."
    )
