"""
macro_bar.py — Quick-command macro strip. Lunar Interface.

Design: Collapsed by default to a thin strip showing keyboard shortcuts.
Click to expand and see the full command buttons.
Minimal footprint — commands should be discoverable, not dominating.
"""
from __future__ import annotations
from typing import Any, Callable

import customtkinter as ctk

from ..config import HERMES_PRESETS, OPENCLAW_PRESETS, all_preset_commands
from ..theme import (
    C, F, label_font, label_bold, small_font, micro_font,
    PAD_SM, PAD_MD, PAD_LG, PAD_XL,
    RADIUS_SM, RADIUS_MD,
)

# (button label, remote command, shortcut hint) — shortcuts only on OpenClaw row for strip text
_OC_MACROS = [
    ("Status",   "openclaw status",   "Ctrl+1"),
    ("Sessions", "openclaw sessions", "Ctrl+2"),
    ("Logs",     "openclaw logs",     "Ctrl+3"),
    ("TUI",      "openclaw tui",      "Ctrl+4"),
]
_HM_MACROS = [
    ("Status",   "hermes status",   ""),
    ("Sessions", "hermes sessions", ""),
    ("Logs",     "hermes logs",     ""),
    ("Chat",     "hermes",          ""),
]


class MacroBar(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        on_fire: Callable[[str], None] | None = None,
        on_broadcast: Callable[[str], None] | None = None,
        on_broadcast_all: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, corner_radius=0, **kwargs)
        self._on_fire = on_fire or (lambda c: None)
        self._on_broadcast = on_broadcast or (lambda c: None)
        self._on_broadcast_all = on_broadcast_all
        self._expanded = False
        self._buttons: list[ctk.CTkButton] = []

        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self) -> None:
        # ── Collapsed strip (always visible) ──
        self._strip = ctk.CTkFrame(self, corner_radius=0, height=32, cursor="hand2")
        self._strip.grid(row=0, column=0, sticky="ew")
        self._strip.grid_propagate(False)
        self._strip.grid_columnconfigure(1, weight=1)

        self._toggle_lbl = ctk.CTkLabel(
            self._strip, text="Quick Commands",
            font=F(11, "bold"), anchor="w",
        )
        self._toggle_lbl.grid(row=0, column=0, padx=PAD_LG, pady=PAD_SM, sticky="w")

        oc_short = "  ·  ".join(f"{m[0]} {m[2]}" for m in _OC_MACROS if m[2] and m[1] in OPENCLAW_PRESETS)
        self._shortcuts_lbl = ctk.CTkLabel(
            self._strip, text=f"OpenClaw: {oc_short}  ·  Hermes: same layout",
            font=micro_font(), anchor="w",
        )
        self._shortcuts_lbl.grid(row=0, column=1, padx=PAD_SM, sticky="w")

        self._chevron = ctk.CTkLabel(
            self._strip, text="›",
            font=F(14, "bold"), width=24,
        )
        self._chevron.grid(row=0, column=2, padx=PAD_MD)

        # Bind click on entire strip
        for w in (self._strip, self._toggle_lbl, self._shortcuts_lbl, self._chevron):
            w.bind("<Button-1>", lambda e: self._toggle())
            try:
                w.configure(cursor="hand2")
            except Exception:
                pass

        # ── Expanded panel (hidden by default) ──
        self._panel = ctk.CTkFrame(self, corner_radius=0)
        self._panel.grid(row=1, column=0, sticky="ew")
        self._panel.grid_remove()  # hidden

        inner = ctk.CTkFrame(self._panel, fg_color="transparent")
        inner.pack(padx=PAD_LG, pady=(PAD_SM, PAD_MD), fill="x")

        ctk.CTkLabel(inner, text="OpenClaw", font=label_bold(), text_color=C("gold")).pack(anchor="w")
        row_oc = ctk.CTkFrame(inner, fg_color="transparent")
        row_oc.pack(fill="x", pady=(0, PAD_SM))
        for label, cmd, _s in _OC_MACROS:
            if cmd not in OPENCLAW_PRESETS:
                continue
            btn = ctk.CTkButton(
                row_oc, text=label,
                font=label_font(),
                width=100, height=32,
                corner_radius=RADIUS_SM,
                command=lambda c=cmd: self._fire(c),
            )
            btn.pack(side="left", padx=PAD_SM)
            self._buttons.append(btn)

        ctk.CTkLabel(inner, text="Hermes", font=label_bold(), text_color=C("gold")).pack(anchor="w")
        row_hm = ctk.CTkFrame(inner, fg_color="transparent")
        row_hm.pack(fill="x", pady=(0, PAD_SM))
        for label, cmd, _s in _HM_MACROS:
            if cmd not in HERMES_PRESETS:
                continue
            btn = ctk.CTkButton(
                row_hm, text=label,
                font=label_font(),
                width=100, height=32,
                corner_radius=RADIUS_SM,
                command=lambda c=cmd: self._fire(c),
            )
            btn.pack(side="left", padx=PAD_SM)
            self._buttons.append(btn)

        row_bc = ctk.CTkFrame(inner, fg_color="transparent")
        row_bc.pack(fill="x")
        self._broadcast_btn = ctk.CTkButton(
            row_bc, text="Broadcast All (status)",
            font=micro_font(),
            width=180, height=32,
            corner_radius=RADIUS_SM,
            command=lambda: self._broadcast_all(),
        )
        self._broadcast_btn.pack(side="right", padx=PAD_SM)

        self.apply_theme()

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self._panel.grid()
            self._chevron.configure(text="⌄")
        else:
            self._panel.grid_remove()
            self._chevron.configure(text="›")

    def _fire(self, cmd: str) -> None:
        if cmd in all_preset_commands():
            self._on_fire(cmd)

    def _broadcast_all(self) -> None:
        if self._on_broadcast_all is not None:
            self._on_broadcast_all()
        else:
            self._on_broadcast("openclaw status")

    def apply_theme(self) -> None:
        self.configure(fg_color=C("bg2"))

        # Strip
        self._strip.configure(fg_color=C("bg2"))
        self._toggle_lbl.configure(text_color=C("text"))
        self._shortcuts_lbl.configure(text_color=C("dim"))
        self._chevron.configure(text_color=C("text"))

        # Panel
        self._panel.configure(fg_color=C("bg2"))

        for btn in self._buttons:
            btn.configure(
                fg_color=C("card2"), hover_color=C("accent"),
                text_color=C("text"), border_color=C("border"), border_width=1,
            )

        self._broadcast_btn.configure(
            fg_color="transparent", hover_color=C("card2"),
            text_color=C("dim"), border_color=C("border"), border_width=1,
        )
