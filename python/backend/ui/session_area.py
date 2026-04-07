"""
session_area.py — Tabbed session panel. Lunar Interface.

Design notes:
  - Empty state is a real first impression, not an afterthought
  - Session tabs are clean, minimal
  - WebSocket chat panel integration
"""
from __future__ import annotations

import subprocess
import threading
import shlex
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Any, Callable

import customtkinter as ctk
import tkinter as tk

from ..ssh import build_ssh_command, get_terminal_emulator, build_terminal_argv, SSHValidationError, SSHSecurityError
from ..config import (
    DEFAULT_AGENT,
    DEFAULT_COMMAND,
    all_preset_commands,
    default_command_for_agent,
    preset_broadcast_applies,
    status_preset_command_for_profile,
)
from ..theme import (
    C, F,
    display_font, title_font, header_font, body_font, body_bold,
    label_font, label_bold, small_font, micro_font, code_font, dim_font,
    PAD_SM, PAD_MD, PAD_LG, PAD_XL, PAD_2XL,
    RADIUS_SM, RADIUS_MD, RADIUS_LG, RADIUS_XL,
)
from .. import audit


@dataclass
class _Session:
    tab_id: str
    profile: dict
    ssh_cmd: Any          # SSHCommand
    process: subprocess.Popen | None = None
    status: str = "ready"
    ws_panel: Any = None  # WsSessionPanel if this is a websocket tab
    log_path: str = ""


class SessionArea(ctk.CTkFrame):
    def __init__(self, master: Any, on_status: Callable[[str], None] | None = None, **kwargs: Any) -> None:
        super().__init__(master, corner_radius=0, **kwargs)
        self._on_status = on_status or (lambda s: None)
        self._sessions: dict[str, _Session] = {}
        self._profile_to_tab: dict[str, str] = {}
        self._counter = 0
        self._broadcast_var = tk.BooleanVar(value=False)
        self._last_open_time: dict[str, float] = {}  # debounce: profile_key → timestamp
        self._DEBOUNCE_S = 1.5  # min seconds between opens for same profile

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_toolbar()
        self._build_tabs()
        self._build_empty()
        self._refresh_visibility()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        self._toolbar = ctk.CTkFrame(self, corner_radius=0, height=48)
        self._toolbar.grid(row=0, column=0, sticky="ew")
        self._toolbar.grid_propagate(False)
        self._toolbar.grid_columnconfigure(1, weight=1)

        self._sessions_lbl = ctk.CTkLabel(
            self._toolbar, text="SESSIONS",
            font=F(12, "bold"),
        )
        self._sessions_lbl.grid(row=0, column=0, padx=PAD_XL, pady=PAD_MD, sticky="w")

        # Right side controls
        self._controls = ctk.CTkFrame(self._toolbar, fg_color="transparent")
        self._controls.grid(row=0, column=2, padx=PAD_LG, pady=PAD_SM)

        self._broadcast_chk = ctk.CTkCheckBox(
            self._controls, text="Broadcast",
            variable=self._broadcast_var,
            font=small_font(),
            height=28,
            corner_radius=4,
            checkbox_width=18, checkbox_height=18,
        )
        self._broadcast_chk.pack(side="left", padx=PAD_MD)

        self._close_btn = ctk.CTkButton(
            self._controls, text="Close All",
            font=small_font(),
            width=80, height=28,
            corner_radius=RADIUS_SM,
            command=self.close_all,
        )
        self._close_btn.pack(side="left", padx=PAD_SM)

    def _build_tabs(self) -> None:
        self._tabs = ctk.CTkTabview(self)
        self._tabs.grid(row=1, column=0, sticky="nsew", padx=PAD_SM, pady=PAD_SM)

    def _build_empty(self) -> None:
        self._empty = ctk.CTkFrame(self, corner_radius=0)
        self._empty.grid(row=1, column=0, sticky="nsew")

        # Centered content
        center = ctk.CTkFrame(self._empty, fg_color="transparent")
        center.place(relx=0.5, rely=0.45, anchor="center")

        # Brand mark
        self._empty_brand = ctk.CTkLabel(
            center, text="ClawTTY",
            font=display_font(),
        )
        self._empty_brand.pack(pady=(0, PAD_SM))

        # Tagline
        self._empty_tag = ctk.CTkLabel(
            center, text="Agent Console",
            font=body_font(),
        )
        self._empty_tag.pack(pady=(0, PAD_2XL))

        # Separator line
        self._empty_sep = ctk.CTkFrame(center, height=1, width=200)
        self._empty_sep.pack(pady=(0, PAD_2XL))

        # Call to action
        self._empty_cta = ctk.CTkLabel(
            center,
            text="Select a profile to connect\nor create a new one to get started",
            font=small_font(),
            justify="center",
        )
        self._empty_cta.pack(pady=(0, PAD_XL))

        # Quick hint
        self._empty_hint = ctk.CTkLabel(
            center,
            text="SSH  ·  WebSocket  ·  Multi-agent",
            font=micro_font(),
        )
        self._empty_hint.pack()

    def _refresh_visibility(self) -> None:
        if self._sessions:
            self._empty.grid_remove()
            self._tabs.grid()
        else:
            self._tabs.grid_remove()
            self._empty.grid()

    # ── Public API ────────────────────────────────────────────────────────────

    def open_session(self, profile: dict) -> str | None:
        import time
        # Debounce — ignore rapid repeated connects for same profile
        profile_key = profile.get("id") or f"{profile.get('host')}:{profile.get('username')}"
        now = time.monotonic()
        last = self._last_open_time.get(profile_key, 0)
        if now - last < self._DEBOUNCE_S:
            return None  # too soon, ignore
        self._last_open_time[profile_key] = now

        profile_id = profile.get("id", "")
        if profile_id and profile_id in self._profile_to_tab:
            tab_id = self._profile_to_tab[profile_id]
            if tab_id in self._sessions:
                conn_type = profile.get("connection_type", "ssh")
                label = f"{profile['name']}  #{tab_id}"
                try:
                    self._tabs.set(label)
                except Exception:
                    pass
                self._on_status(f"Switched to {profile['name']}")
                return tab_id

        conn_type = profile.get("connection_type", "ssh")
        if conn_type == "websocket":
            return self._open_ws_session(profile)
        return self._open_ssh_session(profile)

    def _open_ssh_session(self, profile: dict) -> str | None:
        try:
            ssh_cmd = build_ssh_command(profile)
        except (SSHValidationError, SSHSecurityError) as exc:
            audit.log_blocked(profile.get("name","?"), profile.get("host","?"), profile.get("remote_command","?"), str(exc))
            self._on_status(f"Blocked — {exc}")
            self._error_dialog("Connection Blocked", str(exc))
            return None

        self._counter += 1
        tab_id = str(self._counter)
        label = f"{profile['name']}  #{tab_id}"

        self._tabs.add(label)
        frame = self._tabs.tab(label)
        frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        sess = _Session(tab_id=tab_id, profile=profile, ssh_cmd=ssh_cmd)
        self._sessions[tab_id] = sess
        if profile.get("id"):
            self._profile_to_tab[profile["id"]] = tab_id

        self._fill_ssh_tab(frame, sess, label)
        self._tabs.set(label)
        self._refresh_visibility()
        self._on_status(f"Ready — {profile['name']}")
        return tab_id

    def _open_ws_session(self, profile: dict) -> str | None:
        import webbrowser
        from ..credentials import load_token, CredentialUnavailable, KeyringError

        token: str = ""
        try:
            stored = load_token(profile.get("id", ""))
            if stored:
                token = stored
        except (CredentialUnavailable, KeyringError):
            pass

        self._counter += 1
        tab_id = str(self._counter)
        label = f"{profile['name']}  #{tab_id}"

        self._tabs.add(label)
        frame = self._tabs.tab(label)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        sess = _Session(tab_id=tab_id, profile=profile, ssh_cmd=None)
        self._sessions[tab_id] = sess
        if profile.get("id"):
            self._profile_to_tab[profile["id"]] = tab_id

        # Build connection options card
        ws_url = profile.get("ws_url", "ws://127.0.0.1:18789")
        http_url = ws_url.replace("wss://", "https://").replace("ws://", "http://")
        dashboard_url = f"{http_url}/#token={token}" if token else http_url

        card = ctk.CTkFrame(frame, corner_radius=0, fg_color=C("bg"))
        card.place(relx=0.5, rely=0.5, anchor="center")

        # Profile name
        ctk.CTkLabel(
            card, text=profile["name"],
            font=title_font(), text_color=C("text2"),
        ).pack(pady=(0, PAD_SM))

        ctk.CTkLabel(
            card, text=ws_url,
            font=code_font(13), text_color=C("dim"),
        ).pack(pady=(0, PAD_2XL))

        # Option 1 — Native chat (primary)
        ctk.CTkButton(
            card, text="Open Chat",
            font=label_bold(),
            width=260, height=42, corner_radius=RADIUS_MD,
            fg_color=C("accent"), hover_color=C("accent2"), text_color="#ffffff",
            command=lambda: self._open_ws_chat_panel(profile, tab_id, frame, card, token),
        ).pack(pady=(0, PAD_SM))

        ctk.CTkLabel(
            card, text="Direct WebSocket connection — no browser needed",
            font=micro_font(), text_color=C("dim"),
        ).pack(pady=(0, PAD_LG))

        # Option 2 — Browser
        ctk.CTkButton(
            card, text="Open in Browser",
            font=label_font(),
            width=260, height=36, corner_radius=RADIUS_SM,
            fg_color=C("card2"), hover_color=C("card3"),
            text_color=C("text"), border_color=C("border"), border_width=1,
            command=lambda: (
                webbrowser.open(dashboard_url),
                self._on_status(f"Opened {http_url}"),
            ),
        ).pack(pady=(0, PAD_SM))

        # Option 3 — SSH terminal (if available)
        ssh_host = profile.get("host", "").strip()
        ssh_user = profile.get("user", "").strip()
        ssh_available = bool(ssh_host and ssh_user)

        if ssh_available:
            ctk.CTkButton(
                card, text="SSH Terminal",
                font=label_font(),
                width=260, height=36, corner_radius=RADIUS_SM,
                fg_color=C("card2"), hover_color=C("card3"),
                text_color=C("text"), border_color=C("border"), border_width=1,
                command=lambda: self._open_ssh_from_ws(profile, tab_id),
            ).pack(pady=(0, PAD_SM))

        # Close tab
        ctk.CTkButton(
            card, text="Close",
            font=small_font(),
            width=100, height=30, corner_radius=RADIUS_SM,
            fg_color="transparent", hover_color=C("card2"),
            text_color=C("dim"),
            command=lambda: self.close_tab(tab_id),
        ).pack(pady=(PAD_LG, 0))

        self._tabs.set(label)
        self._refresh_visibility()
        self._on_status(f"Ready — {profile['name']}")
        return tab_id

    def _open_ws_chat_panel(self, profile: dict, tab_id: str, frame, card, token: str) -> None:
        from .ws_session_panel import WsSessionPanel

        # Guard: if a panel already exists for this tab, just focus it — don't create another
        sess = self._sessions.get(tab_id)
        if sess and sess.ws_panel is not None:
            try:
                card.destroy()
            except Exception:
                pass
            return

        card.destroy()
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        panel = WsSessionPanel(
            frame,
            profile=profile,
            token=token,
            on_status=self._on_status,
        )
        panel.grid(row=0, column=0, sticky="nsew")

        # Track the panel so we can guard against duplicates and clean up on close
        if sess:
            sess.ws_panel = panel

        # Close button integrated at bottom
        close_frame = ctk.CTkFrame(frame, fg_color=C("bg2"), height=36)
        close_frame.grid(row=1, column=0, sticky="ew")
        close_frame.grid_propagate(False)

        ctk.CTkButton(
            close_frame, text="Disconnect",
            font=small_font(),
            width=100, height=28, corner_radius=RADIUS_SM,
            fg_color=C("card2"), hover_color=C("red"),
            text_color=C("text"), border_color=C("border"), border_width=1,
            command=lambda: (panel.disconnect(), self.close_tab(tab_id)),
        ).pack(side="right", padx=PAD_LG, pady=PAD_SM)

        ctk.CTkButton(
            close_frame, text="Export Log",
            font=small_font(),
            width=100, height=28, corner_radius=RADIUS_SM,
            fg_color=C("card2"), hover_color=C("border"),
            text_color=C("text"), border_color=C("border"), border_width=1,
            command=lambda: self._export_ws_log(profile, panel),
        ).pack(side="right", padx=(0, PAD_SM), pady=PAD_SM)

        self._on_status(f"Connected — {profile['name']}")

    def _export_ws_log(self, profile: dict, panel: Any) -> None:
        default = self._default_export_path(profile.get("name", "session"))
        save_to = filedialog.asksaveasfilename(
            title="Export Session Log",
            initialdir=str(default.parent),
            initialfile=default.name,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not save_to:
            return
        try:
            text = panel.export_log_text() if hasattr(panel, "export_log_text") else ""
            Path(save_to).write_text(text or "No log data available.\n", encoding="utf-8")
            self._on_status(f"Log exported — {profile.get('name','?')}")
        except Exception as exc:
            self._on_status(f"Export failed — {exc}")

    def _open_ssh_from_ws(self, profile: dict, ws_tab_id: str) -> None:
        ssh_profile = dict(profile)
        ssh_profile["connection_type"] = "ssh"
        ssh_profile.setdefault("agent", DEFAULT_AGENT)
        rc = (ssh_profile.get("remote_command") or "").strip()
        if not rc:
            ssh_profile["remote_command"] = default_command_for_agent(ssh_profile["agent"]) or DEFAULT_COMMAND
        else:
            ssh_profile["remote_command"] = rc
        try:
            from ..ssh import build_ssh_command, get_terminal_emulator, build_terminal_argv
            ssh_cmd = build_ssh_command(ssh_profile)
            term = get_terminal_emulator()
            if not term:
                self._on_status("No terminal emulator found")
                return
            import subprocess
            argv = build_terminal_argv(term, ssh_cmd)
            subprocess.Popen(argv)
            self._on_status(f"SSH terminal launched → {profile.get('host')}")
        except Exception as exc:
            self._on_status(f"SSH failed — {exc}")

    def close_tab(self, tab_id: str) -> None:
        sess = self._sessions.pop(tab_id, None)
        if not sess:
            return
        # Clean up WebSocket panel if present
        if sess.ws_panel is not None:
            try:
                sess.ws_panel.disconnect()
            except Exception:
                pass
            sess.ws_panel = None
        pid = sess.profile.get("id", "")
        if pid and self._profile_to_tab.get(pid) == tab_id:
            del self._profile_to_tab[pid]
        label = f"{sess.profile['name']}  #{tab_id}"
        try:
            self._tabs.delete(label)
        except Exception:
            pass
        self._refresh_visibility()

    def close_all(self) -> None:
        for tid in list(self._sessions):
            self.close_tab(tid)

    def broadcast(self, command: str) -> None:
        if command not in all_preset_commands():
            return
        matched = False
        for s in self._sessions.values():
            if preset_broadcast_applies(s.profile, command):
                self._on_status(f"Broadcast '{command}' → {s.profile['name']}")
                matched = True
        if not matched:
            self._on_status("Broadcast: no session uses this agent preset")

    def broadcast_status_all(self) -> None:
        """Send each session the preset status command for its agent (best-effort messaging)."""
        if not self._sessions:
            self._on_status("Broadcast All: no open sessions")
            return
        for s in self._sessions.values():
            cmd = status_preset_command_for_profile(s.profile)
            if cmd:
                self._on_status(f"Broadcast '{cmd}' → {s.profile['name']}")
            else:
                self._on_status(f"Broadcast skipped → {s.profile['name']} (custom or WebSocket)")

    def get_session_count(self) -> int:
        return len(self._sessions)

    # ── SSH Tab content ───────────────────────────────────────────────────────

    def _fill_ssh_tab(self, frame: ctk.CTkFrame, sess: _Session, tab_label: str) -> None:
        # Connection info card
        info = ctk.CTkFrame(frame, corner_radius=RADIUS_LG, border_width=1, border_color=C("border"))
        info.grid(row=0, column=0, sticky="ew", padx=PAD_XL, pady=(PAD_XL, PAD_MD))
        info.grid_columnconfigure(1, weight=1)

        rows = [
            ("Profile",  sess.profile["name"]),
            ("Host",     f"{sess.profile.get('user','?')}@{sess.profile.get('host','?')}:{sess.profile.get('port',22)}"),
            ("Command",  sess.ssh_cmd.display_cmd),
        ]
        for i, (k, v) in enumerate(rows):
            ctk.CTkLabel(
                info, text=k, font=small_font(),
                text_color=C("dim"), anchor="e", width=80,
            ).grid(row=i, column=0, padx=(PAD_LG, PAD_SM), pady=PAD_SM, sticky="e")

            ctk.CTkLabel(
                info, text=v, font=label_bold(),
                text_color=C("text"), anchor="w",
            ).grid(row=i, column=1, padx=(0, PAD_LG), pady=PAD_SM, sticky="w")

        # Status
        sv = tk.StringVar(value="Ready to connect")
        status_lbl = ctk.CTkLabel(frame, textvariable=sv, font=body_font(), text_color=C("dim"))
        status_lbl.grid(row=1, column=0, pady=PAD_LG)

        # Buttons
        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.grid(row=2, column=0, pady=PAD_SM)

        ctk.CTkButton(
            btns, text="Open Session",
            font=label_bold(),
            width=160, height=42,
            corner_radius=RADIUS_MD,
            fg_color=C("accent"), hover_color=C("accent2"), text_color="#ffffff",
            command=lambda: self._launch(sess, sv),
        ).pack(side="left", padx=PAD_SM)

        ctk.CTkButton(
            btns, text="Close",
            font=label_font(),
            width=100, height=42,
            corner_radius=RADIUS_MD,
            fg_color=C("card2"), hover_color=C("red"),
            text_color=C("text"), border_color=C("border"), border_width=1,
            command=lambda: self.close_tab(sess.tab_id),
        ).pack(side="left", padx=PAD_SM)

        ctk.CTkButton(
            btns, text="Export Log",
            font=label_font(),
            width=120, height=42,
            corner_radius=RADIUS_MD,
            fg_color=C("card2"), hover_color=C("border"),
            text_color=C("text"), border_color=C("border"), border_width=1,
            command=lambda: self._export_ssh_log(sess, sv),
        ).pack(side="left", padx=PAD_SM)

        notes = sess.profile.get("notes", "")
        if notes:
            ctk.CTkLabel(
                frame, text=notes,
                font=small_font(), text_color=C("dim"),
                wraplength=500, justify="left",
            ).grid(row=3, column=0, padx=PAD_XL, pady=(PAD_SM, PAD_LG), sticky="w")

    def _launch(self, sess: _Session, sv: tk.StringVar) -> None:
        term = get_terminal_emulator()
        if not term:
            sv.set("No terminal found — install konsole, gnome-terminal, kitty, or alacritty")
            return

        argv = build_terminal_argv(term, sess.ssh_cmd)
        script_bin = shutil.which("script")
        if script_bin:
            log_dir = Path.home() / ".local" / "share" / "clawtty" / "session-logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            safe_name = "".join(
                c if c.isalnum() or c in ("-", "_", ".") else "_"
                for c in sess.profile.get("name", "session")
            )
            log_path = log_dir / f"{safe_name}-{sess.tab_id}-{ts}.log"
            sess.log_path = str(log_path)

            ssh_cmd = shlex.join(sess.ssh_cmd.argv)
            wrapped = f"{script_bin} -q -f {shlex.quote(str(log_path))} -c {shlex.quote(ssh_cmd)}"
            term_name = Path(term).name
            if term_name == "konsole":
                argv = [term, "-e", "bash", "-lc", wrapped]
            elif term_name in ("gnome-terminal", "kitty", "alacritty"):
                argv = [term, "--", "bash", "-lc", wrapped]
            else:
                argv = [term, "-e", "bash", "-lc", wrapped]
        sv.set(f"Launching {term.split('/')[-1]}…")
        audit.log_connect(sess.profile.get("name","?"), sess.profile.get("host","?"), sess.ssh_cmd.command)
        self._on_status(f"Launched — {sess.profile['name']}")

        def _run() -> None:
            try:
                proc = subprocess.Popen(argv)
                sess.process = proc
                proc.wait()
                sv.set("Session ended")
            except Exception as exc:
                sv.set(f"Error — {exc}")
                audit.log_failed(sess.profile.get("name","?"), sess.profile.get("host","?"), sess.ssh_cmd.command, str(exc))
        threading.Thread(target=_run, daemon=True).start()

    def _default_export_path(self, profile_name: str) -> Path:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in profile_name)
        return Path.home() / "Downloads" / f"clawtty-session-{safe_name} -{ts}.txt"

    def _export_ssh_log(self, sess: _Session, sv: tk.StringVar) -> None:
        default = self._default_export_path(sess.profile.get("name", "session"))
        save_to = filedialog.asksaveasfilename(
            title="Export Session Log",
            initialdir=str(default.parent),
            initialfile=default.name,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not save_to:
            return
        try:
            src = Path(sess.log_path) if sess.log_path else None
            if src and src.exists():
                content = src.read_text(encoding="utf-8", errors="replace")
            else:
                content = (
                    "No captured terminal output is available for this session.\n"
                    "Open a new session and run commands, then export again.\n"
                )
            Path(save_to).write_text(content, encoding="utf-8")
            sv.set(f"✔  Exported log → {save_to}")
            self._on_status(f"Log exported — {sess.profile.get('name','?')}")
        except Exception as exc:
            sv.set(f"❌  Export failed — {exc}")

    def _error_dialog(self, title: str, msg: str) -> None:
        d = ctk.CTkToplevel(self)
        d.title(title)
        d.configure(fg_color=C("card"))
        d.resizable(False, False)
        d.after(100, lambda: d.grab_set() if d.winfo_exists() else None)

        ctk.CTkLabel(
            d, text=title,
            font=header_font(), text_color=C("red"),
        ).pack(padx=PAD_2XL, pady=(PAD_XL, PAD_SM))

        ctk.CTkLabel(
            d, text=msg,
            font=small_font(), text_color=C("text"),
            wraplength=440, justify="left",
        ).pack(padx=PAD_2XL, pady=(0, PAD_XL))

        ctk.CTkButton(
            d, text="OK", font=label_bold(),
            width=90, height=36, corner_radius=RADIUS_SM,
            fg_color=C("accent"), hover_color=C("accent2"), text_color="#ffffff",
            command=d.destroy,
        ).pack(pady=(0, PAD_XL))
        d.wait_window()

    # ── Theme ─────────────────────────────────────────────────────────────────

    def apply_theme(self) -> None:
        self.configure(fg_color=C("bg"))

        # Toolbar
        self._toolbar.configure(fg_color=C("bg"))
        self._sessions_lbl.configure(text_color=C("dim"))
        self._broadcast_chk.configure(
            text_color=C("dim"), fg_color=C("accent"),
            hover_color=C("accent2"), border_color=C("border"),
        )
        self._close_btn.configure(
            fg_color=C("card2"), hover_color=C("red"),
            text_color=C("text"), border_color=C("border"), border_width=1,
        )

        # Tabs
        self._tabs.configure(
            fg_color=C("bg"),
            segmented_button_fg_color=C("card"),
            segmented_button_selected_color=C("accent"),
            segmented_button_selected_hover_color=C("accent2"),
            segmented_button_unselected_color=C("card"),
            segmented_button_unselected_hover_color=C("card2"),
            text_color=C("text"),
        )

        # Empty state
        self._empty.configure(fg_color=C("bg"))
        self._empty_brand.configure(text_color=C("gold"))
        self._empty_tag.configure(text_color=C("dim"))
        self._empty_sep.configure(fg_color=C("border"))
        self._empty_cta.configure(text_color=C("dim"))
        self._empty_hint.configure(text_color=C("faint"))
