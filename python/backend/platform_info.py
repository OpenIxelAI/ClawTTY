"""
platform_info.py — runtime OS/platform helpers.
"""
from __future__ import annotations

import os
import platform


def is_windows() -> bool:
    return platform.system().lower() == "windows"


def is_wsl2() -> bool:
    if is_windows():
        return False
    rel = platform.release().lower()
    if "microsoft" in rel or "wsl" in rel:
        return True
    try:
        return "microsoft" in os.uname().release.lower()
    except Exception:
        return False


def is_macos() -> bool:
    return platform.system().lower() == "darwin"


def platform_label() -> str:
    if is_windows():
        return "windows"
    if is_wsl2():
        return "wsl2"
    if is_macos():
        return "macos"
    return "linux"


def use_keyring_backend() -> bool:
    return is_windows() or is_wsl2()

