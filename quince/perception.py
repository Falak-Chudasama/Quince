from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image
import mss

try:
    import pygetwindow as gw
except Exception:
    gw = None


def _active_window_title() -> str:
    try:
        if gw is None:
            return ""
        win = gw.getActiveWindow()
        if not win:
            return ""
        return (getattr(win, "title", "") or "").strip()
    except Exception:
        return ""


@dataclass
class ScreenState:
    screenshot_path: Optional[Path]
    screenshot_b64: Optional[str]
    ocr_text: str = ""
    active_window: str = ""
    browser_state: Dict[str, Any] = field(default_factory=dict)
    native_state: Dict[str, Any] = field(default_factory=dict)

    def to_context(self) -> str:
        browser = json.dumps(self.browser_state or {}, indent=2, ensure_ascii=False)
        native = json.dumps(self.native_state or {}, indent=2, ensure_ascii=False)
        parts = [
            "ACTIVE WINDOW:",
            self.active_window or "unknown",
            "",
            "OCR TEXT:",
            self.ocr_text.strip() or "none",
            "",
            "BROWSER STATE:",
            browser,
            "",
            "NATIVE STATE:",
            native,
        ]
        return "\n".join(parts)


def capture_screen(output_dir: Path, prefix: str = "screen") -> ScreenState:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    shot_path = output_dir / f"{prefix}-{ts}.png"

    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.rgb)
            img.save(shot_path)
        with open(shot_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return ScreenState(
            screenshot_path=shot_path,
            screenshot_b64=b64,
            active_window=_active_window_title(),
        )
    except Exception:
        # Return a valid object even when screen capture fails.
        return ScreenState(
            screenshot_path=None,
            screenshot_b64=None,
            active_window=_active_window_title(),
        )


def try_ocr(image_path: Path) -> str:
    try:
        import pytesseract
        image = Image.open(image_path)
        return pytesseract.image_to_string(image)
    except Exception:
        return ""
