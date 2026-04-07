"""
status_cache.py — persistent last-seen cache for dashboard checks.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

_CFG_DIR = Path.home() / ".config" / "clawtty"
_CACHE = _CFG_DIR / "status_cache.json"


def _ensure_dir() -> None:
    _CFG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(_CFG_DIR, stat.S_IRWXU)


def load_status_cache() -> dict[str, Any]:
    if not _CACHE.exists():
        return {}
    try:
        data = json.loads(_CACHE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_status_cache(data: dict[str, Any]) -> None:
    _ensure_dir()
    tmp = _CACHE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    tmp.replace(_CACHE)

