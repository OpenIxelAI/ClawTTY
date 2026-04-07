#!/usr/bin/env python3
"""
ClawTTY v3 — AI agent SSH launcher (PuTTY-style)
Entry point. Keep this file thin.
"""
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_PYTHON_DIR = os.path.join(_HERE, "python")
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)


def main() -> None:
    # CLI subcommand check — if handled, skip GUI
    from backend.cli import main as cli_main
    if cli_main():
        return

    try:
        import customtkinter as ctk
    except ImportError:
        print(
            "[ClawTTY] ERROR: 'customtkinter' not installed.\n"
            "Run: pip install --user customtkinter>=5.2.0",
            file=sys.stderr,
        )
        sys.exit(1)

    from backend.platform_info import use_keyring_backend
    if use_keyring_backend():
        try:
            import keyring  # noqa: F401
        except ImportError:
            print(
                "[ClawTTY] WARNING: 'keyring' not installed — credential storage unavailable.\n"
                "Run: pip install --user keyring>=24.0.0",
                file=sys.stderr,
            )
    else:
        try:
            import secretstorage  # noqa: F401
        except ImportError:
            print(
                "[ClawTTY] WARNING: 'secretstorage' not installed — passphrase storage unavailable.\n"
                "Run: pip install --user secretstorage>=3.3.0",
                file=sys.stderr,
            )

    # Load saved prefs (scale, theme) BEFORE creating the window
    from backend import settings as cfg
    prefs = cfg.load()

    # Apply theme mode before any widgets
    ctk.set_appearance_mode("dark" if prefs["theme"] == "dark" else "light")

    # Apply scaling — env var overrides saved pref
    scale = float(os.environ.get("CLAWTTY_SCALE", prefs.get("ui_scale", 1.75)))
    scale = max(0.5, min(3.0, scale))
    ctk.set_widget_scaling(scale)
    ctk.set_window_scaling(scale)
    print(f"[ClawTTY] scale={scale}x  theme={prefs['theme']}")

    try:
        from backend.app import ClawTTYApp
    except ImportError as exc:
        print(f"[ClawTTY] ERROR: Failed to import app: {exc}", file=sys.stderr)
        sys.exit(1)

    app = ClawTTYApp(initial_scale=scale)
    app.mainloop()


if __name__ == "__main__":
    main()
