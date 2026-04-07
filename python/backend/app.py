"""
app.py — ClawTTY v3 main window. Lunar Interface design.

Layout:
  ┌────────────────────────────────────────────────────────────┐
  │  Titlebar  (brand · spacer · theme · settings)             │
  ├──────────────┬─────────────────────────────────────────────┤
  │              │                                             │
  │   Sidebar    │          Session area                       │
  │  280px       │   (empty state or tabbed sessions)          │
  │              │                                             │
  ├──────────────┴─────────────────────────────────────────────┤
  │  Macro strip  (collapsed by default)                       │
  ├────────────────────────────────────────────────────────────┤
  │  Status bar                                                │
  └────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import threading
from typing import Any

import customtkinter as ctk
import tkinter as tk

from .theme import (
    C, F, set_mode, toggle, is_dark,
    display_font, title_font, header_font, body_font, body_bold,
    label_font, label_bold, small_font, micro_font, code_font, dim_font,
    PAD_SM, PAD_MD, PAD_LG, PAD_XL, PAD_2XL,
    RADIUS_SM, RADIUS_MD, RADIUS_LG, RADIUS_XL,
)
from .config import all_preset_commands
from .ssh import verify_host_key, trust_host_key, VerificationResult
from .ui.sidebar import ProfileSidebar
from .ui.session_area import SessionArea
from .ui._base import SafeGrabMixin
from .ui.macro_bar import MacroBar
from . import audit
from . import settings as cfg


class ClawTTYApp(ctk.CTk):
    def __init__(self, initial_scale: float = 1.75) -> None:
        prefs = cfg.load()
        set_mode(prefs.get("theme", "dark"))
        super().__init__()

        self._current_scale = initial_scale
        self.title("ClawTTY — Agent Console")
        self.geometry(f"{prefs.get('window_w', 1400)}x{prefs.get('window_h', 900)}")
        self.minsize(1100, 700)

        self._status_var = tk.StringVar(value="")
        self._theme_label = tk.StringVar(
            value="☀" if prefs.get("theme") == "dark" else "🌙"
        )

        # Ensure no transparency — solid window
        self.attributes('-alpha', 1.0)

        self._build_layout()
        self._apply_theme()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Row 0: titlebar — clean, minimal
        self._titlebar = ctk.CTkFrame(self, corner_radius=0, height=52)
        self._titlebar.grid(row=0, column=0, sticky="ew")
        self._titlebar.grid_propagate(False)
        self._titlebar.grid_columnconfigure(1, weight=1)
        self._build_titlebar()

        # Row 1: sidebar + session area
        self._center = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self._center.grid(row=1, column=0, sticky="nsew")
        self._center.grid_rowconfigure(0, weight=1)
        self._center.grid_columnconfigure(1, weight=1)

        self._sidebar = ProfileSidebar(
            self._center,
            on_connect=self._connect_profile,
            on_edit=self._edit_profile,
            on_add=self._add_profile,
            on_status=self._show_status_dashboard,
        )
        self._sidebar.grid(row=0, column=0, sticky="nsew")

        # Subtle divider — just a 1px line, not a wall
        self._divider = ctk.CTkFrame(self._center, width=1, corner_radius=0)
        self._divider.grid(row=0, column=0, sticky="nse")

        self._session_area = SessionArea(self._center, on_status=self._set_status)
        self._session_area.grid(row=0, column=1, sticky="nsew")

        # Row 2: macro bar
        self._macro_bar = MacroBar(
            self,
            on_fire=self._macro_fire,
            on_broadcast=self._macro_broadcast,
            on_broadcast_all=self._macro_broadcast_all,
        )
        self._macro_bar.grid(row=2, column=0, sticky="ew")

        # Row 3: status bar — thin, informational
        self._statusbar = ctk.CTkFrame(self, corner_radius=0, height=32)
        self._statusbar.grid(row=3, column=0, sticky="ew")
        self._statusbar.grid_propagate(False)
        self._statusbar.grid_columnconfigure(0, weight=1)

        self._status_lbl = ctk.CTkLabel(
            self._statusbar,
            textvariable=self._status_var,
            font=micro_font(),
            anchor="w",
        )
        self._status_lbl.grid(row=0, column=0, padx=PAD_LG, sticky="w")

        self._ver_lbl = ctk.CTkLabel(
            self._statusbar,
            text="ClawTTY v3  ·  AI agent SSH  ·  No telemetry",
            font=micro_font(),
        )
        self._ver_lbl.grid(row=0, column=1, padx=PAD_LG, sticky="e")

    def _build_titlebar(self) -> None:
        # Brand mark — the logo IS the brand, no subtitle needed
        self._logo_lbl = ctk.CTkLabel(
            self._titlebar,
            text="ClawTTY",
            font=F(18, "bold"),
        )
        self._logo_lbl.grid(row=0, column=0, padx=PAD_XL, pady=PAD_MD, sticky="w")

        # Version badge
        self._ver_badge = ctk.CTkLabel(
            self._titlebar,
            text="v3",
            font=F(11, "bold"),
            width=28, height=18,
            corner_radius=4,
        )
        self._ver_badge.grid(row=0, column=0, padx=(100, 0), pady=PAD_MD, sticky="w")

        # Spacer (column 1 expands)

        # Right side buttons — minimal, icon-forward
        self._btn_frame = ctk.CTkFrame(self._titlebar, fg_color="transparent")
        self._btn_frame.grid(row=0, column=2, padx=PAD_LG, pady=PAD_SM)

        self._theme_btn = ctk.CTkButton(
            self._btn_frame,
            textvariable=self._theme_label,
            font=F(16),
            width=36, height=36,
            corner_radius=RADIUS_SM,
            command=self._toggle_theme,
        )
        self._theme_btn.pack(side="left", padx=PAD_SM)

        self._audit_btn = ctk.CTkButton(
            self._btn_frame,
            text="Audit Log",
            font=label_font(),
            width=90, height=36,
            corner_radius=RADIUS_SM,
            command=self._show_audit_log,
        )
        self._audit_btn.pack(side="left", padx=PAD_SM)

        self._settings_btn = ctk.CTkButton(
            self._btn_frame,
            text="Settings",
            font=label_font(),
            width=80, height=36,
            corner_radius=RADIUS_SM,
            command=self._show_settings,
        )
        self._settings_btn.pack(side="left", padx=PAD_SM)

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        self.configure(fg_color=C("bg"))

        # Titlebar
        self._titlebar.configure(fg_color=C("bg"))
        self._logo_lbl.configure(text_color=C("gold"))
        self._ver_badge.configure(
            fg_color=C("card2"), text_color=C("dim"),
        )

        # Titlebar buttons — ghost style
        for btn in (self._theme_btn, self._audit_btn, self._settings_btn):
            btn.configure(
                fg_color="transparent", hover_color=C("card2"),
                text_color=C("dim"), border_width=0,
            )

        self._center.configure(fg_color=C("bg"))
        self._divider.configure(fg_color=C("border"))

        # Status bar
        self._statusbar.configure(fg_color=C("bg2"))
        self._status_lbl.configure(text_color=C("dim"))
        self._ver_lbl.configure(text_color=C("faint"))

        # Children
        self._sidebar.apply_theme()
        self._session_area.apply_theme()
        self._macro_bar.apply_theme()

    def _toggle_theme(self) -> None:
        new = toggle()
        self._theme_label.set("🌙" if new == "light" else "☀")
        self._apply_theme()

    # ── Profile actions ───────────────────────────────────────────────────────

    def _connect_profile(self, profile: dict) -> None:
        if profile.get("connection_type") == "websocket":
            self._session_area.open_session(profile)
            return
        self._set_status("Verifying host key…")
        threading.Thread(target=self._verify_and_connect, args=(profile,), daemon=True).start()

    def _verify_and_connect(self, profile: dict) -> None:
        result = verify_host_key(
            profile_name=profile.get("name", "?"),
            host=profile["host"],
            port=int(profile.get("port", 22)),
        )
        self.after(0, lambda: self._handle_verification(profile, result))

    def _handle_verification(self, profile: dict, result: VerificationResult) -> None:
        if result.status == "trusted":
            self._set_status(f"Connected — {profile['name']}")
            self._session_area.open_session(profile)

        elif result.status == "unknown":
            dlg = HostKeyDialog(self, profile=profile, result=result)
            trust_host_key(
                profile_name=profile.get("name", "?"),
                host=profile["host"],
                port=int(profile.get("port", 22)),
                fingerprint=result.fingerprint,
                accepted=dlg.accepted,
            )
            if dlg.accepted:
                self._set_status(f"Connected — {profile['name']}")
                self._session_area.open_session(profile)
            else:
                self._set_status("Host key rejected")

        elif result.status == "mismatch":
            AlertDialog(self, "Host Key Mismatch", result.message, kind="danger")
            self._set_status(f"BLOCKED — key mismatch for {profile['host']}")

        else:
            AlertDialog(self, "Connection Error", result.message, kind="error")
            self._set_status(f"Error — {result.message[:60]}")

    def _edit_profile(self, profile: dict) -> None:
        from .ui.profile_form import ProfileForm
        ProfileForm(self, profile=profile, on_saved=lambda _: self._sidebar.refresh())

    def _add_profile(self) -> None:
        from .ui.profile_form import ProfileForm
        ProfileForm(self, profile=None, on_saved=lambda _: self._sidebar.refresh())

    # ── Macro actions ─────────────────────────────────────────────────────────

    def _macro_fire(self, command: str) -> None:
        self._set_status(f"{command} — open a session first")

    def _macro_broadcast(self, command: str) -> None:
        if command not in all_preset_commands():
            self._set_status("Blocked — not a preset command")
            return
        self._session_area.broadcast(command)
        self._set_status(f"Broadcast '{command}' (see status line per session)")

    def _macro_broadcast_all(self) -> None:
        self._session_area.broadcast_status_all()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str) -> None:
        self.after(0, lambda: self._status_var.set(msg))

    def _show_audit_log(self) -> None:
        AuditLogDialog(self)

    def _show_settings(self) -> None:
        from .ui.settings_dialog import SettingsDialog
        SettingsDialog(
            self,
            on_scale_change=self._apply_scale,
            on_theme_change=self._apply_theme_mode,
        )

    def _show_status_dashboard(self) -> None:
        from .ui.status_dashboard import StatusDashboard
        StatusDashboard(self)

    def _apply_scale(self, scale: float) -> None:
        import customtkinter as ctk
        ctk.set_widget_scaling(scale)
        ctk.set_window_scaling(scale)
        cfg.set_value("ui_scale", scale)
        self._set_status(f"Scale set to {scale:.2f}× — restart for full effect")

    def _apply_theme_mode(self, mode: str) -> None:
        set_mode(mode)
        self._theme_label.set("☀" if mode == "dark" else "🌙")
        cfg.set_value("theme", mode)
        self._apply_theme()


# ── Dialogs ───────────────────────────────────────────────────────────────────

class HostKeyDialog(SafeGrabMixin, ctk.CTkToplevel):
    def __init__(self, master: Any, profile: dict, result: VerificationResult) -> None:
        super().__init__(master)
        self.title("Verify Host Key")
        self.configure(fg_color=C("card"))
        self.resizable(False, False)
        self.after(100, self._safe_grab)
        self.accepted = False

        ctk.CTkLabel(
            self, text="Unknown Host Key",
            font=header_font(), text_color=C("text2"),
        ).pack(padx=PAD_2XL, pady=(PAD_2XL, PAD_SM))

        ctk.CTkLabel(
            self, text=result.message,
            font=small_font(), text_color=C("text"),
            wraplength=480, justify="left",
        ).pack(padx=PAD_2XL, pady=(0, PAD_SM))

        ctk.CTkLabel(
            self, text="Only trust keys you can verify independently.",
            font=micro_font(), text_color=C("gold"),
        ).pack(padx=PAD_2XL, pady=(0, PAD_XL))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=(0, PAD_2XL))

        ctk.CTkButton(
            row, text="Reject", font=label_font(),
            width=120, height=40, corner_radius=RADIUS_SM,
            fg_color=C("card2"), hover_color=C("red"),
            text_color=C("text"), border_color=C("border"), border_width=1,
            command=self._reject,
        ).pack(side="left", padx=PAD_SM)

        ctk.CTkButton(
            row, text="Trust & Connect", font=label_bold(),
            width=160, height=40, corner_radius=RADIUS_SM,
            fg_color=C("accent"), hover_color=C("accent2"),
            text_color="#ffffff",
            command=self._accept,
        ).pack(side="left", padx=PAD_SM)

        self.wait_window()

    def _accept(self) -> None:
        self.accepted = True
        self.destroy()

    def _reject(self) -> None:
        self.destroy()


class AlertDialog(SafeGrabMixin, ctk.CTkToplevel):
    def __init__(self, master: Any, title: str, message: str, kind: str = "error") -> None:
        super().__init__(master)
        self.title(title)
        self.configure(fg_color=C("card"))
        self.resizable(False, False)
        self.after(100, self._safe_grab)

        color = C("red") if kind == "danger" else C("yellow")

        ctk.CTkLabel(
            self, text=title,
            font=header_font(), text_color=color,
        ).pack(padx=PAD_2XL, pady=(PAD_2XL, PAD_SM))

        ctk.CTkLabel(
            self, text=message,
            font=small_font(), text_color=C("text"),
            wraplength=480, justify="left",
        ).pack(padx=PAD_2XL, pady=(0, PAD_XL))

        ctk.CTkButton(
            self, text="OK", font=label_bold(),
            width=100, height=38, corner_radius=RADIUS_SM,
            fg_color=C("accent"), hover_color=C("accent2"),
            text_color="#ffffff",
            command=self.destroy,
        ).pack(pady=(0, PAD_2XL))

        self.wait_window()


class AuditLogDialog(SafeGrabMixin, ctk.CTkToplevel):
    def __init__(self, master: Any) -> None:
        super().__init__(master)
        self.title("Audit Log")
        self.configure(fg_color=C("card"))
        self.geometry("900x560")
        self.after(100, self._safe_grab)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=PAD_XL, pady=(PAD_XL, PAD_SM))

        ctk.CTkLabel(
            header, text="Audit Log",
            font=header_font(), text_color=C("text2"),
        ).pack(side="left")

        ctk.CTkLabel(
            header, text=str(audit.get_log_path()),
            font=micro_font(), text_color=C("dim"),
        ).pack(side="right")

        # Log content
        box = ctk.CTkTextbox(
            self,
            fg_color=C("bg"), text_color=C("text"),
            font=code_font(13),
            corner_radius=RADIUS_MD,
            border_width=1, border_color=C("border"),
        )
        box.pack(fill="both", expand=True, padx=PAD_XL, pady=(0, PAD_SM))

        lines = audit.read_recent(200)
        box.insert("0.0", "\n".join(lines) if lines else "(no entries)")
        box.configure(state="disabled")

        # Close
        ctk.CTkButton(
            self, text="Close", font=label_font(),
            width=90, height=34, corner_radius=RADIUS_SM,
            fg_color=C("card2"), hover_color=C("border"),
            text_color=C("text"), border_color=C("border"), border_width=1,
            command=self.destroy,
        ).pack(pady=(0, PAD_XL))
