from __future__ import annotations

import queue
import tkinter as tk
from tkinter import font as tkfont
from typing import TYPE_CHECKING, Any

from src.logging_setup import get_logger
from src.ui.theme import PRIMARY, SCENT, SECONDARY

if TYPE_CHECKING:
    from src.client import QuinceClient

logger = get_logger("ui.gui")

# Dark Theme Colors
BG_MAIN = "#121214"
BG_CARD = "#1A1A1E"
BG_INPUT = "#26262B"
BG_INPUT_FOCUS = "#2F2F36"
TEXT_MAIN = "#F4F4F5"
TEXT_MUTED = "#9CA3AF"
BORDER_COLOR = "#2E2E36"
ACCENT_GOLD = SECONDARY  # #FFD71C
ACCENT_PINK = PRIMARY    # #F9768C
ACCENT_GREEN = SCENT    # #80A32C


class QuinceGUI:
    """
    Sleek, responsive Tkinter GUI for Quince.

    Accepts text input in an input field with a Send button and Enter key trigger,
    displays live streaming chat transcripts, and visualizes turn/connection states,
    while running smoothly alongside Quince's global push-to-talk voice input (Ctrl+Q).
    """

    def __init__(self, client: QuinceClient) -> None:
        self.client = client
        self.root = tk.Tk()
        self.root.title("Quince — Basket Companion")
        self.root.configure(bg=BG_MAIN)
        self.root.geometry("640x720")
        self.root.minsize(480, 520)

        # Set window icon / styling hints
        try:
            # Dark title bar on Windows 10/11 if supported
            import ctypes
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            value = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
            )
        except Exception:
            pass

        self._queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._streaming_assistant = False
        self._current_assistant_text = ""

        self._setup_fonts()
        self._build_header()
        self._build_transcript()
        self._build_input_bar()

        # Connect client hooks
        self._attach_client_callbacks()

        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Periodically process queue for UI updates
        self.root.after(50, self._process_queue)

    def _setup_fonts(self) -> None:
        self.font_title = tkfont.Font(family="Segoe UI", size=15, weight="bold")
        self.font_subtitle = tkfont.Font(family="Segoe UI", size=9)
        self.font_badge = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.font_body = tkfont.Font(family="Segoe UI", size=10)
        self.font_header = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        self.font_hint = tkfont.Font(family="Segoe UI", size=9)
        self.font_btn = tkfont.Font(family="Segoe UI", size=10, weight="bold")

    def _build_header(self) -> None:
        header_frame = tk.Frame(self.root, bg=BG_CARD, padx=16, pady=12, highlightthickness=1, highlightbackground=BORDER_COLOR)
        header_frame.pack(fill="x", side="top")

        left_box = tk.Frame(header_frame, bg=BG_CARD)
        left_box.pack(side="left", fill="y")

        title_label = tk.Label(
            left_box,
            text="QUINCE",
            font=self.font_title,
            fg=ACCENT_GOLD,
            bg=BG_CARD,
        )
        title_label.pack(side="top", anchor="w")

        subtitle_label = tk.Label(
            left_box,
            text="Voice & Text Companion for Basket",
            font=self.font_subtitle,
            fg=TEXT_MUTED,
            bg=BG_CARD,
        )
        subtitle_label.pack(side="top", anchor="w")

        # Right side: badges
        right_box = tk.Frame(header_frame, bg=BG_CARD)
        right_box.pack(side="right", fill="y")

        self.conn_badge = tk.Label(
            right_box,
            text="● Connecting...",
            font=self.font_badge,
            fg=ACCENT_GOLD,
            bg="#222228",
            padx=10,
            pady=4,
            relief="flat",
        )
        self.conn_badge.pack(side="right", padx=(8, 0))

        self.turn_badge = tk.Label(
            right_box,
            text="IDLE",
            font=self.font_badge,
            fg=TEXT_MUTED,
            bg="#222228",
            padx=10,
            pady=4,
            relief="flat",
        )
        self.turn_badge.pack(side="right")

        # Hotkey hint banner
        hint_bar = tk.Frame(self.root, bg=BG_MAIN, padx=16, pady=6)
        hint_bar.pack(fill="x", side="top")

        hint_label = tk.Label(
            hint_bar,
            text="🎙 Push-to-Talk: Hold [ Ctrl + Q ] to speak | Type prompt below and hit Enter",
            font=self.font_hint,
            fg=TEXT_MUTED,
            bg=BG_MAIN,
        )
        hint_label.pack(side="left")

    def _build_transcript(self) -> None:
        container = tk.Frame(self.root, bg=BG_MAIN, padx=16, pady=4)
        container.pack(fill="both", expand=True)

        self.transcript = tk.Text(
            container,
            bg="#161619",
            fg=TEXT_MAIN,
            font=self.font_body,
            wrap="word",
            relief="flat",
            padx=14,
            pady=14,
            spacing1=3,
            spacing3=3,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            insertbackground=TEXT_MAIN,
            selectbackground="#3E3E4A",
        )
        scrollbar = tk.Scrollbar(container, command=self.transcript.yview, relief="flat", bg=BG_CARD, width=10)
        self.transcript.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.transcript.pack(side="left", fill="both", expand=True)

        # Setup tags
        self.transcript.tag_configure("you_header", font=self.font_header, foreground=ACCENT_GOLD)
        self.transcript.tag_configure("you_voice_header", font=self.font_header, foreground=ACCENT_PINK)
        self.transcript.tag_configure("user_text", font=self.font_body, foreground=TEXT_MAIN)
        self.transcript.tag_configure("assistant_header", font=self.font_header, foreground=ACCENT_GREEN)
        self.transcript.tag_configure("assistant_text", font=self.font_body, foreground="#E4E4E7")
        self.transcript.tag_configure("system_msg", font=self.font_subtitle, foreground=TEXT_MUTED)

        # Initial welcome message
        self.transcript.insert("end", "Quince is ready.\n", "system_msg")
        self.transcript.insert("end", "Speak with [Ctrl+Q] or type your query below.\n\n", "system_msg")
        self.transcript.configure(state="disabled")

    def _build_input_bar(self) -> None:
        input_container = tk.Frame(self.root, bg=BG_CARD, padx=16, pady=12, highlightthickness=1, highlightbackground=BORDER_COLOR)
        input_container.pack(fill="x", side="bottom")

        # Top row in input container: options
        options_row = tk.Frame(input_container, bg=BG_CARD)
        options_row.pack(fill="x", side="top", pady=(0, 8))

        self.synthesize_var = tk.BooleanVar(value=True)
        self.voice_checkbox = tk.Checkbutton(
            options_row,
            text="Synthesize Voice Response (TTS)",
            variable=self.synthesize_var,
            font=self.font_hint,
            fg=TEXT_MAIN,
            bg=BG_CARD,
            activebackground=BG_CARD,
            activeforeground=ACCENT_GOLD,
            selectcolor=BG_INPUT,
            highlightthickness=0,
            bd=0,
        )
        self.voice_checkbox.pack(side="left")

        # Bottom row: Entry and Send button
        entry_row = tk.Frame(input_container, bg=BG_CARD)
        entry_row.pack(fill="x", side="bottom")

        self.input_entry = tk.Entry(
            entry_row,
            bg=BG_INPUT,
            fg=TEXT_MAIN,
            font=self.font_body,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=ACCENT_GOLD,
            insertbackground=TEXT_MAIN,
        )
        self.input_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 10))
        self.input_entry.bind("<Return>", lambda event: self.send_text())
        self.input_entry.focus_set()

        self.send_btn = tk.Button(
            entry_row,
            text="Send  ➤",
            font=self.font_btn,
            bg=ACCENT_GOLD,
            fg="#121214",
            activebackground="#E5C118",
            activeforeground="#121214",
            relief="flat",
            padx=18,
            pady=6,
            cursor="hand2",
            command=self.send_text,
        )
        self.send_btn.pack(side="right")

    def _attach_client_callbacks(self) -> None:
        self.client.on_user_message_cb = lambda text, mode: self._queue.put(("user_msg", (text, mode)))
        self.client.on_llm_token_cb = lambda token: self._queue.put(("token", token))
        self.client.on_llm_final_cb = lambda text: self._queue.put(("llm_final", text))
        self.client.on_status_change_cb = lambda turn, conn: self._queue.put(("status", (turn, conn)))

    def _process_queue(self) -> None:
        try:
            while True:
                kind, data = self._queue.get_nowait()
                if kind == "user_msg":
                    text, mode = data
                    self._append_user_message(text, mode)
                elif kind == "token":
                    self._append_llm_token(data)
                elif kind == "llm_final":
                    self._finalize_llm_response(data)
                elif kind == "status":
                    turn, conn = data
                    self._update_status(turn, conn)
        except queue.Empty:
            pass
        finally:
            self.root.after(50, self._process_queue)

    def _append_user_message(self, text: str, mode: str) -> None:
        self._streaming_assistant = False
        self.transcript.configure(state="normal")
        header = "You (Voice):\n" if mode == "voice" else "You:\n"
        tag = "you_voice_header" if mode == "voice" else "you_header"

        self.transcript.insert("end", header, tag)
        self.transcript.insert("end", f"{text}\n\n", "user_text")
        self.transcript.see("end")
        self.transcript.configure(state="disabled")

    def _append_llm_token(self, token: str) -> None:
        self.transcript.configure(state="normal")
        if not self._streaming_assistant:
            self._streaming_assistant = True
            self._current_assistant_text = ""
            self.transcript.insert("end", "Quince:\n", "assistant_header")

        self.transcript.insert("end", token, "assistant_text")
        self._current_assistant_text += token
        self.transcript.see("end")
        self.transcript.configure(state="disabled")

    def _finalize_llm_response(self, full_text: str) -> None:
        self.transcript.configure(state="normal")
        if not self._streaming_assistant:
            self.transcript.insert("end", "Quince:\n", "assistant_header")
            self.transcript.insert("end", full_text, "assistant_text")
        self.transcript.insert("end", "\n\n")
        self._streaming_assistant = False
        self._current_assistant_text = ""
        self.transcript.see("end")
        self.transcript.configure(state="disabled")

    def _update_status(self, turn: str, conn: str) -> None:
        # Update connection badge
        if conn == "connected":
            self.conn_badge.configure(text="● Connected", fg=ACCENT_GREEN)
        elif conn == "connecting":
            self.conn_badge.configure(text="● Connecting...", fg=ACCENT_GOLD)
        else:
            self.conn_badge.configure(text="● Offline", fg=ACCENT_PINK)

        # Update turn badge
        turn_upper = turn.upper()
        if turn == "recording":
            self.turn_badge.configure(text="● LISTENING", fg=ACCENT_PINK)
        elif turn == "thinking":
            self.turn_badge.configure(text="● THINKING", fg=ACCENT_GOLD)
        elif turn == "speaking":
            self.turn_badge.configure(text="● SPEAKING", fg=ACCENT_GREEN)
        else:
            self.turn_badge.configure(text="IDLE", fg=TEXT_MUTED)

    def send_text(self) -> None:
        prompt = self.input_entry.get().strip()
        if not prompt:
            return

        if not self.client.connection.is_connected:
            self.transcript.configure(state="normal")
            self.transcript.insert("end", "⚠️ Not connected to Basket. Please ensure Basket is running.\n\n", "system_msg")
            self.transcript.see("end")
            self.transcript.configure(state="disabled")
            return

        self.input_entry.delete(0, "end")
        synth = self.synthesize_var.get()
        self.client.submit_text(prompt, synthesize_speech=synth)

    def on_close(self) -> None:
        logger.info("Closing Quince GUI window.")
        self.client.request_shutdown()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
