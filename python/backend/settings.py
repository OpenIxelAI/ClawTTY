"""
settings.py — Persistent user preferences for ClawTTY v3.

Stored at: ~/.config/clawtty/settings.json
Separate from profiles.json intentionally.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

_SETTINGS_DIR  = Path.home() / ".config" / "clawtty"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"

_DEFAULTS: dict[str, Any] = {
    "ui_scale":   1.75,   # widget scaling factor
    "theme":      "dark", # "dark" | "light"
    "window_w":   1400,
    "window_h":   900,
}


def load() -> dict[str, Any]:
    if not _SETTINGS_FILE.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        merged = dict(_DEFAULTS)
        merged.update({k: v for k, v in data.items() if k in _DEFAULTS})
        # Clamp scale
        merged["ui_scale"] = max(0.5, min(3.0, float(merged["ui_scale"])))
        return merged
    except Exception:
        return dict(_DEFAULTS)


def save(settings: dict[str, Any]) -> None:
    _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(_SETTINGS_DIR, stat.S_IRWXU)
    tmp = _SETTINGS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    tmp.replace(_SETTINGS_FILE)


def get(key: str) -> Any:
    return load().get(key, _DEFAULTS.get(key))


def set_value(key: str, value: Any) -> None:
    s = load()
    s[key] = value
    save(s)
