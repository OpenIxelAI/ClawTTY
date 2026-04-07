"""
sidebar.py — Profile sidebar. Lunar Interface design.

Design notes:
  - Cards are clickable (single click = connect, right-click = menu)
  - No ▶ button clutter — the card IS the button
  - Selected card has a left accent bar (like Slack's active channel)
  - Hover lifts the card subtly
  - Connection type shown as a small icon badge, not text
  - Group headers are minimal uppercase labels
"""
from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

import customtkinter as ctk

from ..config import load_profiles, get_profiles_by_group, delete_profile, duplicate_profile
from ._base import SafeGrabMixin
from ..theme import (
    C, F,
    title_font, header_font, body_font, body_bold, label_font, label_bold,
    small_font, micro_font, dim_font,
    PAD_SM, PAD_MD, PAD_LG, PAD_XL, PAD_2XL,
    RADIUS_SM, RADIUS_MD, RADIUS_LG,
)


class ProfileSidebar(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        on_connect: Callable[[dict], None],
        on_edit: Callable[[dict], None],
        on_add: Callable[[], None],
        on_status: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, corner_radius=0, width=280, **kwargs)
        self.grid_propagate(False)

        self._on_connect = on_connect
        self._on_edit = on_edit
        self._on_add = on_add
        self._on_status = on_status or (lambda: None)
        self._selected_id: str = ""

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build()
        self.apply_theme()
        self.refresh()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # ── Header ──
        self._header = ctk.CTkFrame(self, corner_radius=0, height=56)
        self._header.grid(row=0, column=0, sticky="ew")
        self._header.grid_propagate(False)
        self._header.grid_columnconfigure(0, weight=1)

        self._header_lbl = ctk.CTkLabel(
            self._header, text="PROFILES",
            font=F(12, "bold"),
        )
        self._header_lbl.grid(row=0, column=0, padx=PAD_XL, pady=PAD_LG, sticky="w")

        self._add_btn = ctk.CTkButton(
            self._header, text="+",
            font=F(18, "bold"),
            width=36, height=36,
            corner_radius=RADIUS_SM,
            command=self._on_add,
        )
        self._add_btn.grid(row=0, column=1, padx=PAD_MD, pady=PAD_MD)

        self._status_btn = ctk.CTkButton(
            self._header, text="◉",
            font=F(14, "bold"),
            width=36, height=36,
            corner_radius=RADIUS_SM,
            command=self._on_status,
        )
        self._status_btn.grid(row=0, column=2, padx=(0, PAD_MD), pady=PAD_MD)

        # ── Search ──
        self._search_wrap = ctk.CTkFrame(self, corner_radius=0, height=48)
        self._search_wrap.grid(row=1, column=0, sticky="ew", padx=PAD_MD, pady=(PAD_SM, 0))
        self._search_wrap.grid_columnconfigure(0, weight=1)

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._rebuild())

        self._search_entry = ctk.CTkEntry(
            self._search_wrap,
            textvariable=self._search_var,
            placeholder_text="Search profiles…",
            font=small_font(),
            height=34,
            corner_radius=RADIUS_SM,
            border_width=1,
        )
        # Ensure placeholder text is visible
        self._search_entry.configure(placeholder_text_color=C("dim"))
        self._search_entry.grid(row=0, column=0, sticky="ew", pady=PAD_SM)

        # ── Scrollable list ──
        self._scroll = ctk.CTkScrollableFrame(self, corner_radius=0)
        self._scroll.grid(row=2, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._profiles = load_profiles()
        self._rebuild()

    def _rebuild(self) -> None:
        for w in self._scroll.winfo_children():
            w.destroy()

        q = self._search_var.get().lower().strip()
        by_group = get_profiles_by_group()
        row = 0

        for group, profiles in by_group.items():
            matches = [
                p for p in profiles
                if not q
                or q in p["name"].lower()
                or q in p.get("host", "").lower()
                or q in p.get("user", "").lower()
                or q in p.get("ws_url", "").lower()
                or q in group.lower()
            ]
            if not matches:
                continue

            # Group label — uppercase, readable
            g_lbl = ctk.CTkLabel(
                self._scroll,
                text=group.upper(),
                font=F(12, "bold"),
                anchor="w",
                height=26,
            )
            g_lbl.grid(row=row, column=0, sticky="ew", padx=PAD_XL, pady=(PAD_LG, PAD_SM))
            g_lbl.configure(text_color=C("accent"))
            row += 1

            for p in matches:
                card = self._make_card(p)
                card.grid(row=row, column=0, sticky="ew", padx=PAD_SM, pady=2)
                row += 1

    def _make_card(self, profile: dict) -> ctk.CTkFrame:
        is_ws = profile.get("connection_type") == "websocket"
        is_selected = profile.get("id") == self._selected_id

        # Outer frame — this IS the button
        card = ctk.CTkFrame(
            self._scroll,
            corner_radius=RADIUS_MD,
            border_width=0,
            cursor="hand2",
        )
        card.grid_columnconfigure(1, weight=1)

        # Left accent bar (visible when selected)
        accent_bar = ctk.CTkFrame(
            card, width=3, corner_radius=2,
            fg_color=C("accent2") if is_selected else "transparent",
        )
        accent_bar.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(PAD_SM, 0), pady=PAD_SM)

        # Content area
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.grid(row=0, column=1, sticky="ew", padx=(PAD_SM, PAD_MD), pady=(PAD_MD, 0))
        content.grid_columnconfigure(0, weight=1)

        # Profile name + type badge
        name_frame = ctk.CTkFrame(content, fg_color="transparent")
        name_frame.grid(row=0, column=0, sticky="ew")
        name_frame.grid_columnconfigure(0, weight=1)

        name_lbl = ctk.CTkLabel(
            name_frame, text=profile["name"],
            font=label_bold(), anchor="w",
        )
        name_lbl.grid(row=0, column=0, sticky="w")

        # Type badge — small but readable
        badge_text = "WS" if is_ws else "SSH"
        badge_color = C("accent") if is_ws else C("text")
        badge_bg = C("card3") if is_ws else C("bg2")
        badge = ctk.CTkLabel(
            name_frame, text=badge_text,
            font=F(10, "bold"),
            width=30, height=18,
            corner_radius=4,
            fg_color=badge_bg,
            text_color=badge_color,
        )
        badge.grid(row=0, column=1, padx=(PAD_SM, 0))

        # Subtitle — host or URL
        if is_ws:
            sub_text = profile.get("ws_url", "ws://…")
            # Shorten for display
            if len(sub_text) > 32:
                sub_text = sub_text[:30] + "…"
        else:
            sub_text = f"{profile.get('user', '?')}@{profile.get('host', '?')}"

        sub_lbl = ctk.CTkLabel(
            card, text=sub_text,
            font=micro_font(), anchor="w",
            wraplength=200,
        )
        sub_lbl.grid(row=1, column=1, sticky="w", padx=(PAD_SM, PAD_MD), pady=(0, PAD_MD))

        # ── Click handlers ──
        def _on_click(e=None):
            # Guard against non-left clicks being interpreted as connect
            if e is not None and getattr(e, "num", 1) != 1:
                return "break"
            self._selected_id = profile.get("id", "")
            self._rebuild()  # refresh to show selection
            self._on_connect(profile)
            return "break"

        def _on_right_click(e=None):
            # Select card, then open context menu only (no connect)
            self._selected_id = profile.get("id", "")
            self._rebuild()
            return ctx.show(e)

        def _on_enter(e=None):
            if profile.get("id") != self._selected_id:
                card.configure(fg_color=C("hover"))

        def _on_leave(e=None):
            if profile.get("id") != self._selected_id:
                card.configure(fg_color=C("card"))

        # Bind all child widgets too so clicks don't miss
        ctx = _CtxMenu(self, profile, self._on_connect, self._on_edit,
                       lambda p: self._delete(p), lambda p: self._duplicate(p))

        for widget in (card, content, name_frame, name_lbl, sub_lbl, badge, accent_bar):
            widget.bind("<Button-1>", _on_click)
            widget.bind("<Double-Button-1>", _on_click)
            widget.bind("<Enter>", _on_enter)
            widget.bind("<Leave>", _on_leave)
            widget.bind("<Button-3>", _on_right_click)
            widget.bind("<Button-2>", _on_right_click)  # fallback on some platforms
            if hasattr(widget, "configure") and widget != accent_bar:
                try:
                    widget.configure(cursor="hand2")
                except Exception:
                    pass

        # Store refs for theming
        card._accent_bar = accent_bar    # type: ignore[attr-defined]
        card._name_lbl = name_lbl        # type: ignore[attr-defined]
        card._sub_lbl = sub_lbl          # type: ignore[attr-defined]
        card._badge = badge              # type: ignore[attr-defined]
        card._profile_id = profile.get("id", "")  # type: ignore[attr-defined]
        card._is_selected = is_selected  # type: ignore[attr-defined]

        # Apply card theme
        self._theme_card(card)
        return card

    def _theme_card(self, card: ctk.CTkFrame) -> None:
        is_selected = getattr(card, "_is_selected", False)
        card.configure(
            fg_color=C("card2") if is_selected else C("card"),
        )
        card._accent_bar.configure(  # type: ignore[attr-defined]
            fg_color=C("accent2") if is_selected else "transparent",
        )
        card._name_lbl.configure(  # type: ignore[attr-defined]
            text_color=C("text2") if is_selected else C("text"),
            fg_color="transparent",
        )
        card._sub_lbl.configure(  # type: ignore[attr-defined]
            text_color=C("dim"),
            fg_color="transparent",
        )

    def _delete(self, profile: dict) -> None:
        d = _ConfirmDelete(self, profile["name"])
        if d.ok:
            delete_profile(profile["id"])
            if self._selected_id == profile.get("id"):
                self._selected_id = ""
            self.refresh()

    def _duplicate(self, profile: dict) -> None:
        duplicate_profile(profile["id"])
        self.refresh()

    # ── Theme ─────────────────────────────────────────────────────────────────

    def apply_theme(self) -> None:
        self.configure(fg_color=C("bg"))

        self._header.configure(fg_color=C("bg"))
        self._header_lbl.configure(text_color=C("dim"))

        self._add_btn.configure(
            fg_color=C("card2"), hover_color=C("accent"),
            text_color=C("accent"), border_color=C("border"), border_width=1,
        )
        self._status_btn.configure(
            fg_color=C("card2"), hover_color=C("accent"),
            text_color=C("accent"), border_color=C("border"), border_width=1,
        )

        self._search_wrap.configure(fg_color=C("bg"))
        self._search_entry.configure(
            fg_color=C("card"), border_color=C("border2"),
            text_color=C("text"), placeholder_text_color=C("dim"),
        )

        self._scroll.configure(fg_color=C("bg"))

        # Re-theme all cards
        for w in self._scroll.winfo_children():
            if isinstance(w, ctk.CTkFrame) and hasattr(w, "_profile_id"):
                w._is_selected = (w._profile_id == self._selected_id)  # type: ignore[attr-defined]
                self._theme_card(w)
            elif isinstance(w, ctk.CTkLabel):
                # Group labels
                w.configure(text_color=C("accent"), fg_color="transparent")


# ── Context menu ──────────────────────────────────────────────────────────────

class _CtxMenu:
    def __init__(self, parent, profile, on_connect, on_edit, on_delete, on_duplicate):
        self._p = profile
        self._parent = parent
        self._actions = (on_connect, on_edit, on_delete, on_duplicate)

    def show(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        on_connect, on_edit, on_delete, on_duplicate = self._actions
        m = tk.Menu(
            self._parent, tearoff=0,
            bg=C("card2"), fg=C("text"),
            activebackground=C("accent"), activeforeground="#ffffff",
            font=(_UI_FAMILY_FALLBACK, 13), bd=0, relief="flat",
            selectcolor=C("accent"),
        )
        m.add_command(label="  Connect",    command=lambda: on_connect(self._p))
        m.add_command(label="  Edit",       command=lambda: on_edit(self._p))
        m.add_command(label="  Duplicate",  command=lambda: on_duplicate(self._p))
        m.add_separator()
        m.add_command(label="  Delete", foreground=C("red"),
                      command=lambda: on_delete(self._p))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()
        return "break"


_UI_FAMILY_FALLBACK = "Inter"


# ── Confirm delete dialog ─────────────────────────────────────────────────────

class _ConfirmDelete(SafeGrabMixin, ctk.CTkToplevel):
    def __init__(self, parent: Any, name: str) -> None:
        super().__init__(parent)
        self.title("Delete Profile")
        self.configure(fg_color=C("card"))
        self.resizable(False, False)
        self.after(100, self._safe_grab)
        self.ok = False

        # Minimal, centered dialog
        ctk.CTkLabel(
            self, text="Delete profile?",
            font=header_font(), text_color=C("text2"),
        ).pack(padx=PAD_2XL, pady=(PAD_2XL, PAD_SM))

        ctk.CTkLabel(
            self, text=f'"{name}" will be permanently removed.',
            font=body_font(), text_color=C("dim"),
            wraplength=320, justify="center",
        ).pack(padx=PAD_2XL, pady=(0, PAD_XL))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=(0, PAD_2XL))

        ctk.CTkButton(
            row, text="Cancel", font=label_font(),
            width=100, height=38, corner_radius=RADIUS_SM,
            fg_color=C("card2"), hover_color=C("border"),
            text_color=C("text"), border_color=C("border"), border_width=1,
            command=self.destroy,
        ).pack(side="left", padx=PAD_SM)

        ctk.CTkButton(
            row, text="Delete", font=label_bold(),
            width=100, height=38, corner_radius=RADIUS_SM,
            fg_color=C("red"), hover_color="#a01010", text_color="#ffffff",
            command=self._confirm,
        ).pack(side="left", padx=PAD_SM)

        self.wait_window()

    def _confirm(self) -> None:
        self.ok = True
        self.destroy()
