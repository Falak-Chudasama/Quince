from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pyautogui
import pyperclip

try:
    from pywinauto import Desktop
except Exception:
    Desktop = None

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

@dataclass
class WindowInfo:
    title: str
    class_name: str = ""
    process_id: Optional[int] = None

class NativeController:
    def __init__(self):
        self._desktop = Desktop(backend="uia") if Desktop else None

    def list_windows(self) -> List[Dict[str, Any]]:
        result = []
        if self._desktop:
            try:
                for w in self._desktop.windows():
                    title = (w.window_text() or "").strip()
                    if title:
                        result.append({
                            "title": title,
                            "class_name": getattr(w.element_info, "class_name", ""),
                            "control_type": getattr(w.element_info, "control_type", ""),
                        })
            except Exception:
                pass
        return result[:50]

    def _match_window(self, title_hint: str):
        if not self._desktop:
            raise RuntimeError("pywinauto is not available.")
        windows = self._desktop.windows()
        title_hint_l = title_hint.lower()
        candidates = [w for w in windows if title_hint_l in (w.window_text() or "").lower()]
        if not candidates:
            raise RuntimeError(f"No window matched: {title_hint}")
        return candidates[0]

    def focus_window(self, title_hint: str) -> Dict[str, Any]:
        win = self._match_window(title_hint)
        win.set_focus()
        return {"focused": win.window_text()}

    def inspect_window(self, title_hint: str) -> Dict[str, Any]:
        win = self._match_window(title_hint)
        try:
            children = []
            for child in win.children():
                try:
                    children.append({
                        "title": (child.window_text() or "").strip(),
                        "class_name": getattr(child.element_info, "class_name", ""),
                        "control_type": getattr(child.element_info, "control_type", ""),
                        "automation_id": getattr(child.element_info, "automation_id", ""),
                    })
                except Exception:
                    continue
        except Exception:
            children = []
        return {
            "title": win.window_text(),
            "children": children[:120],
        }

    def open_app(self, app_name: str) -> Dict[str, Any]:
        app_name = app_name.strip()
        if not app_name:
            raise RuntimeError("Empty app name.")
        try:
            os.startfile(app_name)
        except Exception:
            subprocess.Popen(f'start "" "{app_name}"', shell=True)
        time.sleep(2)
        return {"opened": app_name}

    def click(self, x: int, y: int, button: str = "left") -> Dict[str, Any]:
        pyautogui.click(x=x, y=y, button=button)
        return {"clicked": [x, y, button]}

    def double_click(self, x: int, y: int) -> Dict[str, Any]:
        pyautogui.doubleClick(x=x, y=y)
        return {"double_clicked": [x, y]}

    def right_click(self, x: int, y: int) -> Dict[str, Any]:
        pyautogui.rightClick(x=x, y=y)
        return {"right_clicked": [x, y]}

    def type(self, text: str, interval: float = 0.01) -> Dict[str, Any]:
        pyautogui.write(text, interval=interval)
        return {"typed": text}

    def paste(self, text: str) -> Dict[str, Any]:
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        return {"pasted": text}

    def hotkey(self, keys: List[str]) -> Dict[str, Any]:
        if not keys:
            raise RuntimeError("Empty hotkey.")
        pyautogui.hotkey(*keys)
        return {"hotkey": keys}

    def press(self, keys: str) -> Dict[str, Any]:
        key_list = [k.strip() for k in keys.split("+") if k.strip()]
        pyautogui.hotkey(*key_list) if len(key_list) > 1 else pyautogui.press(key_list[0])
        return {"pressed": keys}

    def scroll(self, amount: int = -800) -> Dict[str, Any]:
        pyautogui.scroll(amount)
        return {"scrolled": amount}

    def wait(self, seconds: float = 1.0) -> Dict[str, Any]:
        time.sleep(seconds)
        return {"waited": seconds}

    def screenshot(self) -> Dict[str, Any]:
        img = pyautogui.screenshot()
        path = Path(os.getcwd()) / "native_screenshot.png"
        img.save(path)
        return {"path": str(path), "size": img.size}
