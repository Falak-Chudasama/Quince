"""
Bridge configuration — loaded from .env (resolved relative to the repo root).

NEVER import from this module at top level in any code path that runs
before the bridge is needed; it causes python-dotenv to load on every import.
"""
from __future__ import annotations

import os
import secrets
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _repo_root() -> Path:
    """Return the repository root (the directory containing this package)."""
    # quince_mcp/bridge/config.py  ->  quince_mcp/bridge  ->  quince_mcp  ->  repo root
    return Path(__file__).resolve().parent.parent.parent


def _load_dotenv() -> None:
    """Load .env from the repo root using python-dotenv (if available)."""
    try:
        from dotenv import load_dotenv
        env_path = _repo_root() / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)
    except ImportError:
        pass  # python-dotenv not installed; rely on environment variables


def _get_or_generate_token() -> str:
    """
    Return the bridge token from env or the .bridge_token file.
    If neither exists, generate a new one, write it to .bridge_token,
    and print a one-line instruction to stderr.
    Token value is NEVER logged.
    """
    env_token = os.environ.get("QUINCE_BRIDGE_TOKEN", "").strip()
    if env_token:
        return env_token

    token_file = _repo_root() / "quince_mcp" / "bridge" / ".bridge_token"
    if token_file.exists():
        try:
            return token_file.read_text(encoding="utf-8").strip()
        except OSError:
            pass

    # Generate a new token.
    token = secrets.token_urlsafe(32)
    try:
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(token, encoding="utf-8")
        print(
            f"\n[Quince Bridge] No token found. Generated one and saved to:\n"
            f"  {token_file}\n"
            f"Paste it into the extension's Options page (Bridge Token field).\n",
            file=sys.stderr,
            flush=True,
        )
    except OSError as exc:
        print(
            f"\n[Quince Bridge] Could not write token file ({exc}). "
            "Set QUINCE_BRIDGE_TOKEN in .env instead.\n",
            file=sys.stderr,
            flush=True,
        )
    return token


@dataclass
class BridgeSettings:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 7100
    token: str = ""
    extension_id: str = ""  # optional pin
    snapshot_max_chars: int = 6000
    max_steps: int = 40
    max_duration_s: int = 900
    idle_timeout_s: int = 600
    judge_policy: str = "always"
    merge_compare_judge: bool = False
    risk_gate: str = "on"
    termination_ends_loop: bool = False
    return_raw_state_change: bool = False

    @classmethod
    def from_env(cls) -> "BridgeSettings":
        _load_dotenv()

        host = os.environ.get("QUINCE_BRIDGE_HOST", "127.0.0.1").strip()
        if not (host.startswith("127.") or host in ("::1", "localhost")):
            raise ValueError(
                f"QUINCE_BRIDGE_HOST must be a loopback address (e.g. 127.0.0.1); "
                f"got {host!r}. Refusing to bind to a non-loopback address."
            )

        return cls(
            enabled=os.environ.get("QUINCE_BRIDGE_ENABLED", "true").lower() not in ("false", "0", "no"),
            host=host,
            port=int(os.environ.get("QUINCE_BRIDGE_PORT", "7100")),
            token=_get_or_generate_token(),
            extension_id=os.environ.get("QUINCE_BRIDGE_EXTENSION_ID", "").strip(),
            snapshot_max_chars=int(os.environ.get("RTSI_SNAPSHOT_MAX_CHARS", "6000")),
            max_steps=int(os.environ.get("RTSI_MAX_STEPS", "40")),
            max_duration_s=int(os.environ.get("RTSI_MAX_DURATION_S", "900")),
            idle_timeout_s=int(os.environ.get("RTSI_IDLE_TIMEOUT_S", "600")),
            judge_policy=os.environ.get("RTSI_JUDGE_POLICY", "always").lower(),
            merge_compare_judge=os.environ.get("RTSI_MERGE_COMPARE_JUDGE", "false").lower() in ("true", "1", "yes"),
            risk_gate=os.environ.get("RTSI_RISK_GATE", "on").lower(),
            termination_ends_loop=os.environ.get("RTSI_TERMINATION_ENDS_LOOP", "false").lower() in ("true", "1", "yes"),
            return_raw_state_change=os.environ.get("RTSI_RETURN_RAW_STATE_CHANGE", "false").lower() in ("true", "1", "yes"),
        )
