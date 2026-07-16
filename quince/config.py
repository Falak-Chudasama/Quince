from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT_DIR / "quince" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PREFERENCES = ROOT_DIR / "preferences.txt"
DEFAULT_PREFERENCES_EXAMPLE = ROOT_DIR / "preferences.example.txt"

@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    groq_model: str
    browser_channel: str
    chromium_sandbox: bool
    browser_profile_dir: Path
    browser_start_url: str
    preferences_path: Path
    screenshot_dir: Path
    confirm_risky_actions: bool
    max_steps_per_task: int
    use_ocr: bool
    use_browser_vision: bool

def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}

def load_settings() -> Settings:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing. Put it in .env or your environment.")

    model = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct").strip()
    browser_channel = os.getenv("QUINCE_BROWSER_CHANNEL", "").strip()
    browser_profile_dir = Path(os.getenv("QUINCE_BROWSER_PROFILE_DIR", str(STATE_DIR / "chrome-profile"))).expanduser().resolve()
    chromium_sandbox = _env_bool("QUINCE_CHROMIUM_SANDBOX", True)
    browser_start_url = os.getenv("QUINCE_BROWSER_START_URL", "").strip()
    preferences_path = Path(os.getenv("QUINCE_PREFERENCES_FILE", str(DEFAULT_PREFERENCES))).expanduser().resolve()
    screenshot_dir = Path(os.getenv("QUINCE_SCREENSHOT_DIR", str(STATE_DIR / "screens"))).expanduser().resolve()
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        groq_api_key=api_key,
        groq_model=model,
        browser_channel=browser_channel,
        chromium_sandbox=chromium_sandbox,
        browser_profile_dir=browser_profile_dir,
        browser_start_url=browser_start_url,
        preferences_path=preferences_path,
        screenshot_dir=screenshot_dir,
        confirm_risky_actions=_env_bool("QUINCE_CONFIRM_RISKY_ACTIONS", True),
        max_steps_per_task=int(os.getenv("QUINCE_MAX_STEPS_PER_TASK", "16")),
        use_ocr=_env_bool("QUINCE_USE_OCR", True),
        use_browser_vision=_env_bool("QUINCE_USE_BROWSER_VISION", True),
    )
