"""
ssh.py — SSH command builder and host key verification for ClawTTY v3.

Security design:
  - Remote commands are validated per profile agent (OpenClaw/Hermes presets or custom guards).
  - Host keys tracked in ~/.local/share/clawtty/known_hosts (separate from ~/.ssh/known_hosts).
  - First connect: fingerprint shown to user; they must confirm before proceeding.
  - Any mismatch between stored and observed key: CONNECTION BLOCKED, loud warning.
  - Fail-closed: any validation failure raises SSHSecurityError.
  - No shell=True, no string interpolation of user values into shell arguments.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import socket
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .platform_info import is_windows
from .config import (
    AGENTS,
    AGENT_CUSTOM,
    AGENT_OPENCLAW,
    DEFAULT_AGENT,
    HERMES_PRESETS,
    OPENCLAW_PRESETS,
    is_remote_command_valid,
)
from . import audit

# ── Optional paramiko import ──────────────────────────────────────────────────
try:
    import paramiko  # type: ignore

    _PARAMIKO_AVAILABLE = True
except ImportError:
    _PARAMIKO_AVAILABLE = False

_KNOWN_HOSTS_DIR = Path.home() / ".local" / "share" / "clawtty"
_KNOWN_HOSTS_FILE = _KNOWN_HOSTS_DIR / "known_hosts"


class SSHSecurityError(RuntimeError):
    """Raised when a security check fails. Connection must not proceed."""


class SSHValidationError(ValueError):
    """Raised when profile fields are missing or invalid."""


# ── Known-hosts management ────────────────────────────────────────────────────

def _ensure_known_hosts_file() -> Path:
    _KNOWN_HOSTS_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(_KNOWN_HOSTS_DIR, stat.S_IRWXU)
    if not _KNOWN_HOSTS_FILE.exists():
        _KNOWN_HOSTS_FILE.touch(mode=0o600)
    else:
        os.chmod(_KNOWN_HOSTS_FILE, stat.S_IRUSR | stat.S_IWUSR)
    return _KNOWN_HOSTS_FILE


def _load_known_hosts() -> dict[str, str]:
    """
    Return dict mapping "host:port" → fingerprint string.
    Format per line: host:port <fingerprint>
    """
    _ensure_known_hosts_file()
    result: dict[str, str] = {}
    try:
        for line in _KNOWN_HOSTS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                result[parts[0]] = parts[1]
    except OSError:
        pass
    return result


def _save_known_host(host_key: str, fingerprint: str) -> None:
    """Append a new trusted host entry."""
    _ensure_known_hosts_file()
    with _KNOWN_HOSTS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"{host_key} {fingerprint}\n")


def _host_key(host: str, port: int) -> str:
    return f"{host}:{port}"


# ── Fingerprint fetching via paramiko ─────────────────────────────────────────

@dataclass
class HostKeyInfo:
    host: str
    port: int
    key_type: str
    fingerprint_md5: str
    fingerprint_sha256: str
    raw_b64: str = ""


def fetch_host_key(host: str, port: int = 22, timeout: float = 10.0) -> HostKeyInfo:
    """
    Connect to the SSH port and retrieve the host key fingerprint.
    Does NOT authenticate; closes immediately after key exchange.

    Raises:
        SSHSecurityError: if paramiko is unavailable or connection fails.
    """
    if not _PARAMIKO_AVAILABLE:
        raise SSHSecurityError(
            "paramiko is not installed. Host key verification unavailable.\n"
            "Run: pip install paramiko>=3.4.0"
        )

    transport: paramiko.Transport | None = None
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        transport = paramiko.Transport(sock)
        transport.start_client(timeout=timeout)
        key = transport.get_remote_server_key()
        if key is None:
            raise SSHSecurityError("Remote server returned no host key")

        import base64
        raw_bytes = key.asbytes()
        raw_b64 = base64.b64encode(raw_bytes).decode()

        md5_hex = hashlib.md5(raw_bytes).hexdigest()
        md5_fmt = ":".join(md5_hex[i:i+2] for i in range(0, len(md5_hex), 2))

        sha256_b64 = hashlib.sha256(raw_bytes).digest()
        import base64 as _b64
        sha256_fmt = "SHA256:" + _b64.b64encode(sha256_b64).decode().rstrip("=")

        return HostKeyInfo(
            host=host,
            port=port,
            key_type=key.get_name(),
            fingerprint_md5=md5_fmt,
            fingerprint_sha256=sha256_fmt,
            raw_b64=raw_b64,
        )

    except SSHSecurityError:
        raise
    except paramiko.SSHException as exc:
        raise SSHSecurityError(f"SSH key exchange failed: {exc}") from exc
    except (socket.timeout, ConnectionRefusedError, OSError) as exc:
        raise SSHSecurityError(f"Cannot reach host {host}:{port} — {exc}") from exc
    finally:
        if transport is not None:
            try:
                transport.close()
            except Exception:
                pass


# ── Host key verification flow ────────────────────────────────────────────────

@dataclass
class VerificationResult:
    """Result of verify_host_key()."""
    status: str          # "trusted" | "unknown" | "mismatch" | "error"
    fingerprint: str     # SHA256 fingerprint string
    key_type: str        # e.g. "ssh-ed25519"
    message: str         # Human-readable explanation
    host_key_info: HostKeyInfo | None = None


def verify_host_key(
    profile_name: str,
    host: str,
    port: int = 22,
) -> VerificationResult:
    """
    Verify the remote host's key against our known_hosts store.

    Returns a VerificationResult; caller must check .status:
      "trusted"  — key matches stored record; proceed.
      "unknown"  — first time seeing this host; must prompt user.
      "mismatch" — key CHANGED; must BLOCK and warn.
      "error"    — could not fetch key; must BLOCK.
    """
    try:
        info = fetch_host_key(host, port)
    except SSHSecurityError as exc:
        audit.log_blocked(profile_name, host, "", str(exc))
        return VerificationResult(
            status="error",
            fingerprint="",
            key_type="",
            message=str(exc),
        )

    hk = _host_key(host, port)
    known = _load_known_hosts()

    if hk not in known:
        return VerificationResult(
            status="unknown",
            fingerprint=info.fingerprint_sha256,
            key_type=info.key_type,
            message=(
                f"First connection to {host}:{port}\n"
                f"Key type: {info.key_type}\n"
                f"Fingerprint: {info.fingerprint_sha256}\n\n"
                "Do you trust this host?"
            ),
            host_key_info=info,
        )

    stored = known[hk]
    if stored == info.fingerprint_sha256:
        return VerificationResult(
            status="trusted",
            fingerprint=info.fingerprint_sha256,
            key_type=info.key_type,
            message="Host key verified.",
            host_key_info=info,
        )

    # KEY MISMATCH — potential MITM attack
    audit.log_host_key_mismatch(profile_name, host, stored, info.fingerprint_sha256)
    return VerificationResult(
        status="mismatch",
        fingerprint=info.fingerprint_sha256,
        key_type=info.key_type,
        message=(
            f"⚠️  HOST KEY MISMATCH for {host}:{port}\n\n"
            f"Expected: {stored}\n"
            f"Got:      {info.fingerprint_sha256}\n\n"
            "This could indicate a MITM attack or server key rotation.\n"
            "CONNECTION BLOCKED. Contact your administrator."
        ),
        host_key_info=info,
    )


def trust_host_key(profile_name: str, host: str, port: int, fingerprint: str, accepted: bool) -> None:
    """Record user's trust decision. If accepted, persist to known_hosts."""
    audit.log_host_key_confirm(profile_name, host, fingerprint, accepted)
    if accepted:
        _save_known_host(_host_key(host, port), fingerprint)


# ── SSH command builder ───────────────────────────────────────────────────────

@dataclass
class SSHCommand:
    """A validated, ready-to-exec SSH command."""
    argv: list[str]            # Full argument list (no shell expansion needed)
    display_cmd: str           # Human-readable form for UI display
    profile_name: str
    host: str
    command: str


def build_ssh_command(profile: dict[str, Any]) -> SSHCommand:
    """
    Build an SSH argv list from a profile dict.

    Validates:
      - host is set
      - user is set
      - agent + remote_command match policy (presets or custom guards)
      - port is valid

    Raises:
        SSHValidationError: on any validation failure.
        SSHSecurityError:   if remote_command is rejected for the profile agent.
    """
    host = (profile.get("host") or "").strip()
    user = (profile.get("user") or "").strip()
    port = profile.get("port", 22)
    identity_file = (profile.get("identity_file") or "").strip()
    remote_command = (profile.get("remote_command") or "").strip()
    agent = (profile.get("agent") or DEFAULT_AGENT).strip()
    profile_name = profile.get("name", "<unknown>")

    # ── Validation ────────────────────────────────────────────────────────────
    if not host:
        raise SSHValidationError("Host is required")

    if not user:
        raise SSHValidationError("User is required")

    try:
        port = int(port)
    except (TypeError, ValueError):
        raise SSHValidationError(f"Invalid port: {port!r}")

    if not (1 <= port <= 65535):
        raise SSHValidationError(f"Port out of range: {port}")

    # ── Remote command check (security-critical) ──────────────────────────────
    if agent not in AGENTS:
        reason = f"Invalid agent {agent!r}"
        audit.log_blocked(profile_name, host, remote_command, reason)
        raise SSHSecurityError(reason)

    if not is_remote_command_valid(agent, remote_command):
        if agent == AGENT_CUSTOM:
            reason = (
                f"Custom command rejected (empty, too long, or disallowed characters). "
                f"See profile settings."
            )
        else:
            allowed = OPENCLAW_PRESETS if agent == AGENT_OPENCLAW else HERMES_PRESETS
            reason = (
                f"Command {remote_command!r} is not valid for agent {agent!r}. "
                f"Allowed: {list(allowed)}"
            )
        audit.log_blocked(profile_name, host, remote_command, reason)
        raise SSHSecurityError(reason)

    # ── Identity file check ───────────────────────────────────────────────────
    identity_args: list[str] = []
    if identity_file:
        id_path = Path(identity_file).expanduser().resolve()
        if not id_path.exists():
            raise SSHValidationError(f"Identity file not found: {id_path}")
        # Check permissions
        mode = oct(stat.S_IMODE(id_path.stat().st_mode))
        if id_path.stat().st_mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH):
            raise SSHValidationError(
                f"Identity file {id_path} has insecure permissions ({mode}). "
                "Run: chmod 600 <keyfile>"
            )
        identity_args = ["-i", str(id_path)]

    ssh = shutil.which("ssh")
    if not ssh:
        raise SSHValidationError("'ssh' not found on PATH")

    argv = [
        ssh,
        "-t",                              # Force PTY — required for interactive TUI
        "-p", str(port),
        *identity_args,
        "-o", "StrictHostKeyChecking=no",  # We do our own verification
        "-o", "UserKnownHostsFile=/dev/null",  # Don't touch ~/.ssh/known_hosts
        "-o", "BatchMode=no",
        f"{user}@{host}",
        remote_command,
    ]

    import shlex as _shlex
    display_cmd = (
        f"ssh -p {port} "
        + (f"-i {_shlex.quote(identity_file)} " if identity_file else "")
        + f"{user}@{host} {_shlex.quote(remote_command) if remote_command else ''}"
    ).strip()

    return SSHCommand(
        argv=argv,
        display_cmd=display_cmd,
        profile_name=profile_name,
        host=host,
        command=remote_command,
    )


def get_terminal_emulator() -> str | None:
    """
    Return the path to the best available terminal emulator.
    Priority: konsole → gnome-terminal → kitty → alacritty → xterm
    """
    if is_windows():
        for term in ("wt.exe", "cmd.exe"):
            path = shutil.which(term)
            if path:
                return path
        return None
    for term in ("konsole", "gnome-terminal", "kitty", "alacritty", "xterm"):
        path = shutil.which(term)
        if path:
            return path
    return None


def build_terminal_argv(terminal: str, ssh_cmd: SSHCommand) -> list[str]:
    """
    Wrap the SSH argv in a terminal emulator invocation.
    Returns the full argv list for subprocess.
    """
    name = Path(terminal).name

    if name.lower() in ("wt.exe", "wt"):
        return [terminal, "new-tab", "--", *ssh_cmd.argv]
    if name.lower() in ("cmd.exe", "cmd"):
        return [terminal, "/k", " ".join(ssh_cmd.argv)]
    if name == "konsole":
        return [terminal, "-e", *ssh_cmd.argv]
    elif name == "gnome-terminal":
        return [terminal, "--", *ssh_cmd.argv]
    elif name in ("kitty", "alacritty"):
        return [terminal, "--", *ssh_cmd.argv]
    else:
        # xterm and generic fallback
        return [terminal, "-e", " ".join(ssh_cmd.argv)]


def validate_profile(profile: dict[str, Any]) -> list[str]:
    """
    Return a list of validation error strings (empty = valid).
    Does NOT raise; suitable for form validation.
    """
    errors: list[str] = []

    host = (profile.get("host") or "").strip()
    user = (profile.get("user") or "").strip()
    port = profile.get("port", 22)
    remote_command = (profile.get("remote_command") or "").strip()
    agent = (profile.get("agent") or DEFAULT_AGENT).strip()

    if not host:
        errors.append("Host is required")
    if not user:
        errors.append("User is required")

    try:
        p = int(port)
        if not (1 <= p <= 65535):
            errors.append(f"Port must be 1–65535 (got {p})")
    except (TypeError, ValueError):
        errors.append(f"Port must be a number (got {port!r})")

    if agent not in AGENTS:
        errors.append(f"Agent must be one of: {', '.join(AGENTS)}")
    elif not is_remote_command_valid(agent, remote_command):
        if agent == AGENT_CUSTOM:
            errors.append("Custom command is invalid (empty, too long, or disallowed characters)")
        else:
            allowed = OPENCLAW_PRESETS if agent == AGENT_OPENCLAW else HERMES_PRESETS
            errors.append(f"Command must be one of: {', '.join(allowed)}")

    identity_file = (profile.get("identity_file") or "").strip()
    if identity_file:
        id_path = Path(identity_file).expanduser()
        if not id_path.exists():
            errors.append(f"Identity file not found: {id_path}")

    return errors
