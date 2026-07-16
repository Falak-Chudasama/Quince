from __future__ import annotations

from urllib.parse import quote_plus
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote_plus

from playwright.sync_api import BrowserContext, Page, sync_playwright

@dataclass
class BrowserState:
    url: str = ""
    title: str = ""
    accessibility: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "accessibility": self.accessibility,
        }

class BrowserController:
    def __init__(self, profile_dir: Path, start_url: str, channel: str = "chrome", chromium_sandbox: bool = True):
        self.profile_dir = profile_dir
        self.start_url = start_url
        self.channel = channel
        self.chromium_sandbox = chromium_sandbox
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def launch(self) -> None:
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        chromium = self._playwright.chromium
        launch_kwargs = {
            "user_data_dir": str(self.profile_dir),
            "headless": False,
            "viewport": {"width": 1400, "height": 1000},
            "chromium_sandbox": self.chromium_sandbox,
        }
        if self.channel:
            launch_kwargs["channel"] = self.channel
        try:
            self._context = chromium.launch_persistent_context(**launch_kwargs)
        except Exception:
            # Some environments cannot start Chromium with sandboxing enabled.
            # Fall back only when necessary.
            if self.chromium_sandbox:
                launch_kwargs["chromium_sandbox"] = False
                try:
                    self._context = chromium.launch_persistent_context(**launch_kwargs)
                except Exception:
                    launch_kwargs.pop("channel", None)
                    self._context = chromium.launch_persistent_context(**launch_kwargs)
            else:
                launch_kwargs.pop("channel", None)
                self._context = chromium.launch_persistent_context(**launch_kwargs)
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        if self.start_url and self._page.url in ("about:blank", ""):
            self._page.goto(self.start_url, wait_until="domcontentloaded")

    def close(self) -> None:
        try:
            if self._context:
                self._context.close()
        finally:
            self._context = None
            self._page = None
            if self._playwright:
                self._playwright.stop()
                self._playwright = None

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("Browser is not launched.")
        return self._page

    def open_url(self, url: str) -> Dict[str, Any]:
        self.page.goto(url, wait_until="domcontentloaded")
        return self.snapshot()

    def search(self, query: str) -> Dict[str, Any]:
        url = f"https://duckduckgo.com/?q={quote_plus(query)}"
        return self.open_url(url)

    def click_text(self, text: str) -> Dict[str, Any]:
        self.page.get_by_text(text, exact=False).first.click(timeout=8000)
        return self.snapshot()

    def click_selector(self, selector: str) -> Dict[str, Any]:
        self.page.locator(selector).first.click(timeout=8000)
        return self.snapshot()

    def find_text(self, text: str) -> Dict[str, Any]:
        locator = self.page.get_by_text(text, exact=False).first
        try:
            locator.scroll_into_view_if_needed(timeout=8000)
        except Exception:
            pass
        return self.snapshot()

    def type(self, text: str, selector: str = "body", clear: bool = False, press_enter: bool = False) -> Dict[str, Any]:
        loc = self.page.locator(selector).first
        if clear:
            try:
                loc.fill("")
            except Exception:
                pass
        loc.click(timeout=8000)
        loc.type(text, delay=15)
        if press_enter:
            loc.press("Enter")
        return self.snapshot()

    def press(self, keys: str) -> Dict[str, Any]:
        self.page.keyboard.press(keys)
        return self.snapshot()

    def scroll(self, delta_y: int = 800) -> Dict[str, Any]:
        self.page.mouse.wheel(0, delta_y)
        return self.snapshot()

    def wait(self, seconds: float = 1.0) -> Dict[str, Any]:
        self.page.wait_for_timeout(int(seconds * 1000))
        return self.snapshot()

    def back(self) -> Dict[str, Any]:
        self.page.go_back(wait_until="domcontentloaded")
        return self.snapshot()

    def forward(self) -> Dict[str, Any]:
        self.page.go_forward(wait_until="domcontentloaded")
        return self.snapshot()

    def new_tab(self, url: str = "about:blank") -> Dict[str, Any]:
        page = self._context.new_page()
        if url:
            page.goto(url, wait_until="domcontentloaded")
        self._page = page
        return self.snapshot()

    def close_tab(self, index: int = -1) -> Dict[str, Any]:
        pages = self._context.pages
        if not pages:
            raise RuntimeError("No browser tabs are open.")
        page = pages[index]
        page.close()
        remaining = self._context.pages
        self._page = remaining[0] if remaining else self._context.new_page()
        return self.snapshot()

    def switch_tab(self, index: int) -> Dict[str, Any]:
        pages = self._context.pages
        if index < 0 or index >= len(pages):
            raise RuntimeError(f"Tab index out of range: {index}")
        self._page = pages[index]
        self._page.bring_to_front()
        return self.snapshot()

    def list_tabs(self) -> Dict[str, Any]:
        tabs = []
        for i, page in enumerate(self._context.pages):
            tabs.append({"index": i, "url": page.url, "title": page.title()})
        return {"tabs": tabs}

    def snapshot(self) -> Dict[str, Any]:
        acc = None
        try:
            locator = self.page.locator("body")
            if hasattr(locator, "aria_snapshot"):
                acc = locator.aria_snapshot()
        except Exception:
            try:
                acc = self.page.locator("body").inner_text(timeout=2000)[:6000]
            except Exception:
                acc = None
        return {
            "url": self.page.url,
            "title": self.page.title(),
            "accessibility": acc,
            "tabs": self.list_tabs().get("tabs", []),
        }

    def summary(self) -> str:
        state = self.snapshot()
        return json.dumps(state, indent=2, ensure_ascii=False)
