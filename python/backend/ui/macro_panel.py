"""
macro_panel.py — Quick-fire preset command macro buttons (OpenClaw + Hermes).
"""

from __future__ import annotations
from typing import Any, Callable

import customtkinter as ctk

from ..config import HERMES_PRESETS, OPENCLAW_PRESETS, all_preset_commands
from ..theme import C, F, label_font, small_font, micro_font

# Backward compat aliases
font = F
tiny_font = micro_font

_DEFAULT_MACROS: list[tuple[str, str, str]] = [
    ("📊  Status",    "openclaw status",   "OpenClaw node status"),
    ("📋  Sessions",  "openclaw sessions", "Agent sessions"),
    ("📜  Logs",      "openclaw logs",     "Log stream"),
    ("🖥  TUI",       "openclaw tui",      "Interactive TUI"),
    ("📊  Status",    "hermes status",   "Hermes node status"),
    ("📋  Sessions",  "hermes sessions", "Agent sessions"),
    ("📜  Logs",      "hermes logs",     "Log stream"),
    ("🖥  TUI",       "hermes tui",      "Interactive TUI"),
]


class MacroPanel(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        on_connect_cmd: Callable[[str], None] | None = None,
        on_broadcast: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, corner_radius=0, **kwargs)

        self._on_connect_cmd = on_connect_cmd or (lambda cmd: None)
        self._on_broadcast   = on_broadcast   or (lambda cmd: None)
        self._macros         = list(_DEFAULT_MACROS)

        self.grid_columnconfigure(0, weight=1)
        self._build_ui()

    def _build_ui(self) -> None:
        self._header = ctk.CTkFrame(self, corner_radius=0, height=36)
        self._header.grid(row=0, column=0, sticky="ew")
        self._header.grid_columnconfigure(0, weight=1)
        self._header.grid_propagate(False)

        self._header_lbl = ctk.CTkLabel(self._header, text="⚡  QUICK COMMANDS", font=font(12, "bold"))
        self._header_lbl.grid(row=0, column=0, padx=14, pady=6, sticky="w")

        self._lock_lbl = ctk.CTkLabel(self._header, text="presets", font=tiny_font())
        self._lock_lbl.grid(row=0, column=1, padx=14, pady=6, sticky="e")

        self._btn_frame = ctk.CTkFrame(self, corner_radius=0)
        self._btn_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=8)

        self._macro_btns: list[tuple[ctk.CTkButton, ctk.CTkButton]] = []

        presets_ok = OPENCLAW_PRESETS + HERMES_PRESETS
        for i, (label, command, tooltip) in enumerate(self._macros):
            if command not in presets_ok:
                continue
            row = i // 4
            col = i % 4
            self._add_macro_button(row, col, label, command, tooltip)

        self.apply_theme()

    def _add_macro_button(self, row: int, col: int, label: str, command: str, tooltip: str) -> None:
        container = ctk.CTkFrame(self._btn_frame, corner_radius=10)
        container.grid(row=row, column=col, padx=8, pady=6, sticky="n")

        fire_btn = ctk.CTkButton(
            container,
            text=label,
            font=font(14, "bold"),
            width=164, height=42,
            corner_radius=8,
            command=lambda cmd=command: self._fire(cmd),
        )
        fire_btn.grid(row=0, column=0, padx=10, pady=(10, 2))

        cmd_lbl = ctk.CTkLabel(container, text=command, font=tiny_font())
        cmd_lbl.grid(row=1, column=0, pady=(0, 4))

        all_btn = ctk.CTkButton(
            container,
            text="📡  All Tabs",
            font=small_font(),
            width=164, height=28,
            corner_radius=6,
            command=lambda cmd=command: self._broadcast(cmd),
        )
        all_btn.grid(row=2, column=0, padx=10, pady=(0, 10))

        self._macro_btns.append((fire_btn, all_btn))

    def _fire(self, command: str) -> None:
        if command not in all_preset_commands():
            return
        self._on_connect_cmd(command)

    def _broadcast(self, command: str) -> None:
        if command not in all_preset_commands():
            return
        self._on_broadcast(command)

    def apply_theme(self) -> None:
        self.configure(fg_color=C("card"))
        self._header.configure(fg_color=C("card2"))
        self._header_lbl.configure(text_color=C("gold"))
        self._lock_lbl.configure(text_color=C("dim"))
        self._btn_frame.configure(fg_color=C("card"))

        for fire_btn, all_btn in self._macro_btns:
            fire_btn.configure(fg_color=C("accent"), hover_color=C("gold"), text_color="#ffffff")
            all_btn.configure(fg_color=C("card2"), hover_color=C("border"), text_color=C("accent"), border_color=C("border"), border_width=1)

        for child in self._btn_frame.winfo_children():
            if isinstance(child, ctk.CTkFrame):
                child.configure(fg_color=C("card2"))
                for sub in child.winfo_children():
                    if isinstance(sub, ctk.CTkLabel):
                        sub.configure(text_color=C("dim"))
