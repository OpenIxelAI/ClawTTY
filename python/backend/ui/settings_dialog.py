"""
settings_dialog.py — Preferences dialog. Lunar Interface.

Clean sections, clear hierarchy, no visual noise.
"""
from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk
import tkinter as tk

from ._base import SafeGrabMixin
from ..theme import (
    C, F,
    header_font, body_font, label_font, label_bold, small_font, micro_font, dim_font,
    set_mode,
    PAD_SM, PAD_MD, PAD_LG, PAD_XL, PAD_2XL,
    RADIUS_SM, RADIUS_MD, RADIUS_LG,
)
from .. import settings as cfg


class SettingsDialog(SafeGrabMixin, ctk.CTkToplevel):
    def __init__(
        self,
        master: Any,
        on_scale_change: Callable[[float], None] | None = None,
        on_theme_change: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Settings")
        self.configure(fg_color=C("card"))
        self.resizable(False, False)
        self.after(100, self._safe_grab)

        self._on_scale = on_scale_change or (lambda s: None)
        self._on_theme = on_theme_change or (lambda t: None)

        prefs = cfg.load()
        self._scale_var = tk.DoubleVar(value=prefs["ui_scale"])
        self._theme_var = tk.StringVar(value=prefs["theme"])
        self._status_var = tk.StringVar(value="")

        self._build()
        self.wait_window()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        # Title
        ctk.CTkLabel(
            self, text="Settings",
            font=header_font(), text_color=C("text2"),
        ).grid(row=0, column=0, padx=PAD_2XL, pady=(PAD_2XL, PAD_SM), sticky="w")

        # ── Scale section ──
        scale_card = ctk.CTkFrame(self, fg_color=C("card2"), corner_radius=RADIUS_MD)
        scale_card.grid(row=1, column=0, padx=PAD_XL, pady=(PAD_MD, PAD_SM), sticky="ew")
        scale_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            scale_card, text="Interface Scale",
            font=label_bold(), text_color=C("text"), anchor="w",
        ).grid(row=0, column=0, padx=PAD_LG, pady=(PAD_LG, PAD_SM), sticky="w")

        ctk.CTkLabel(
            scale_card, text="Adjust for your display. 1.0 standard, 1.75 for 1440p, 2.0 for 4K.",
            font=micro_font(), text_color=C("dim"), wraplength=420, anchor="w",
        ).grid(row=1, column=0, columnspan=2, padx=PAD_LG, pady=(0, PAD_SM), sticky="w")

        # Slider
        slider_row = ctk.CTkFrame(scale_card, fg_color="transparent")
        slider_row.grid(row=2, column=0, sticky="ew", padx=PAD_LG, pady=(0, PAD_SM))
        slider_row.grid_columnconfigure(0, weight=1)

        self._slider = ctk.CTkSlider(
            slider_row,
            from_=0.5, to=3.0,
            number_of_steps=25,
            variable=self._scale_var,
            command=self._on_slider_move,
            button_color=C("accent"),
            button_hover_color=C("accent2"),
            progress_color=C("accent"),
            fg_color=C("border"),
            height=18,
        )
        self._slider.grid(row=0, column=0, sticky="ew", pady=PAD_SM)

        self._scale_lbl = ctk.CTkLabel(
            slider_row,
            text=f"{self._scale_var.get():.2f}×",
            font=label_bold(),
            text_color=C("accent"),
            width=56,
        )
        self._scale_lbl.grid(row=0, column=1, padx=(PAD_MD, 0))

        # Presets
        preset_row = ctk.CTkFrame(scale_card, fg_color="transparent")
        preset_row.grid(row=3, column=0, padx=PAD_LG, pady=(0, PAD_LG), sticky="w")

        for label, value in [("1.0×", 1.0), ("1.5×", 1.5), ("1.75×", 1.75), ("2.0×", 2.0)]:
            ctk.CTkButton(
                preset_row, text=label,
                font=micro_font(),
                width=60, height=28,
                corner_radius=RADIUS_SM,
                fg_color=C("bg"), hover_color=C("border"),
                text_color=C("text"), border_color=C("border"), border_width=1,
                command=lambda v=value: self._set_preset(v),
            ).pack(side="left", padx=3)

        # ── Theme section ──
        theme_card = ctk.CTkFrame(self, fg_color=C("card2"), corner_radius=RADIUS_MD)
        theme_card.grid(row=2, column=0, padx=PAD_XL, pady=(0, PAD_MD), sticky="ew")

        ctk.CTkLabel(
            theme_card, text="Theme",
            font=label_bold(), text_color=C("text"), anchor="w",
        ).grid(row=0, column=0, padx=PAD_LG, pady=(PAD_LG, PAD_SM), sticky="w")

        theme_row = ctk.CTkFrame(theme_card, fg_color="transparent")
        theme_row.grid(row=1, column=0, padx=PAD_LG, pady=(0, PAD_LG), sticky="w")

        self._dark_btn = ctk.CTkButton(
            theme_row, text="Dark",
            font=label_font(), width=100, height=34, corner_radius=RADIUS_SM,
            command=lambda: self._set_theme("dark"),
        )
        self._dark_btn.pack(side="left", padx=PAD_SM)

        self._light_btn = ctk.CTkButton(
            theme_row, text="Light",
            font=label_font(), width=100, height=34, corner_radius=RADIUS_SM,
            command=lambda: self._set_theme("light"),
        )
        self._light_btn.pack(side="left", padx=PAD_SM)

        self._refresh_theme_buttons()

        # ── Status ──
        ctk.CTkLabel(
            self, textvariable=self._status_var,
            font=small_font(), text_color=C("green"),
        ).grid(row=3, column=0, padx=PAD_2XL, pady=(0, PAD_SM), sticky="w")

        # ── Done ──
        ctk.CTkButton(
            self, text="Done",
            font=label_bold(),
            width=100, height=38,
            corner_radius=RADIUS_SM,
            fg_color=C("accent"), hover_color=C("accent2"), text_color="#ffffff",
            command=self._done,
        ).grid(row=4, column=0, padx=PAD_2XL, pady=(0, PAD_2XL), sticky="e")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_slider_move(self, value: float) -> None:
        rounded = round(value * 10) / 10
        self._scale_var.set(rounded)
        self._scale_lbl.configure(text=f"{rounded:.2f}×")

    def _set_preset(self, value: float) -> None:
        self._scale_var.set(value)
        self._scale_lbl.configure(text=f"{value:.2f}×")

    def _set_theme(self, mode: str) -> None:
        self._theme_var.set(mode)
        cfg.set_value("theme", mode)
        self._on_theme(mode)
        self._refresh_theme_buttons()
        self._status_var.set(f"Theme: {mode}")

    def _refresh_theme_buttons(self) -> None:
        t = self._theme_var.get()
        self._dark_btn.configure(
            fg_color=C("accent") if t == "dark" else C("card"),
            text_color="#ffffff" if t == "dark" else C("text"),
            border_color=C("border"), border_width=1,
        )
        self._light_btn.configure(
            fg_color=C("accent") if t == "light" else C("card"),
            text_color="#ffffff" if t == "light" else C("text"),
            border_color=C("border"), border_width=1,
        )

    def _done(self) -> None:
        scale = round(self._scale_var.get() * 10) / 10
        cfg.set_value("ui_scale", scale)
        cfg.set_value("theme", self._theme_var.get())
        self._on_scale(scale)
        self.destroy()
