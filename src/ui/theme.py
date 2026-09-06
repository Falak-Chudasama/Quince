from __future__ import annotations

"""
Quince brand theme.

Single source of truth for the three accent colors so the banner, the
status line, and the log formatter all agree with each other. Nothing
outside this module should hardcode a hex value.
"""

from rich.console import Console
from rich.theme import Theme

# ----------------------------------------------------------------
# Brand palette
# ----------------------------------------------------------------
PRIMARY = "#F9768C"    # blush pink — brand mark, warnings-adjacent accents
SECONDARY = "#FFD71C"  # gold — the workhorse accent, used most
SCENT = "#80A32C"      # olive green — success / connected / good state

# Semantic roles, mapped onto the palette above. Log levels and turn
# states pull from these names rather than raw hex so the mapping only
# has to be decided once.
QUINCE_THEME = Theme(
    {
        # Brand
        "quince.brand": f"bold {SECONDARY}",
        "quince.primary": PRIMARY,
        "quince.secondary": SECONDARY,
        "quince.scent": SCENT,
        "quince.dim": "grey58",
        "quince.muted": "grey42",
        # Log levels
        "log.debug": "grey50",
        "log.info": "grey78",
        "log.warning": f"bold {SECONDARY}",
        "log.error": f"bold {PRIMARY}",
        "log.critical": f"bold white on {PRIMARY}",
        # Turn / connection state
        "state.idle": "grey58",
        "state.recording": f"bold {PRIMARY}",
        "state.thinking": f"bold {SECONDARY}",
        "state.speaking": f"bold {SCENT}",
        "state.connected": SCENT,
        "state.disconnected": f"bold {PRIMARY}",
        "state.connecting": SECONDARY,
    }
)


def make_console(*, stderr: bool = False) -> Console:
    """Every Quince surface shares this console so styling is consistent."""
    return Console(theme=QUINCE_THEME, stderr=stderr, highlight=False)


# Shared singletons — import these rather than constructing new ones,
# so log output and status-line output interleave on the same console
# instead of racing on separate stdout writers.
console = make_console()
err_console = make_console(stderr=True)
