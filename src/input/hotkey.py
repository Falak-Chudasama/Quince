from __future__ import annotations
from typing import Callable
import keyboard

from src.logging_setup import get_logger

"""
Push-to-talk hotkey (default Ctrl+Q).

Hold to record. Release to stop and send. A single press-and-hold
while Quince is speaking (or still mid-pipeline) interrupts playback
AND starts recording the new prompt in the same gesture — the user
never has to press twice. This module only detects intent and calls
back into whatever callbacks it's given — it has no knowledge of
websockets, audio devices, or the pipeline state machine.
"""


logger = get_logger("input.hotkey")

_CTRL_NAMES = {"ctrl", "left ctrl", "right ctrl"}


class PushToTalkHotkey:
    def __init__(
        self,
        *,
        record_key: str = "q",
        on_should_start_recording: Callable[[], None],
        on_should_stop_recording: Callable[[], None],
        on_should_interrupt_and_record: Callable[[], None],
        is_pipeline_busy: Callable[[], bool],
        is_playback_active: Callable[[], bool],
        is_recording: Callable[[], bool],
    ) -> None:
        self._record_key = record_key.lower()

        self._on_start = on_should_start_recording
        self._on_stop = on_should_stop_recording
        self._on_interrupt_and_record = on_should_interrupt_and_record

        self._is_pipeline_busy = is_pipeline_busy
        self._is_playback_active = is_playback_active
        self._is_recording = is_recording

        self._latched = False
        self._mode: str | None = None
        self._hooked = False

    def install(self) -> None:
        if self._hooked:
            return
        keyboard.hook(self._handle_event, suppress=False)
        self._hooked = True
        logger.info("Push-to-talk hook installed on key %r (hold Ctrl).", self._record_key)

    def uninstall(self) -> None:
        if not self._hooked:
            return
        try:
            keyboard.unhook(self._handle_event)
        except (KeyError, ValueError):
            pass  # already removed, e.g. during interpreter shutdown
        self._hooked = False

    # ------------------------------------------------------------
    # EVENT HANDLING
    # ------------------------------------------------------------

    def _handle_event(self, event) -> None:
        name = str(event.name).lower().strip()

        if event.event_type == "down":
            self._handle_key_down(name)
            return

        if event.event_type == "up":
            self._handle_key_up(name)

    def _handle_key_down(self, name: str) -> None:
        if name != self._record_key or self._latched:
            return

        if not keyboard.is_pressed("ctrl"):
            return

        self._latched = True

        # Quince is currently speaking or mid-pipeline: one press does
        # both — interrupt whatever is playing/processing and start
        # listening for the new prompt immediately, as a single motion.
        if self._is_pipeline_busy() and (self._is_playback_active() or not self._is_recording()):
            self._mode = "record"
            self._on_interrupt_and_record()
            return

        if not self._is_pipeline_busy():
            self._mode = "record"
            self._on_start()
            return

        self._mode = "ignore"

    def _handle_key_up(self, name: str) -> None:
        if name not in ({self._record_key} | _CTRL_NAMES):
            return

        mode, self._mode = self._mode, None
        self._latched = False

        if mode == "record" and self._is_recording():
            self._on_stop()
