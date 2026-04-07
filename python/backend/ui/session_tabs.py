"""
session_tabs.py — Tabbed session panel for ClawTTY v3.
"""

from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from typing import Any, Callable

import customtkinter as ctk
import tkinter as tk

from ..ssh import SSHCommand, build_ssh_command, get_terminal_emulator, build_terminal_argv, SSHValidationError, SSHSecurityError
from ..config import all_preset_commands, preset_broadcast_applies
from ..theme import C, F, label_font, small_font, micro_font

# Backward compat aliases
font = F
tiny_font = micro_font
from .. import audit


@dataclass
class SessionEntry:
    tab_id: str
    profile: dict
    ssh_cmd: SSHCommand
    process: subprocess.Popen | None = None
    status: str = "ready"


class SessionTabs(ctk.CTkFrame):
    """Right-side tabbed panel."""

    def __init__(self, master: Any, on_status_message: Callable[[str], None] | None = None, **kwargs: Any) -> None:
        super().__init__(master, corner_radius=0, **kwargs)

        self._on_status = on_status_message or (lambda msg: None)
        self._sessions: dict[str, SessionEntry] = {}
        self._tab_counter = 0
        self._broadcast_mode = tk.BooleanVar(value=False)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_toolbar()
        self._build_tabs()
        self._build_empty_state()
        self._toggle_empty_state()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        self._toolbar = ctk.CTkFrame(self, corner_radius=0, height=48)
        self._toolbar.grid(row=0, column=0, sticky="ew")
        self._toolbar.grid_columnconfigure(3, weight=1)
        self._toolbar.grid_propagate(False)

        self._sessions_lbl = ctk.CTkLabel(self._toolbar, text="SESSIONS", font=font(12, "bold"))
        self._sessions_lbl.grid(row=0, column=0, padx=14, pady=10, sticky="w")

        self._broadcast_chk = ctk.CTkCheckBox(
            self._toolbar,
            text="Broadcast",
            variable=self._broadcast_mode,
            font=label_font(),
            height=30,
            corner_radius=6,
        )
        self._broadcast_chk.grid(row=0, column=1, padx=12, pady=8)

        self._close_all_btn = ctk.CTkButton(
            self._toolbar,
            text="Close All",
            font=small_font(),
            width=90, height=30,
            corner_radius=8,
            command=self.close_all_tabs,
        )
        self._close_all_btn.grid(row=0, column=2, padx=6, pady=8)

    def _build_tabs(self) -> None:
        self._tabview = ctk.CTkTabview(self)
        self._tabview.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)

    def _build_empty_state(self) -> None:
        self._empty_frame = ctk.CTkFrame(self, corner_radius=0)
        self._empty_frame.grid(row=1, column=0, sticky="nsew")

        ctk.CTkLabel(self._empty_frame, text="🦞", font=ctk.CTkFont(size=52)).place(relx=0.5, rely=0.38, anchor="center")
        self._empty_lbl = ctk.CTkLabel(
            self._empty_frame,
            text="No sessions open.\nSelect a profile and click Connect.",
            font=label_font(),
            justify="center",
        )
        self._empty_lbl.place(relx=0.5, rely=0.52, anchor="center")

    def _toggle_empty_state(self) -> None:
        if self._sessions:
            self._empty_frame.grid_remove()
            self._tabview.grid()
        else:
            self._tabview.grid_remove()
            self._empty_frame.grid()

    # ── Public API ────────────────────────────────────────────────────────────

    def open_session(self, profile: dict) -> str | None:
        try:
            ssh_cmd = build_ssh_command(profile)
        except (SSHValidationError, SSHSecurityError) as exc:
            audit.log_blocked(profile.get("name", "?"), profile.get("host", "?"), profile.get("remote_command", "?"), str(exc))
            self._on_status(f"❌  {exc}")
            self._show_error("Connection Blocked", str(exc))
            return None

        tab_id = self._next_tab_id()
        label = f"{profile['name']} ({tab_id})"

        self._tabview.add(label)
        tab_frame = self._tabview.tab(label)
        tab_frame.grid_rowconfigure(1, weight=1)
        tab_frame.grid_columnconfigure(0, weight=1)

        entry = SessionEntry(tab_id=tab_id, profile=profile, ssh_cmd=ssh_cmd)
        self._sessions[tab_id] = entry

        self._populate_tab(tab_frame, entry, label)
        self._tabview.set(label)
        self._toggle_empty_state()
        self._on_status(f"✔  Session ready: {profile['name']} → {profile['host']}")
        return tab_id

    def close_tab(self, tab_id: str) -> None:
        if tab_id not in self._sessions:
            return
        entry = self._sessions.pop(tab_id)
        label = f"{entry.profile['name']} ({tab_id})"
        try:
            self._tabview.delete(label)
        except Exception:
            pass
        self._toggle_empty_state()

    def close_all_tabs(self) -> None:
        for tab_id in list(self._sessions.keys()):
            self.close_tab(tab_id)

    def broadcast_command(self, command: str) -> None:
        if command not in all_preset_commands():
            self._on_status("❌  Broadcast blocked: not a preset command")
            return
        matched = False
        for entry in self._sessions.values():
            if preset_broadcast_applies(entry.profile, command):
                self._on_status(f"📡  Broadcast '{command}' → {entry.profile['name']} (best-effort)")
                matched = True
        if not matched:
            self._on_status("❌  Broadcast: no session uses this agent preset")

    def get_session_count(self) -> int:
        return len(self._sessions)

    # ── Tab content ───────────────────────────────────────────────────────────

    def _populate_tab(self, frame: ctk.CTkFrame, entry: SessionEntry, tab_label: str) -> None:
        # Info card
        card = ctk.CTkFrame(frame, corner_radius=10)
        card.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        card.grid_columnconfigure(1, weight=1)

        def info_row(r: int, key: str, value: str, val_color: str) -> None:
            ctk.CTkLabel(card, text=key, font=small_font(), anchor="e", width=90).grid(row=r, column=0, padx=(12, 4), pady=4, sticky="e")
            ctk.CTkLabel(card, text=value, font=font(13, "bold"), anchor="w").grid(row=r, column=1, padx=(4, 12), pady=4, sticky="w")

        info_row(0, "Profile:", entry.profile["name"], C("gold"))
        info_row(1, "Host:", f"{entry.profile.get('user','?')}@{entry.profile.get('host','?')}:{entry.profile.get('port',22)}", C("accent"))
        info_row(2, "Command:", entry.ssh_cmd.display_cmd, C("text"))

        status_var = tk.StringVar(value="⏳  Ready to connect")
        status_lbl = ctk.CTkLabel(frame, textvariable=status_var, font=label_font())
        status_lbl.grid(row=1, column=0, pady=12)

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, pady=8)

        ctk.CTkButton(
            btn_row,
            text="▶  Open Session",
            font=font(15, "bold"),
            width=180, height=44,
            corner_radius=10,
            command=lambda: self._launch_terminal(entry, status_var),
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_row,
            text="✕  Close Tab",
            font=label_font(),
            width=120, height=44,
            corner_radius=10,
            command=lambda: self.close_tab(entry.tab_id),
        ).pack(side="left", padx=10)

        notes = entry.profile.get("notes", "")
        if notes:
            ctk.CTkLabel(frame, text=notes, font=small_font(), wraplength=560, justify="left").grid(row=3, column=0, padx=16, pady=(4, 12), sticky="w")

        self.apply_theme()

    def _launch_terminal(self, entry: SessionEntry, status_var: tk.StringVar) -> None:
        terminal = get_terminal_emulator()
        if not terminal:
            msg = "No terminal emulator found (konsole/gnome-terminal/kitty/alacritty/xterm)"
            status_var.set(f"❌  {msg}")
            self._on_status(f"❌  {msg}")
            audit.log_failed(entry.profile.get("name", "?"), entry.profile.get("host", "?"), entry.ssh_cmd.command, msg)
            return

        argv = build_terminal_argv(terminal, entry.ssh_cmd)
        status_var.set(f"🟢  Launching {terminal.split('/')[-1]}…")
        entry.status = "running"
        audit.log_connect(entry.profile.get("name", "?"), entry.profile.get("host", "?"), entry.ssh_cmd.command)
        self._on_status(f"🟢  Launched: {entry.profile['name']} → {entry.ssh_cmd.display_cmd}")

        def _run() -> None:
            try:
                proc = subprocess.Popen(argv)
                entry.process = proc
                proc.wait()
                entry.status = "exited"
                status_var.set("⬛  Session ended")
            except Exception as exc:
                entry.status = "error"
                status_var.set(f"❌  Error: {exc}")
                audit.log_failed(entry.profile.get("name", "?"), entry.profile.get("host", "?"), entry.ssh_cmd.command, str(exc))

        threading.Thread(target=_run, daemon=True).start()

    def _next_tab_id(self) -> str:
        self._tab_counter += 1
        return str(self._tab_counter)

    def _show_error(self, title: str, message: str) -> None:
        d = ctk.CTkToplevel(self)
        d.title(title)
        d.configure(fg_color=C("card"))
        d.resizable(False, False)
        d.after(100, lambda: d.grab_set() if d.winfo_exists() else None)
        ctk.CTkLabel(d, text=f"⛔  {title}", text_color=C("red"), font=font(14, "bold")).pack(padx=24, pady=(20, 8))
        ctk.CTkLabel(d, text=message, text_color=C("text"), font=label_font(), wraplength=420, justify="left").pack(padx=24, pady=(0, 16))
        ctk.CTkButton(d, text="OK", fg_color=C("accent"), hover_color=C("gold"), text_color="#ffffff", font=font(14, "bold"), width=90, height=36, corner_radius=8, command=d.destroy).pack(pady=(0, 20))
        d.wait_window()

    # ── Theme ─────────────────────────────────────────────────────────────────

    def apply_theme(self) -> None:
        self.configure(fg_color=C("bg"))
        self._toolbar.configure(fg_color=C("card"))
        self._sessions_lbl.configure(text_color=C("gold"))
        self._broadcast_chk.configure(text_color=C("text"), fg_color=C("accent"), hover_color=C("gold"), border_color=C("border"))
        self._close_all_btn.configure(fg_color=C("card2"), hover_color=C("red"), text_color=C("text"), border_color=C("border"), border_width=1)
        self._tabview.configure(fg_color=C("card"), segmented_button_fg_color=C("card2"), segmented_button_selected_color=C("accent"), segmented_button_selected_hover_color=C("gold"), segmented_button_unselected_color=C("card2"), segmented_button_unselected_hover_color=C("border"), text_color=C("text"))
        self._empty_frame.configure(fg_color=C("bg"))
        self._empty_lbl.configure(text_color=C("dim"))
