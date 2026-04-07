"""
ws_session_panel.py — Live WebSocket session panel. Lunar Interface.

Design notes:
  - Agent messages have a subtle left accent bar, not full border
  - Timestamps fade to near-invisible unless contextually needed
  - Input has a clean focus state
  - Status dot pulses conceptually (color-coded, not animated)
"""
from __future__ import annotations

import threading
import time
import tkinter as tk
import logging
from datetime import datetime
from typing import Any

import customtkinter as ctk

from ..theme import (
    C, F,
    header_font, body_font, body_bold, label_font, label_bold,
    small_font, micro_font, code_font, dim_font,
    PAD_SM, PAD_MD, PAD_LG, PAD_XL, PAD_2XL,
    RADIUS_SM, RADIUS_MD, RADIUS_LG,
)
from ..ws_client import GatewayClient, ConnState
from .. import audit

_logger = logging.getLogger("clawtty.ws_session_panel")

# ── State colors ─────────────────────────────────────────────────────────────

_STATE_COLORS: dict[ConnState, str] = {
    ConnState.DISCONNECTED: "#6b7d94",  # dim
    ConnState.CONNECTING:   "#d4af37",  # gold
    ConnState.CONNECTED:    "#4ade80",  # green
    ConnState.ERROR:        "#e05252",  # ember
}

_STATE_LABELS: dict[ConnState, str] = {
    ConnState.DISCONNECTED: "Disconnected",
    ConnState.CONNECTING:   "Connecting…",
    ConnState.CONNECTED:    "Connected",
    ConnState.ERROR:        "Connection Error",
}


class WsSessionPanel(ctk.CTkFrame):
    """
    Live chat panel for WebSocket gateway sessions.
    """

    def __init__(
        self,
        master: Any,
        profile: dict,
        token: str,
        on_status: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, corner_radius=0, **kwargs)
        self._profile    = profile
        self._token      = token
        self._on_status  = on_status or (lambda s: None)
        self._client     = GatewayClient()
        self._session_key = "main"
        self._session_list: list[str] = []
        self._streaming_msg_lbl = None  # ref to current streaming bubble label
        self._log_lines: list[str] = []

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build()
        self.apply_theme()

        # Listen for all likely event names the gateway might use
        self._client.on_event("chat.message", self._on_chat_message)
        self._client.on_event("chat", self._on_chat_event)
        self._client.on_event("agent", self._on_agent_event)
        self._client.on_event("agent.message", self._on_chat_message)
        self._client.on_event("*", self._on_any_event)  # debug catch-all
        self._client.on_state_change(self._on_state_change)

        threading.Thread(target=self._do_connect, daemon=True, name="ws-panel-connect").start()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # ── Top bar ──
        self._topbar = ctk.CTkFrame(self, corner_radius=0, height=48)
        self._topbar.grid(row=0, column=0, sticky="ew")
        self._topbar.grid_propagate(False)
        self._topbar.grid_columnconfigure(2, weight=1)

        # Status dot
        self._dot_canvas = tk.Canvas(
            self._topbar, width=12, height=12,
            highlightthickness=0, bd=0,
        )
        self._dot_canvas.grid(row=0, column=0, padx=(PAD_LG, PAD_SM), pady=PAD_LG)
        self._dot_id = self._dot_canvas.create_oval(1, 1, 11, 11, fill=C("dim"), outline="")

        # State label
        self._state_var = tk.StringVar(value="Connecting…")
        self._state_lbl = ctk.CTkLabel(
            self._topbar,
            textvariable=self._state_var,
            font=small_font(),
        )
        self._state_lbl.grid(row=0, column=1, padx=(0, PAD_LG), pady=PAD_MD, sticky="w")

        # Session selector
        self._session_var = tk.StringVar(value="main")
        self._session_menu = ctk.CTkOptionMenu(
            self._topbar,
            values=["main"],
            variable=self._session_var,
            font=small_font(),
            width=160, height=30,
            corner_radius=RADIUS_SM,
            command=self._on_session_selected,
        )
        self._session_menu.grid(row=0, column=2, padx=PAD_SM, pady=PAD_SM, sticky="w")

        # Reconnect
        self._reconnect_btn = ctk.CTkButton(
            self._topbar,
            text="Reconnect",
            font=small_font(),
            width=90, height=30,
            corner_radius=RADIUS_SM,
            command=self._manual_reconnect,
        )
        self._reconnect_btn.grid(row=0, column=3, padx=PAD_SM, pady=PAD_SM)
        self._reconnect_btn.configure(state="disabled")

        # Info strip
        self._info_var = tk.StringVar(value="")
        self._info_lbl = ctk.CTkLabel(
            self._topbar,
            textvariable=self._info_var,
            font=micro_font(),
            anchor="e",
        )
        self._info_lbl.grid(row=0, column=4, padx=PAD_LG, pady=PAD_MD, sticky="e")

        # ── Message feed ──
        self._feed_frame = ctk.CTkScrollableFrame(self, corner_radius=0)
        self._feed_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self._feed_frame.grid_columnconfigure(0, weight=1)
        self._feed_row = 0

        # ── Input area ──
        self._input_bar = ctk.CTkFrame(self, corner_radius=0, height=72)
        self._input_bar.grid(row=2, column=0, sticky="ew")
        self._input_bar.grid_propagate(False)
        self._input_bar.grid_columnconfigure(0, weight=1)

        self._input_box = ctk.CTkTextbox(
            self._input_bar,
            font=body_font(),
            height=48,
            corner_radius=RADIUS_SM,
            border_width=1,
            wrap="word",
        )
        self._input_box.grid(row=0, column=0, padx=(PAD_LG, PAD_SM), pady=PAD_MD, sticky="ew")
        # Enter sends, Ctrl+Enter adds newline
        self._input_box.bind("<Return>", self._on_enter)
        self._input_box.bind("<KP_Enter>", self._on_enter)
        self._input_box.bind("<Control-Return>", lambda e: None)  # allow newline
        # Copy/paste
        self._input_box.bind("<Control-c>", lambda e: self._input_box.event_generate("<<Copy>>"))
        self._input_box.bind("<Control-v>", lambda e: self._input_box.event_generate("<<Paste>>"))
        self._input_box.bind("<Control-a>", lambda e: (self._input_box.tag_add("sel", "1.0", "end-1c"), "break")[1])

        self._send_btn = ctk.CTkButton(
            self._input_bar,
            text="Send",
            font=label_bold(),
            width=72, height=48,
            corner_radius=RADIUS_SM,
            command=self._send_message,
        )
        self._send_btn.grid(row=0, column=1, padx=(0, PAD_LG), pady=PAD_MD)
        self._send_btn.configure(state="disabled")

    # ── Connect / disconnect ──────────────────────────────────────────────────

    def _do_connect(self) -> None:
        url   = self._profile.get("ws_url", "")
        token = self._token
        name  = self._profile.get("name", "?")

        if not url:
            self._update_state_ui(ConnState.ERROR)
            self.after(0, lambda: self._on_status("No WebSocket URL"))
            return

        audit.log("WS_PANEL_CONNECT", name, url, "", "PENDING", "Initiating connection")
        # Safety-first default: one-shot connect only.
        # Operator can explicitly click Reconnect for another attempt.
        ok = self._client.connect(url, token, auto_reconnect=False)

        if ok:
            self.after(0, self._post_connect)
        # Do NOT set ERROR here on failure — the state callback from _managed_connect_loop
        # already handles all state transitions. Setting ERROR here would override a
        # CONNECTED state that fired moments earlier from the background loop.

    def _post_connect(self) -> None:
        self._send_btn.configure(state="normal")
        self._reconnect_btn.configure(state="disabled")
        self._refresh_sessions()
        self._refresh_status()
        self._on_status(f"Connected — {self._profile.get('name','?')}")
        self._add_system_message("Connected to gateway")

    def disconnect(self) -> None:
        try:
            self._client.disconnect()
        except Exception:
            pass

    def _manual_reconnect(self) -> None:
        # Fully stop old connection (blocks until thread exits) then reconnect.
        # Using _stop_existing avoids double-connection race with auto-reconnect.
        self._update_state_ui(ConnState.CONNECTING)
        self._on_status(f"Reconnecting to {self._profile.get('name','?')}…")
        threading.Thread(target=self._do_connect, daemon=True, name="ws-reconnect").start()

    # ── State change ──────────────────────────────────────────────────────────

    def _on_state_change(self, state: ConnState) -> None:
        self.after(0, lambda s=state: self._update_state_ui(s))

    def _update_state_ui(self, state: ConnState) -> None:
        _logger.debug("UI state dot -> %s", state.value)
        color = _STATE_COLORS.get(state, C("dim"))
        label = _STATE_LABELS.get(state, str(state.value))

        self._dot_canvas.itemconfig(self._dot_id, fill=color)
        self._state_var.set(label)

        if state == ConnState.CONNECTED:
            self._send_btn.configure(state="normal")
            self._reconnect_btn.configure(state="disabled")
        elif state in (ConnState.DISCONNECTED, ConnState.ERROR):
            self._send_btn.configure(state="disabled")
            self._reconnect_btn.configure(state="normal")
            # Don't spam system messages — the reconnect loop handles it automatically
            # Only show error on first disconnect, not on every reconnect cycle

    # ── Sessions list ─────────────────────────────────────────────────────────

    def _refresh_sessions(self) -> None:
        def _fetch() -> None:
            resp = self._client.list_sessions()
            if resp and resp.get("ok"):
                payload = resp.get("payload", {})
                sessions = payload.get("sessions", payload) if isinstance(payload, dict) else payload
                if isinstance(sessions, list):
                    keys = [str(s.get("key", s.get("id", "main"))) for s in sessions if isinstance(s, dict)]
                    if not keys:
                        keys = ["main"]
                    self.after(0, lambda k=keys: self._set_session_list(k))
        threading.Thread(target=_fetch, daemon=True, name="ws-sessions-list").start()

    def _set_session_list(self, keys: list[str]) -> None:
        self._session_list = keys
        self._session_menu.configure(values=keys)
        if self._session_key not in keys and keys:
            self._session_key = keys[0]
            self._session_var.set(keys[0])

    def _on_session_selected(self, value: str) -> None:
        self._session_key = value
        self._add_system_message(f"Switched to session: {value}")

    # ── Gateway status ────────────────────────────────────────────────────────

    def _refresh_status(self) -> None:
        def _fetch() -> None:
            resp = self._client.get_status()
            if resp and resp.get("ok"):
                p = resp.get("payload", {})
                parts: list[str] = []
                if p.get("version"):
                    parts.append(f"v{p['version']}")
                if p.get("model"):
                    parts.append(p["model"])
                if p.get("uptime") is not None:
                    uptime_s = int(p["uptime"])
                    h, r = divmod(uptime_s, 3600)
                    m, s = divmod(r, 60)
                    parts.append(f"up {h:02d}:{m:02d}:{s:02d}")
                info_text = "  ·  ".join(parts) if parts else ""
                self.after(0, lambda t=info_text: self._info_var.set(t))
        threading.Thread(target=_fetch, daemon=True, name="ws-status-fetch").start()

    # ── Message send ──────────────────────────────────────────────────────────

    def _on_enter(self, event=None) -> str:
        """Enter sends the message. Return 'break' to prevent newline insertion."""
        self._send_message()
        return "break"

    def _send_message(self) -> None:
        text = self._input_box.get("0.0", "end").strip()
        if not text:
            return
        if not self._client.is_connected:
            self._on_status("Not connected")
            return

        # Finalize any in-progress streaming message
        self._finalize_stream()

        self._input_box.delete("0.0", "end")
        self._add_user_bubble(text)

        def _do_send() -> None:
            resp = self._client.send_message(self._session_key, text)
            if resp is None or not resp.get("ok"):
                err = "Send failed" if resp is None else resp.get("error", {}).get("message", "Send failed")
                self.after(0, lambda m=err: self._add_system_message(m))
        threading.Thread(target=_do_send, daemon=True, name="ws-send").start()

    # ── Incoming events ───────────────────────────────────────────────────────

    def _on_chat_message(self, payload: dict) -> None:
        try:
            self.after(0, lambda p=payload: self._safe_handle_chat(p))
        except Exception as exc:
            _logger.warning("chat.message handler scheduling failed: %s", exc)

    def _on_chat_event(self, payload: dict) -> None:
        """Handle generic 'chat' events."""
        try:
            _logger.debug(
                "chat event: role=%s keys=%s",
                payload.get("role", "?"),
                list(payload.keys()) if isinstance(payload, dict) else "?",
            )
            self.after(0, lambda p=payload: self._safe_handle_chat(p))
        except Exception as exc:
            _logger.warning("chat handler scheduling failed: %s", exc)

    def _on_agent_event(self, payload: dict) -> None:
        """Handle 'agent' events — skip streaming, let chat handle full messages."""
        pass  # chat events contain complete text

    def _on_any_event(self, frame: dict) -> None:
        """Debug catch-all."""
        try:
            event_name = frame.get("event", "unknown") if isinstance(frame, dict) else "unknown"
            if event_name in ("tick", "health", "presence", "ping"):
                return
            payload = frame.get("payload", frame.get("data", {})) if isinstance(frame, dict) else {}
            preview = ""
            if isinstance(payload, dict):
                for key in ("content", "message", "text"):
                    if key in payload:
                        val = payload[key]
                        preview = str(val)[:80] if val else ""
                        break
            _logger.debug(
                "ws event: %s: %s",
                event_name,
                preview or (list(payload.keys()) if isinstance(payload, dict) else "?"),
            )
        except Exception as exc:
            _logger.debug("catch-all event logging failed: %s", exc)

    def _safe_handle_chat(self, payload: dict) -> None:
        """Crash-safe wrapper for _handle_chat_message."""
        try:
            self._handle_chat_message(payload)
        except Exception as exc:
            _logger.exception("chat handler crashed: %s", exc)

    def _handle_chat_message(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            return

        role = payload.get("role", payload.get("sender", ""))

        # Skip user messages (we already show them when sent)
        if role in ("user", "human"):
            return

        text = ""

        # Try content field first (streaming chat events)
        content = payload.get("content", "")
        if content:
            text = self._extract_text(content)

        # Try message field (state-change chat events)
        if not text:
            message = payload.get("message", "")
            if isinstance(message, dict):
                # message: {role: 'assistant', content: [...]}
                msg_role = message.get("role", "")
                if msg_role in ("user", "human"):
                    return
                msg_content = message.get("content", "")
                text = self._extract_text(msg_content)
            elif isinstance(message, str) and message:
                text = message

        # Try other fields
        if not text:
            for key in ("text", "reply"):
                if key in payload:
                    val = payload[key]
                    if isinstance(val, str) and val.strip():
                        text = val
                        break

        if not text or not text.strip():
            return

        text = text.strip()
        _logger.debug("showing agent chat text (%d chars)", len(text))
        self._show_agent_message(text)

    def _extract_text(self, content) -> str:
        """Extract plain text from various content formats."""
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    t = block.get("text", "")
                    if t and isinstance(t, str):
                        text_parts.append(t)
                elif isinstance(block, str):
                    text_parts.append(block)
            return "\n".join(text_parts)

        # If it's a dict somehow, try to get text from it
        if isinstance(content, dict):
            return content.get("text", content.get("message", ""))

        return ""

    # ── Message bubbles ───────────────────────────────────────────────────────

    def _timestamp(self) -> str:
        return datetime.now().strftime("%H:%M")

    def _show_agent_message(self, text: str) -> None:
        """Show or update the current agent message (handles streaming updates)."""
        if hasattr(self, '_streaming_msg_lbl') and self._streaming_msg_lbl is not None:
            # Update existing streaming bubble
            try:
                self._streaming_msg_lbl.configure(text=text)
                self._scroll_feed()
                return
            except Exception:
                # Widget destroyed, create new
                self._streaming_msg_lbl = None

        self._add_agent_bubble(text)

    def _finalize_stream(self) -> None:
        """Mark current streaming message as complete."""
        self._streaming_msg_lbl = None

    def _add_agent_bubble(self, text: str) -> None:
        """Agent message — left aligned with subtle accent bar."""
        row = self._feed_row
        self._feed_row += 1

        outer = ctk.CTkFrame(self._feed_frame, fg_color="transparent")
        outer.grid(row=row, column=0, sticky="ew", padx=PAD_MD, pady=(PAD_SM, 1))
        outer.grid_columnconfigure(1, weight=1)

        # Accent bar
        bar = ctk.CTkFrame(outer, width=3, corner_radius=2, fg_color=C("accent"))
        bar.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(0, PAD_SM), pady=2)

        # Content
        content = ctk.CTkFrame(outer, fg_color="transparent")
        content.grid(row=0, column=1, sticky="ew")
        content.grid_columnconfigure(0, weight=1)

        # Timestamp
        ts = ctk.CTkLabel(
            content, text=self._timestamp(),
            font=micro_font(), text_color=C("faint"), anchor="w",
        )
        ts.grid(row=0, column=0, sticky="w")

        # Message text
        msg = ctk.CTkLabel(
            content, text=text, font=body_font(),
            text_color=C("text"), fg_color="transparent",
            anchor="w", justify="left", wraplength=600,
        )
        msg.grid(row=1, column=0, sticky="w", pady=(0, PAD_SM))

        # Store ref for streaming updates
        self._streaming_msg_lbl = msg
        self._log_lines.append(f"[{self._timestamp()}] AGENT: {text}")

        self._scroll_feed()

    def _add_user_bubble(self, text: str) -> None:
        """User message — right aligned, subtle card."""
        row = self._feed_row
        self._feed_row += 1

        outer = ctk.CTkFrame(self._feed_frame, fg_color="transparent")
        outer.grid(row=row, column=0, sticky="ew", padx=PAD_MD, pady=(PAD_SM, 1))
        outer.grid_columnconfigure(0, weight=1)

        bubble = ctk.CTkFrame(
            outer, corner_radius=RADIUS_MD,
            fg_color=C("card2"), border_width=0,
        )
        bubble.grid(row=0, column=0, sticky="e")

        ts = ctk.CTkLabel(
            bubble, text=self._timestamp(),
            font=micro_font(), text_color=C("faint"),
            fg_color="transparent", anchor="e",
        )
        ts.grid(row=0, column=0, padx=PAD_MD, pady=(PAD_SM, 0), sticky="e")

        msg = ctk.CTkLabel(
            bubble, text=text, font=body_font(),
            text_color=C("text"), fg_color="transparent",
            anchor="e", justify="right", wraplength=500,
        )
        msg.grid(row=1, column=0, padx=PAD_MD, pady=(0, PAD_SM), sticky="e")
        self._log_lines.append(f"[{self._timestamp()}] USER: {text}")

        self._scroll_feed()

    def _add_system_message(self, text: str) -> None:
        """Centered system message — minimal, faint."""
        row = self._feed_row
        self._feed_row += 1

        lbl = ctk.CTkLabel(
            self._feed_frame,
            text=text,
            font=micro_font(),
            text_color=C("faint"),
            anchor="center",
        )
        lbl.grid(row=row, column=0, padx=PAD_MD, pady=PAD_SM, sticky="ew")
        self._log_lines.append(f"[{self._timestamp()}] SYSTEM: {text}")

        self._scroll_feed()

    def _scroll_feed(self) -> None:
        try:
            self._feed_frame._parent_canvas.yview_moveto(1.0)  # type: ignore[attr-defined]
        except Exception:
            pass

    def export_log_text(self) -> str:
        """Return full text transcript for export."""
        if not self._log_lines:
            return "No WebSocket chat output captured.\n"
        return "\n".join(self._log_lines) + "\n"

    # ── Theme ─────────────────────────────────────────────────────────────────

    def apply_theme(self) -> None:
        self.configure(fg_color=C("bg"))

        # Top bar
        self._topbar.configure(fg_color=C("bg2"))
        self._dot_canvas.configure(bg=C("bg2"))
        self._state_lbl.configure(text_color=C("text"))
        self._info_lbl.configure(text_color=C("dim"))

        self._session_menu.configure(
            fg_color=C("card"),
            button_color=C("accent"),
            button_hover_color=C("accent2"),
            dropdown_fg_color=C("card"),
            dropdown_text_color=C("text"),
            dropdown_hover_color=C("accent"),
            text_color=C("text"),
        )
        self._reconnect_btn.configure(
            fg_color=C("card2"), hover_color=C("border"),
            text_color=C("text"), border_color=C("border"), border_width=1,
        )

        # Feed
        self._feed_frame.configure(fg_color=C("bg"))

        # Input
        self._input_bar.configure(fg_color=C("bg2"))
        self._input_box.configure(
            fg_color=C("card"), border_color=C("border"),
            text_color=C("text"),
        )
        self._send_btn.configure(
            fg_color=C("accent"), hover_color=C("accent2"),
            text_color="#ffffff",
        )
