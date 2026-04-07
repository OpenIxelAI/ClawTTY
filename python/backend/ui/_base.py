"""
_base.py — Shared mixin for all CTkToplevel dialogs.

Provides _safe_grab() which defers grab_set() until the window is
actually visible — required on Wayland/KDE where windows aren't
immediately mapped.
"""
from __future__ import annotations


class SafeGrabMixin:
    """Mix into any ctk.CTkToplevel subclass that calls self.after(100, self._safe_grab)."""

    def _safe_grab(self) -> None:
        try:
            if self.winfo_exists() and self.winfo_viewable():  # type: ignore[attr-defined]
                self.grab_set()  # type: ignore[attr-defined]
            else:
                # Not visible yet — try again shortly
                self.after(100, self._safe_grab)  # type: ignore[attr-defined]
        except Exception:
            pass  # Never crash the app over a grab failure
