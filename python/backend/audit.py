"""
audit.py — Append-only local audit log for every connection attempt.

Format:
  [ISO timestamp] ACTION profile="X" host="Y" command="Z" result="OK|BLOCKED|FAILED" reason="..."

Security design:
  - Append-only (never truncated by this module)
  - Written to ~/.local/share/clawtty/audit.log
  - Permissions 0o600 enforced on creation
  - No network calls, ever
"""

from __future__ import annotations

import os
import stat
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOG_DIR = Path.home() / ".local" / "share" / "clawtty"
_LOG_FILE = _LOG_DIR / "audit.log"
_lock = threading.Lock()


def _ensure_log_file() -> Path:
    """Create the log directory and file with secure permissions if needed."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    # Secure the directory: owner rwx only
    os.chmod(_LOG_DIR, stat.S_IRWXU)

    if not _LOG_FILE.exists():
        _LOG_FILE.touch(mode=0o600)
    else:
        # Enforce permissions even on existing file
        os.chmod(_LOG_FILE, stat.S_IRUSR | stat.S_IWUSR)

    return _LOG_FILE


def _quote(value: str) -> str:
    """Escape double-quotes so values stay parseable."""
    return value.replace('"', '\\"')


def log(
    action: str,
    profile: str,
    host: str,
    command: str,
    result: str,
    reason: str = "",
) -> None:
    """
    Write one audit entry. Thread-safe.

    Args:
        action:  Verb describing the event, e.g. "CONNECT", "BLOCKED", "KEYGEN".
        profile: Profile name (or "<none>").
        host:    Target hostname or IP.
        command: Remote command string (preset or custom attempt).
        result:  "OK" | "BLOCKED" | "FAILED".
        reason:  Human-readable explanation (empty string is fine for OK).
    """
    ts = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    entry = (
        f'[{ts}] {action} '
        f'profile="{_quote(profile)}" '
        f'host="{_quote(host)}" '
        f'command="{_quote(command)}" '
        f'result="{result}" '
        f'reason="{_quote(reason)}"\n'
    )

    with _lock:
        log_file = _ensure_log_file()
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(entry)


def log_connect(profile: str, host: str, command: str) -> None:
    """Shortcut: log a successful connection launch."""
    log("CONNECT", profile, host, command, "OK")


def log_blocked(profile: str, host: str, command: str, reason: str) -> None:
    """Shortcut: log a blocked connection attempt."""
    log("BLOCKED", profile, host, command, "BLOCKED", reason)


def log_failed(profile: str, host: str, command: str, reason: str) -> None:
    """Shortcut: log a connection that failed after starting."""
    log("FAILED", profile, host, command, "FAILED", reason)


def log_keygen(profile: str, host: str, result: str, reason: str = "") -> None:
    """Log a key generation or copy-id event."""
    log("KEYGEN", profile, host, "ssh-keygen", result, reason)


def log_host_key_confirm(profile: str, host: str, fingerprint: str, accepted: bool) -> None:
    """Log user's decision about an unknown host key."""
    result = "OK" if accepted else "BLOCKED"
    reason = f"fingerprint={fingerprint}"
    log("HOSTKEY_CONFIRM", profile, host, "", result, reason)


def log_host_key_mismatch(profile: str, host: str, expected: str, got: str) -> None:
    """Log a host key mismatch — always BLOCKED."""
    reason = f"expected={expected} got={got}"
    log("HOSTKEY_MISMATCH", profile, host, "", "BLOCKED", reason)


def get_log_path() -> Path:
    """Return the audit log path (for display in the UI)."""
    return _LOG_FILE


def read_recent(n: int = 100) -> list[str]:
    """
    Return the last *n* lines of the audit log (newest last).
    Uses a reverse-read to avoid loading the entire file into memory
    (the log is append-only and grows unbounded).
    """
    try:
        _ensure_log_file()
        if not _LOG_FILE.exists():
            return []
        # Efficient tail: read in chunks from end of file
        chunk_size = 8192
        lines: list[str] = []
        with _LOG_FILE.open("rb") as f:
            f.seek(0, 2)  # seek to end
            remaining = f.tell()
            buf = b""
            while remaining > 0 and len(lines) < n + 1:
                read_size = min(chunk_size, remaining)
                remaining -= read_size
                f.seek(remaining)
                buf = f.read(read_size) + buf
                lines = buf.decode("utf-8", errors="replace").splitlines()
        return lines[-n:]
    except OSError:
        return []
