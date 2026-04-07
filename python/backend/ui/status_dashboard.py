"""
status_dashboard.py — agent status dashboard panel.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from urllib.parse import urlparse
from typing import Any

import customtkinter as ctk

from ._base import SafeGrabMixin
from ..config import load_profiles
from ..credentials import load_token, CredentialUnavailable, KeyringError
from ..status_cache import load_status_cache, save_status_cache
from ..theme import C, header_font, body_font, label_font, label_bold, micro_font
from ..ws_client import GatewayClient


class StatusDashboard(SafeGrabMixin, ctk.CTkToplevel):
    def __init__(self, master: Any) -> None:
        super().__init__(master)
        self.title("Agent Status Dashboard")
        self.configure(fg_color=C("card"))
        self.geometry("980x560")
        self.minsize(860, 460)
        self.after(80, self._safe_grab)

        self._cache = load_status_cache()
        self._rows: dict[str, dict[str, ctk.CTkLabel]] = {}
        self._build()
        self._load_rows()
        self.refresh_all()
        self.wait_window()

    def _build(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self, fg_color=C("card2"), corner_radius=10, height=54)
        top.grid(row=0, column=0, padx=14, pady=(14, 8), sticky="ew")
        top.grid_propagate(False)
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text="Agent Status", font=header_font(), text_color=C("gold")).grid(
            row=0, column=0, padx=14, pady=10, sticky="w"
        )
        ctk.CTkButton(
            top, text="Refresh All", font=label_bold(), width=120, height=34, corner_radius=8,
            fg_color=C("accent"), hover_color=C("accent2"), text_color="#ffffff",
            command=self.refresh_all,
        ).grid(row=0, column=1, padx=14, pady=10, sticky="e")

        table = ctk.CTkScrollableFrame(self, fg_color=C("bg"), corner_radius=10)
        table.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="nsew")
        table.grid_columnconfigure(0, weight=2)
        table.grid_columnconfigure(1, weight=2)
        table.grid_columnconfigure(2, weight=1)
        table.grid_columnconfigure(3, weight=1)
        table.grid_columnconfigure(4, weight=2)
        self._table = table

        headers = ("Name", "Host", "Agent", "Status", "Last Connected")
        for i, h in enumerate(headers):
            ctk.CTkLabel(table, text=h, font=label_bold(), text_color=C("dim")).grid(
                row=0, column=i, padx=8, pady=(8, 6), sticky="w"
            )

    def _profile_host(self, p: dict) -> str:
        host = (p.get("host") or "").strip()
        if host:
            return host
        ws = (p.get("ws_url") or "").strip()
        if ws:
            return urlparse(ws).hostname or ws
        return "—"

    def _row_last_seen(self, profile_id: str) -> str:
        v = self._cache.get(profile_id, {}).get("last_seen", "")
        if not v:
            return "Never"
        return str(v)

    def _load_rows(self) -> None:
        for w in self._table.winfo_children():
            info = w.grid_info()
            if int(info.get("row", 0)) > 0:
                w.destroy()
        self._rows.clear()

        profiles = load_profiles()
        for idx, p in enumerate(profiles, start=1):
            pid = p.get("id", f"row-{idx}")
            host = self._profile_host(p)
            agent = p.get("agent", "websocket" if p.get("connection_type") == "websocket" else "ssh")
            ctk.CTkLabel(self._table, text=p.get("name", "Unnamed"), font=body_font(), text_color=C("text")).grid(
                row=idx, column=0, padx=8, pady=6, sticky="w"
            )
            ctk.CTkLabel(self._table, text=host, font=body_font(), text_color=C("dim")).grid(
                row=idx, column=1, padx=8, pady=6, sticky="w"
            )
            ctk.CTkLabel(self._table, text=str(agent), font=body_font(), text_color=C("text")).grid(
                row=idx, column=2, padx=8, pady=6, sticky="w"
            )
            status_lbl = ctk.CTkLabel(self._table, text="Checking…", font=label_font(), text_color=C("gold"))
            status_lbl.grid(row=idx, column=3, padx=8, pady=6, sticky="w")
            last_lbl = ctk.CTkLabel(self._table, text=self._row_last_seen(pid), font=micro_font(), text_color=C("dim"))
            last_lbl.grid(row=idx, column=4, padx=8, pady=6, sticky="w")
            self._rows[pid] = {"status": status_lbl, "last": last_lbl}

    def _check_profile(self, p: dict) -> tuple[bool, str]:
        ws_url = (p.get("ws_url") or "").strip()
        if not ws_url:
            host = (p.get("host") or "").strip()
            if host:
                ws_url = f"ws://{host}:18789"
        if not ws_url:
            return False, "Offline"

        token = ""
        pid = p.get("id", "")
        if pid:
            try:
                token = load_token(pid) or ""
            except (CredentialUnavailable, KeyringError):
                token = ""

        done = {"ok": False}

        def _run() -> None:
            c = GatewayClient()
            ok = c.connect(ws_url, token, auto_reconnect=False)
            c.disconnect()
            done["ok"] = ok

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=5.0)
        if t.is_alive():
            return False, "Offline"
        return (done["ok"], "Online" if done["ok"] else "Offline")

    def refresh_all(self) -> None:
        profiles = load_profiles()
        for p in profiles:
            pid = p.get("id", "")
            if pid in self._rows:
                self._rows[pid]["status"].configure(text="Checking…", text_color=C("gold"))

        def _worker(p: dict) -> None:
            pid = p.get("id", "")
            online, text = self._check_profile(p)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            def _apply() -> None:
                row = self._rows.get(pid)
                if not row:
                    return
                row["status"].configure(
                    text=text,
                    text_color="#4ade80" if online else C("red"),
                )
                if online:
                    self._cache.setdefault(pid, {})["last_seen"] = now
                    row["last"].configure(text=now)
            self.after(0, _apply)

        for p in profiles:
            threading.Thread(target=_worker, args=(p,), daemon=True).start()

        def _save_later() -> None:
            time.sleep(0.4)
            save_status_cache(self._cache)

        threading.Thread(target=_save_later, daemon=True).start()

