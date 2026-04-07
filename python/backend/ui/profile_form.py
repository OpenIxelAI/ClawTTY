"""
profile_form.py — Add/Edit profile dialog. Supports SSH and WebSocket profiles.
"""
from __future__ import annotations

import threading
from pathlib import Path
from tkinter import filedialog
from typing import Any, Callable

import customtkinter as ctk
import tkinter as tk

from ._base import SafeGrabMixin
from ..config import (
    AGENT_CUSTOM,
    AGENT_OPENCLAW,
    DEFAULT_AGENT,
    DEFAULT_COMMAND,
    HERMES_PRESETS,
    OPENCLAW_PRESETS,
    add_profile, update_profile, new_profile, new_ws_profile,
    import_and_save_from_ssh_config,
)

_AGENT_DISPLAY = ("OpenClaw", "Hermes", "Custom")
_AGENT_INTERNAL = ("openclaw", "hermes", "custom")
_AGENT_DISP_TO_INT: dict[str, str] = dict(zip(_AGENT_DISPLAY, _AGENT_INTERNAL))
_AGENT_INT_TO_DISP: dict[str, str] = dict(zip(_AGENT_INTERNAL, _AGENT_DISPLAY))
from ..ssh import validate_profile
from ..credentials import (
    generate_ssh_key,
    save_token,
    load_token,
    delete_token,
    CredentialUnavailable,
    KeyringError,
)
from ..theme import (
    C, F,
    header_font, body_font, body_bold, label_font, label_bold,
    small_font, micro_font, dim_font,
    PAD_SM, PAD_MD, PAD_LG, PAD_XL, PAD_2XL,
    RADIUS_SM, RADIUS_MD, RADIUS_LG,
)


class ProfileForm(SafeGrabMixin, ctk.CTkToplevel):
    def __init__(self, master: Any, profile: dict | None = None, on_saved: Callable[[dict], None] | None = None) -> None:
        super().__init__(master)
        self._is_edit = profile is not None
        self._profile = profile or new_profile()
        self._on_saved = on_saved or (lambda p: None)

        # Current connection type (may change while form is open)
        self._conn_type = self._profile.get("connection_type", "ssh")

        self.title("Edit Profile" if self._is_edit else "New Profile")
        self.configure(fg_color=C("card"))
        self.resizable(False, False)
        self.after(100, self._safe_grab)

        self._vars: dict[str, tk.Variable] = {}
        self._status_var = tk.StringVar(value="")
        self._token_saved_var = tk.StringVar(value="")
        self._suppress_agent_trace = False

        self._build()
        self._load()
        self.wait_window()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        # Title
        ctk.CTkLabel(self,
            text="✎  Edit Profile" if self._is_edit else "＋  New Profile",
            font=header_font(), text_color=C("gold"),
        ).grid(row=0, column=0, padx=28, pady=(28, 4), sticky="w")

        # ── Connection type toggle ──
        toggle_frame = ctk.CTkFrame(self, fg_color=C("card2"), corner_radius=10)
        toggle_frame.grid(row=1, column=0, padx=28, pady=(0, 16), sticky="w")

        ctk.CTkLabel(toggle_frame, text="Type:", font=label_font(), text_color=C("dim")).pack(
            side="left", padx=(12, 8), pady=10)

        self._ssh_btn = ctk.CTkButton(
            toggle_frame, text="🖥  SSH",
            font=label_font(), width=110, height=34, corner_radius=8,
            command=lambda: self._switch_type("ssh"),
        )
        self._ssh_btn.pack(side="left", padx=(0, 4), pady=8)

        self._ws_btn = ctk.CTkButton(
            toggle_frame, text="🌐  WebSocket",
            font=label_font(), width=130, height=34, corner_radius=8,
            command=lambda: self._switch_type("websocket"),
        )
        self._ws_btn.pack(side="left", padx=(0, 12), pady=8)

        # ── SSH fields card ──
        self._ssh_card = ctk.CTkFrame(self, fg_color=C("card2"), corner_radius=12)
        self._ssh_card.grid(row=2, column=0, padx=24, sticky="ew")
        self._ssh_card.grid_columnconfigure(1, weight=1)
        self._build_ssh_fields(self._ssh_card)

        # ── WebSocket fields card ──
        self._ws_card = ctk.CTkFrame(self, fg_color=C("card2"), corner_radius=12)
        self._ws_card.grid(row=2, column=0, padx=24, sticky="ew")
        self._ws_card.grid_columnconfigure(1, weight=1)
        self._build_ws_fields(self._ws_card)

        # ── Status label ──
        self._status_lbl = ctk.CTkLabel(
            self, textvariable=self._status_var,
            font=label_font(), text_color=C("red"), wraplength=520,
        )
        self._status_lbl.grid(row=3, column=0, padx=28, pady=(12, 0), sticky="w")

        # ── Utility buttons ──
        self._util_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._util_frame.grid(row=4, column=0, padx=24, pady=(10, 0), sticky="w")

        self._test_btn = ctk.CTkButton(
            self._util_frame, text="🔌  Test Connection",
            font=label_font(), height=38, corner_radius=8,
            fg_color=C("card2"), hover_color=C("border"), text_color=C("text"),
            border_color=C("border"), border_width=1, command=self._test,
        )
        self._test_btn.pack(side="left", padx=4)

        self._keygen_btn = ctk.CTkButton(
            self._util_frame, text="🔑  Generate SSH Key",
            font=label_font(), height=38, corner_radius=8,
            fg_color=C("card2"), hover_color=C("border"), text_color=C("text"),
            border_color=C("border"), border_width=1, command=self._keygen,
        )
        self._keygen_btn.pack(side="left", padx=4)

        self._import_btn = ctk.CTkButton(
            self._util_frame, text="📂  Import ~/.ssh/config",
            font=label_font(), height=38, corner_radius=8,
            fg_color=C("card2"), hover_color=C("border"), text_color=C("text"),
            border_color=C("border"), border_width=1, command=self._import,
        )
        self._import_btn.pack(side="left", padx=4)

        # ── Save / Cancel ──
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=5, column=0, padx=24, pady=(14, 28), sticky="e")
        ctk.CTkButton(
            actions, text="Cancel", font=label_font(), width=110, height=42, corner_radius=10,
            fg_color=C("card2"), hover_color=C("border"), text_color=C("text"),
            border_color=C("border"), border_width=1, command=self.destroy,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            actions, text="Save Profile", font=F(15, "bold"), width=148, height=42, corner_radius=10,
            fg_color=C("accent"), hover_color=C("gold"), text_color="#ffffff", command=self._save,
        ).pack(side="left", padx=8)

        # Apply initial type visibility
        self._apply_type_ui()

    def _build_ssh_fields(self, form: ctk.CTkFrame) -> None:
        row_idx = 0

        def field(lbl: str, key: str, ph: str = "") -> None:
            nonlocal row_idx
            ctk.CTkLabel(form, text=lbl, font=label_font(), text_color=C("dim"), anchor="e", width=130).grid(
                row=row_idx, column=0, padx=(16, 10), pady=8, sticky="e")
            var = tk.StringVar()
            self._vars[key] = var
            ctk.CTkEntry(
                form, textvariable=var, placeholder_text=ph,
                fg_color=C("bg"), border_color=C("border"),
                text_color=C("text"), placeholder_text_color=C("dim"),
                font=body_font(), height=42, corner_radius=8,
            ).grid(row=row_idx, column=1, padx=(0, 16), pady=8, sticky="ew")
            row_idx += 1

        field("Name *",  "name",  "My agent host")
        field("Group",   "group", "Default")
        field("Host *",  "host",  "192.168.1.10  or  hostname")
        field("User *",  "user",  "youruser")
        field("Port",    "port",  "22")

        # Identity file + browse
        ctk.CTkLabel(form, text="Identity File", font=label_font(), text_color=C("dim"), anchor="e", width=130).grid(
            row=row_idx, column=0, padx=(16, 10), pady=8, sticky="e")
        id_frame = ctk.CTkFrame(form, fg_color="transparent")
        id_frame.grid(row=row_idx, column=1, padx=(0, 16), pady=8, sticky="ew")
        id_frame.grid_columnconfigure(0, weight=1)
        id_var = tk.StringVar()
        self._vars["identity_file"] = id_var
        ctk.CTkEntry(
            id_frame, textvariable=id_var, placeholder_text="~/.ssh/id_ed25519  (optional)",
            fg_color=C("bg"), border_color=C("border"), text_color=C("text"),
            placeholder_text_color=C("dim"), font=body_font(), height=42, corner_radius=8,
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            id_frame, text="Browse", font=label_font(), width=100, height=42, corner_radius=8,
            fg_color=C("card"), hover_color=C("border"), text_color=C("text"),
            border_color=C("border"), border_width=1, command=self._browse,
        ).grid(row=0, column=1, padx=(8, 0))
        row_idx += 1

        # Agent (SSH target CLI)
        ctk.CTkLabel(form, text="Agent *", font=label_font(), text_color=C("dim"), anchor="e", width=130).grid(
            row=row_idx, column=0, padx=(16, 10), pady=8, sticky="e")
        agent_disp_var = tk.StringVar(value=_AGENT_INT_TO_DISP[DEFAULT_AGENT])
        self._vars["agent_display"] = agent_disp_var
        self._agent_menu = ctk.CTkOptionMenu(
            form, values=list(_AGENT_DISPLAY), variable=agent_disp_var,
            fg_color=C("bg"), button_color=C("accent"), button_hover_color=C("gold"),
            dropdown_fg_color=C("card"), dropdown_text_color=C("text"), dropdown_hover_color=C("accent"),
            text_color=C("text"), font=body_font(), height=42, corner_radius=8,
            command=lambda _v: self._on_agent_changed(),
        )
        self._agent_menu.grid(row=row_idx, column=1, padx=(0, 16), pady=8, sticky="w")
        row_idx += 1

        # Command: preset menu OR custom entry
        ctk.CTkLabel(form, text="Command *", font=label_font(), text_color=C("dim"), anchor="e", width=130).grid(
            row=row_idx, column=0, padx=(16, 10), pady=8, sticky="e")
        cmd_var = tk.StringVar(value=DEFAULT_COMMAND)
        self._vars["remote_command"] = cmd_var
        cmd_frame = ctk.CTkFrame(form, fg_color="transparent")
        cmd_frame.grid(row=row_idx, column=1, padx=(0, 16), pady=8, sticky="ew")
        cmd_frame.grid_columnconfigure(0, weight=1)
        self._cmd_menu = ctk.CTkOptionMenu(
            cmd_frame, values=list(OPENCLAW_PRESETS), variable=cmd_var,
            fg_color=C("bg"), button_color=C("accent"), button_hover_color=C("gold"),
            dropdown_fg_color=C("card"), dropdown_text_color=C("text"), dropdown_hover_color=C("accent"),
            text_color=C("text"), font=body_font(), height=42, corner_radius=8,
        )
        self._cmd_menu.grid(row=0, column=0, sticky="ew")
        self._cmd_custom = ctk.CTkEntry(
            cmd_frame, textvariable=cmd_var,
            placeholder_text="Remote command (single line, no shell metacharacters)",
            fg_color=C("bg"), border_color=C("border"),
            text_color=C("text"), placeholder_text_color=C("dim"),
            font=body_font(), height=42, corner_radius=8,
        )
        self._cmd_custom.grid(row=0, column=0, sticky="ew")
        self._cmd_custom.grid_remove()
        row_idx += 1

        # Notes (SSH)
        ctk.CTkLabel(form, text="Notes", font=label_font(), text_color=C("dim"), anchor="e", width=130).grid(
            row=row_idx, column=0, padx=(16, 10), pady=8, sticky="ne")
        self._notes = ctk.CTkTextbox(
            form, fg_color=C("bg"), border_color=C("border"),
            text_color=C("text"), font=body_font(),
            height=88, corner_radius=8, border_width=1,
        )
        self._notes.grid(row=row_idx, column=1, padx=(0, 16), pady=8, sticky="ew")
        row_idx += 1

        # Per-profile API token (stored in keychain only)
        ctk.CTkLabel(form, text="API Token", font=label_font(), text_color=C("dim"), anchor="e", width=130).grid(
            row=row_idx, column=0, padx=(16, 10), pady=(2, 8), sticky="e")
        token_frame = ctk.CTkFrame(form, fg_color="transparent")
        token_frame.grid(row=row_idx, column=1, padx=(0, 16), pady=(2, 8), sticky="ew")
        token_frame.grid_columnconfigure(0, weight=1)
        tok_var = tk.StringVar()
        self._vars["api_token"] = tok_var
        ctk.CTkEntry(
            token_frame, textvariable=tok_var, placeholder_text="Optional token (stored in keychain)",
            show="●",
            fg_color=C("bg"), border_color=C("border"),
            text_color=C("text"), placeholder_text_color=C("dim"),
            font=body_font(), height=42, corner_radius=8,
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            token_frame, text="Clear", font=small_font(), width=72, height=42, corner_radius=8,
            fg_color=C("card"), hover_color=C("border"), text_color=C("text"),
            border_color=C("border"), border_width=1, command=lambda: self._clear_saved_token(),
        ).grid(row=0, column=1, padx=(8, 0))

        ctk.CTkLabel(
            form, textvariable=self._token_saved_var, font=micro_font(), text_color=C("dim"), anchor="w"
        ).grid(row=row_idx + 1, column=1, padx=(0, 16), pady=(0, 6), sticky="w")

    def _build_ws_fields(self, form: ctk.CTkFrame) -> None:
        row_idx = 0

        def entry_row(lbl: str, key: str, ph: str = "", show: str = "") -> None:
            nonlocal row_idx
            ctk.CTkLabel(form, text=lbl, font=label_font(), text_color=C("dim"), anchor="e", width=130).grid(
                row=row_idx, column=0, padx=(16, 10), pady=8, sticky="e")
            var = tk.StringVar()
            self._vars[key] = var
            ctk.CTkEntry(
                form, textvariable=var, placeholder_text=ph, show=show,
                fg_color=C("bg"), border_color=C("border"),
                text_color=C("text"), placeholder_text_color=C("dim"),
                font=body_font(), height=42, corner_radius=8,
            ).grid(row=row_idx, column=1, padx=(0, 16), pady=8, sticky="ew")
            row_idx += 1

        entry_row("Name *",    "ws_name",  "Home Gateway")
        entry_row("Group",     "ws_group", "WebSocket")
        entry_row("URL *",     "ws_url",   "ws://192.168.1.10:18789  or  wss://…")
        # Token field — password-style; value is stored in keychain, shown masked
        entry_row("API Token", "ws_token", "Gateway auth token (stored in keychain)", show="●")

        # Security hint for ws://
        self._ws_warn_lbl = ctk.CTkLabel(
            form,
            text="⚠  Use wss:// for remote gateways. ws:// is only safe on localhost.",
            font=small_font(), text_color=C("gold"), anchor="w",
        )
        self._ws_warn_lbl.grid(row=row_idx, column=0, columnspan=2, padx=16, pady=(0, 4), sticky="w")
        row_idx += 1

        # Bind URL field to toggle the warning
        self._vars.get("ws_url") and self._vars["ws_url"].trace_add(
            "write", lambda *_: self._check_ws_url_warn()
        )

        # Notes (WS)
        ctk.CTkLabel(form, text="Notes", font=label_font(), text_color=C("dim"), anchor="e", width=130).grid(
            row=row_idx, column=0, padx=(16, 10), pady=8, sticky="ne")
        self._ws_notes = ctk.CTkTextbox(
            form, fg_color=C("bg"), border_color=C("border"),
            text_color=C("text"), font=body_font(),
            height=72, corner_radius=8, border_width=1,
        )
        self._ws_notes.grid(row=row_idx, column=1, padx=(0, 16), pady=8, sticky="ew")

    # ── Type switching ────────────────────────────────────────────────────────

    def _switch_type(self, conn_type: str) -> None:
        self._conn_type = conn_type
        self._apply_type_ui()

    def _apply_type_ui(self) -> None:
        """Show/hide the correct form card and toggle button states."""
        is_ssh = self._conn_type == "ssh"

        # Toggle button appearance
        self._ssh_btn.configure(
            fg_color=C("accent") if is_ssh else C("card2"),
            text_color="#ffffff" if is_ssh else C("text"),
        )
        self._ws_btn.configure(
            fg_color=C("accent") if not is_ssh else C("card2"),
            text_color="#ffffff" if not is_ssh else C("text"),
        )

        if is_ssh:
            self._ws_card.grid_remove()
            self._ssh_card.grid()
            self._keygen_btn.configure(state="normal")
            self._import_btn.configure(state="normal")
        else:
            self._ssh_card.grid_remove()
            self._ws_card.grid()
            self._keygen_btn.configure(state="disabled")
            self._import_btn.configure(state="disabled")

        self._check_ws_url_warn()

    def _agent_internal(self) -> str:
        disp = self._vars.get("agent_display", tk.StringVar(value=_AGENT_INT_TO_DISP[DEFAULT_AGENT])).get()
        return _AGENT_DISP_TO_INT.get(disp, DEFAULT_AGENT)

    def _on_agent_changed(self) -> None:
        if self._suppress_agent_trace:
            return
        a = self._agent_internal()
        cmd = self._vars["remote_command"].get().strip()
        if a == AGENT_CUSTOM:
            self._cmd_menu.grid_remove()
            self._cmd_custom.grid()
            return
        self._cmd_custom.grid_remove()
        self._cmd_menu.grid()
        presets = list(OPENCLAW_PRESETS if a == AGENT_OPENCLAW else HERMES_PRESETS)
        self._cmd_menu.configure(values=presets)
        if cmd in presets:
            self._vars["remote_command"].set(cmd)
        else:
            self._vars["remote_command"].set(presets[0])

    def _apply_agent_command_ui(self) -> None:
        """Show preset menu vs custom entry; align command with presets when not custom."""
        self._suppress_agent_trace = True
        try:
            a = self._agent_internal()
            if a == AGENT_CUSTOM:
                self._cmd_menu.grid_remove()
                self._cmd_custom.grid()
                return
            self._cmd_custom.grid_remove()
            self._cmd_menu.grid()
            presets = list(OPENCLAW_PRESETS if a == AGENT_OPENCLAW else HERMES_PRESETS)
            self._cmd_menu.configure(values=presets)
            cur = self._vars["remote_command"].get().strip()
            if cur not in presets:
                self._vars["remote_command"].set(presets[0])
        finally:
            self._suppress_agent_trace = False

    def _check_ws_url_warn(self) -> None:
        """Show the wss:// warning when appropriate."""
        if not hasattr(self, "_ws_warn_lbl"):
            return
        if self._conn_type != "websocket":
            self._ws_warn_lbl.grid_remove()
            return
        url = self._vars.get("ws_url", tk.StringVar()).get()
        if url.startswith("ws://"):
            host = url[5:].split("/")[0].split(":")[0]
            if host not in ("localhost", "127.0.0.1", "::1"):
                self._ws_warn_lbl.grid()
                return
        self._ws_warn_lbl.grid_remove()

    def _set_token_saved_indicator(self, saved: bool) -> None:
        self._token_saved_var.set("Saved token: ••••••••" if saved else "Saved token: none")

    def _clear_saved_token(self) -> None:
        pid = self._profile.get("id", "")
        if not pid:
            self._vars.get("api_token", tk.StringVar()).set("")
            self._vars.get("ws_token", tk.StringVar()).set("")
            self._set_token_saved_indicator(False)
            return
        try:
            deleted = delete_token(pid)
            self._vars.get("api_token", tk.StringVar()).set("")
            self._vars.get("ws_token", tk.StringVar()).set("")
            self._set_token_saved_indicator(False)
            if deleted:
                self._status_var.set("✔  Saved token cleared")
            else:
                self._status_var.set("✔  No saved token existed")
        except (CredentialUnavailable, KeyringError) as exc:
            self._status_var.set(f"⛔  Keyring error: {exc}")

    # ── Load / collect ────────────────────────────────────────────────────────

    def _load(self) -> None:
        p = self._profile
        conn_type = p.get("connection_type", "ssh")
        self._conn_type = conn_type

        if conn_type == "ssh":
            self._suppress_agent_trace = True
            try:
                for key in ("name", "group", "host", "user", "identity_file"):
                    self._vars[key].set(p.get(key, ""))
                self._vars["port"].set(str(p.get("port", 22)))
                agent = p.get("agent", DEFAULT_AGENT)
                self._vars["agent_display"].set(_AGENT_INT_TO_DISP.get(agent, "OpenClaw"))
                self._vars["remote_command"].set(p.get("remote_command", DEFAULT_COMMAND))
            finally:
                self._suppress_agent_trace = False
            self._apply_agent_command_ui()
            notes = p.get("notes", "")
            self._notes.delete("0.0", "end")
            if notes:
                self._notes.insert("0.0", notes)
            # token is keychain-only; never persisted in profile json
            if self._is_edit and p.get("id"):
                try:
                    has_token = bool(load_token(p["id"]))
                    self._set_token_saved_indicator(has_token)
                except (CredentialUnavailable, KeyringError):
                    self._set_token_saved_indicator(False)
            else:
                self._set_token_saved_indicator(False)
        else:
            self._vars["ws_name"].set(p.get("name", ""))
            self._vars["ws_group"].set(p.get("group", "WebSocket"))
            self._vars["ws_url"].set(p.get("ws_url", "ws://127.0.0.1:18789"))
            # Load token from keychain if editing
            if self._is_edit and p.get("id"):
                try:
                    has_token = bool(load_token(p["id"]))
                    self._set_token_saved_indicator(has_token)
                except (CredentialUnavailable, KeyringError):
                    self._set_token_saved_indicator(False)
            notes_ws = p.get("notes", "")
            self._ws_notes.delete("0.0", "end")
            if notes_ws:
                self._ws_notes.insert("0.0", notes_ws)

        self._apply_type_ui()

    def _collect_ssh(self) -> dict:
        p = dict(self._profile)
        p["connection_type"] = "ssh"
        for key in ("name", "group", "host", "user", "identity_file", "remote_command"):
            p[key] = self._vars[key].get().strip()
        p["agent"] = self._agent_internal()
        p["group"] = p["group"] or "Default"
        p["notes"] = self._notes.get("0.0", "end").strip()
        try:
            p["port"] = int(self._vars["port"].get().strip() or "22")
        except ValueError:
            p["port"] = 22
        return p

    def _collect_ws(self) -> tuple[dict, str]:
        """Returns (profile_dict_without_token, raw_token)."""
        p = dict(self._profile)
        p["connection_type"] = "websocket"
        p["name"]   = self._vars["ws_name"].get().strip()
        p["group"]  = self._vars["ws_group"].get().strip() or "WebSocket"
        p["ws_url"] = self._vars["ws_url"].get().strip()
        p["notes"]  = self._ws_notes.get("0.0", "end").strip()
        raw_token   = self._vars["ws_token"].get()
        return p, raw_token

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save(self) -> None:
        if self._conn_type == "ssh":
            p = self._collect_ssh()
            errors = validate_profile(p)
            if errors:
                self._status_var.set("⛔  " + "  ·  ".join(errors))
                return
            saved = update_profile(p) if self._is_edit else add_profile(p)
            token = self._vars.get("api_token", tk.StringVar()).get().strip()
            if token:
                try:
                    save_token(saved["id"], token)
                    self._set_token_saved_indicator(True)
                except (CredentialUnavailable, KeyringError) as exc:
                    self._status_var.set(f"⛔  Keyring error: {exc}")
                    return
                finally:
                    token = "\x00" * len(token)
            self._on_saved(saved)
            self.destroy()

        else:  # websocket
            p, token = self._collect_ws()
            errs: list[str] = []
            if not p["name"]:
                errs.append("Name is required")
            if not p["ws_url"]:
                errs.append("URL is required")
            elif not (p["ws_url"].startswith("ws://") or p["ws_url"].startswith("wss://")):
                errs.append("URL must start with ws:// or wss://")
            if errs:
                self._status_var.set("⛔  " + "  ·  ".join(errs))
                return

            saved = update_profile(p) if self._is_edit else add_profile(p)
            # Store token in keychain
            if token:
                try:
                    save_token(saved["id"], token)
                except (CredentialUnavailable, KeyringError) as exc:
                    self._status_var.set(f"⛔  Keyring error: {exc}")
                    return
                finally:
                    token = "\x00" * len(token)  # wipe local copy

            self._on_saved(saved)
            self.destroy()

    # ── Test connection ───────────────────────────────────────────────────────

    def _test(self) -> None:
        if self._conn_type == "ssh":
            self._test_ssh()
        else:
            self._test_ws()

    def _test_ssh(self) -> None:
        p = self._collect_ssh()
        errs = validate_profile(p)
        if errs:
            self._status_var.set("⛔  " + "  ·  ".join(errs))
            return
        self._status_var.set("⏳  Testing SSH connection…")
        def _do() -> None:
            from ..ssh import fetch_host_key, SSHSecurityError
            try:
                info = fetch_host_key(p["host"], int(p.get("port", 22)))
                msg = f"✔  Reachable  ·  {info.key_type}  ·  {info.fingerprint_sha256}"
            except SSHSecurityError as exc:
                msg = f"❌  {exc}"
            self.after(0, lambda: self._status_var.set(msg))
        threading.Thread(target=_do, daemon=True).start()

    def _test_ws(self) -> None:
        p, token = self._collect_ws()
        url = p.get("ws_url", "")
        if not url:
            self._status_var.set("⛔  URL is required for test")
            return
        if not token and self._profile.get("id"):
            try:
                token = load_token(self._profile["id"]) or ""
            except (CredentialUnavailable, KeyringError):
                token = ""
        if not token:
            self._status_var.set("⛔  API token is required for test")
            return
        self._status_var.set("⏳  Testing WebSocket connection…")
        def _do() -> None:
            from ..ws_client import GatewayClient, ConnState
            client = GatewayClient()
            ok = client.connect(url, token)
            client.disconnect()
            if ok:
                msg = "✔  WebSocket handshake successful — gateway reachable"
            else:
                msg = "❌  WebSocket handshake failed — check URL and token"
            self.after(0, lambda: self._status_var.set(msg))
        threading.Thread(target=_do, daemon=True).start()

    # ── SSH-only helpers ──────────────────────────────────────────────────────

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select SSH Identity File",
            initialdir=str(Path.home() / ".ssh"),
            filetypes=[("All files", "*"), ("PEM keys", "*.pem")],
        )
        if path:
            self._vars["identity_file"].set(path)

    def _keygen(self) -> None:
        KeyGenDialog(self, self._vars.get("identity_file"))

    def _import(self) -> None:
        added, skipped = import_and_save_from_ssh_config()
        self._status_var.set(f"✔  Imported {added} profile(s) from ~/.ssh/config  ({skipped} skipped)")


class KeyGenDialog(SafeGrabMixin, ctk.CTkToplevel):
    def __init__(self, master: Any, identity_var: tk.StringVar | None = None) -> None:
        super().__init__(master)
        self.title("Generate SSH Key")
        self.configure(fg_color=C("card"))
        self.resizable(False, False)
        self.after(100, self._safe_grab)
        self._identity_var = identity_var
        self._status_var = tk.StringVar(value="")
        self._build()
        self.wait_window()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Generate SSH Key Pair", font=header_font(), text_color=C("gold")).pack(padx=28, pady=(28, 10))

        form = ctk.CTkFrame(self, fg_color=C("card2"), corner_radius=12)
        form.pack(padx=24, pady=8, fill="x")
        form.grid_columnconfigure(1, weight=1)

        def row(r: int, lbl: str) -> None:
            ctk.CTkLabel(form, text=lbl, font=label_font(), text_color=C("dim"), anchor="e", width=110).grid(
                row=r, column=0, padx=(14, 10), pady=8, sticky="e")

        row(0, "Key path")
        self._path_var = tk.StringVar(value=str(Path.home() / ".ssh" / "id_ed25519_clawtty"))
        pf = ctk.CTkFrame(form, fg_color="transparent")
        pf.grid(row=0, column=1, padx=(0, 14), pady=8, sticky="ew")
        pf.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(pf, textvariable=self._path_var, fg_color=C("bg"), border_color=C("border"),
                     text_color=C("text"), font=body_font(), height=40, corner_radius=8).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(pf, text="Browse", font=label_font(), width=90, height=40, corner_radius=8,
                      fg_color=C("card"), hover_color=C("border"), text_color=C("text"),
                      border_color=C("border"), border_width=1, command=self._browse).grid(row=0, column=1, padx=(8,0))

        row(1, "Key type")
        self._type_var = tk.StringVar(value="ed25519")
        ctk.CTkOptionMenu(form, values=["ed25519", "rsa"], variable=self._type_var,
                          fg_color=C("bg"), button_color=C("accent"), button_hover_color=C("gold"),
                          dropdown_fg_color=C("card"), dropdown_text_color=C("text"),
                          text_color=C("text"), font=body_font(), height=40, corner_radius=8,
        ).grid(row=1, column=1, padx=(0,14), pady=8, sticky="w")

        row(2, "Comment")
        self._comment_var = tk.StringVar(value="clawtty-key")
        ctk.CTkEntry(form, textvariable=self._comment_var, fg_color=C("bg"), border_color=C("border"),
                     text_color=C("text"), font=body_font(), height=40, corner_radius=8,
        ).grid(row=2, column=1, padx=(0,14), pady=8, sticky="ew")

        ctk.CTkLabel(self, textvariable=self._status_var, font=label_font(), text_color=C("accent"), wraplength=440).pack(padx=20, pady=(6,0))

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(pady=(12, 24))
        ctk.CTkButton(btns, text="Cancel", font=label_font(), width=110, height=42, corner_radius=10,
                      fg_color=C("card2"), hover_color=C("border"), text_color=C("text"),
                      border_color=C("border"), border_width=1, command=self.destroy).pack(side="left", padx=10)
        ctk.CTkButton(btns, text="Generate", font=F(15, "bold"), width=130, height=42, corner_radius=10,
                      fg_color=C("accent"), hover_color=C("gold"), text_color="#ffffff", command=self._gen).pack(side="left", padx=10)

    def _browse(self) -> None:
        path = filedialog.asksaveasfilename(title="Save SSH Key As", initialdir=str(Path.home() / ".ssh"), initialfile="id_ed25519_clawtty")
        if path:
            self._path_var.set(path)

    def _gen(self) -> None:
        key_path = self._path_var.get().strip()
        if not key_path:
            self._status_var.set("⛔  Key path is required")
            return
        self._status_var.set("⏳  Generating key…")
        def _do() -> None:
            result = generate_ssh_key(key_path, key_type=self._type_var.get(), comment=self._comment_var.get().strip() or "clawtty-key")
            if result.success:
                msg = f"✔  {result.private_key_path}\n{result.fingerprint}"
                if self._identity_var is not None:
                    self.after(0, lambda: self._identity_var.set(str(result.private_key_path)))
            else:
                msg = f"❌  {result.message}"
            self.after(0, lambda: self._status_var.set(msg))
        threading.Thread(target=_do, daemon=True).start()
