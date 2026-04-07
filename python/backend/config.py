"""
config.py — Profile management for ClawTTY v3.

Storage: ~/.config/clawtty/profiles.json
Schema per profile (SSH):
  {
    "id":             str  (UUID4, generated on creation),
    "name":           str,
    "group":          str  (folder/group label),
    "connection_type": str ("ssh" [default] | "websocket"),
    "host":           str,
    "user":           str,
    "port":           int  (default 22),
    "identity_file":  str  (path, may be ""),
    "agent":          str  ("openclaw" | "hermes" | "custom"),
    "remote_command": str  (preset for agent, or custom string if agent is custom),
    "notes":          str
  }

Schema per profile (WebSocket):
  {
    "id":              str  (UUID4),
    "name":            str,
    "group":           str,
    "connection_type": "websocket",
    "ws_url":          str  (ws:// or wss://),
    "notes":           str
    -- WS token stored in system keychain by profile id, NEVER here --
  }

Security: NO passwords, NO passphrases, NO secrets of any kind.
Tokens for WebSocket profiles are stored exclusively in the system keychain.
"""

from __future__ import annotations

import json
import os
import re
import stat
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, FrozenSet

# ── Agent presets (SSH remote command strings) ───────────────────────────────
OPENCLAW_PRESETS: tuple[str, ...] = (
    "openclaw tui",
    "openclaw status",
    "openclaw sessions",
    "openclaw logs",
)
HERMES_PRESETS: tuple[str, ...] = (
    "hermes",
    "hermes status",
    "hermes sessions",
    "hermes logs",
)

AGENT_OPENCLAW = "openclaw"
AGENT_HERMES = "hermes"
AGENT_CUSTOM = "custom"

AGENTS: tuple[str, ...] = (AGENT_OPENCLAW, AGENT_HERMES, AGENT_CUSTOM)

AGENT_PRESETS: dict[str, tuple[str, ...]] = {
    AGENT_OPENCLAW: OPENCLAW_PRESETS,
    AGENT_HERMES: HERMES_PRESETS,
}

DEFAULT_AGENT = AGENT_OPENCLAW
DEFAULT_COMMAND = OPENCLAW_PRESETS[0]

# Backward compatibility: old code imported ALLOWED_COMMANDS as all preset strings
ALLOWED_COMMANDS: tuple[str, ...] = tuple(
    dict.fromkeys(OPENCLAW_PRESETS + HERMES_PRESETS)
)

CUSTOM_REMOTE_MAX_LEN = 1024

# Reject shell metacharacters / substitution; single-line remote argv string only
_CUSTOM_INVALID = re.compile(r"[\n\r\t;|&$`]|\$\(|\$\{")


def commands_for_agent(agent: str) -> FrozenSet[str]:
    """Preset commands for openclaw/hermes; empty for custom."""
    if agent == AGENT_CUSTOM:
        return frozenset()
    presets = AGENT_PRESETS.get(agent)
    return frozenset(presets) if presets else frozenset()


def all_preset_commands() -> FrozenSet[str]:
    """Union of all built-in preset remote commands (for macros)."""
    return frozenset(OPENCLAW_PRESETS) | frozenset(HERMES_PRESETS)


def default_command_for_agent(agent: str) -> str:
    if agent == AGENT_HERMES:
        return HERMES_PRESETS[0]
    if agent == AGENT_CUSTOM:
        return ""
    return OPENCLAW_PRESETS[0]


def validate_custom_remote_command(cmd: str) -> bool:
    """True if custom agent remote_command passes lightweight guards."""
    s = cmd.strip()
    if not s or len(s) > CUSTOM_REMOTE_MAX_LEN:
        return False
    if _CUSTOM_INVALID.search(s):
        return False
    return True


def is_remote_command_valid(agent: str, remote_command: str) -> bool:
    cmd = (remote_command or "").strip()
    if agent == AGENT_CUSTOM:
        return validate_custom_remote_command(cmd)
    allowed = commands_for_agent(agent)
    return cmd in allowed


def preset_broadcast_applies(profile: dict[str, Any], command: str) -> bool:
    """True if preset macro command is valid for this SSH profile."""
    if profile.get("connection_type") != "ssh":
        return False
    agent = profile.get("agent", DEFAULT_AGENT)
    if agent == AGENT_CUSTOM:
        return False
    cmd = (command or "").strip()
    return cmd in commands_for_agent(agent)


def status_preset_command_for_profile(profile: dict[str, Any]) -> str | None:
    """Preset 'status' remote command for Broadcast All, or None if N/A."""
    if profile.get("connection_type") != "ssh":
        return None
    agent = profile.get("agent", DEFAULT_AGENT)
    if agent == AGENT_OPENCLAW:
        return "openclaw status"
    if agent == AGENT_HERMES:
        return "hermes status"
    return None


# ── Paths ─────────────────────────────────────────────────────────────────────
_CONFIG_DIR = Path.home() / ".config" / "clawtty"
_PROFILES_FILE = _CONFIG_DIR / "profiles.json"

# ── Schema defaults ───────────────────────────────────────────────────────────
_PROFILE_DEFAULTS: dict[str, Any] = {
    "id":              "",
    "name":            "Unnamed Profile",
    "group":           "Default",
    "connection_type": "ssh",       # "ssh" | "websocket"
    # SSH fields
    "host":            "",
    "user":            "",
    "port":            22,
    "identity_file":   "",
    "agent":           DEFAULT_AGENT,
    "remote_command":  DEFAULT_COMMAND,
    # WebSocket fields
    "ws_url":          "",
    # Shared
    "notes":           "",
}

_FORBIDDEN_KEYS = {"password", "passphrase", "secret", "key_data", "private_key", "ws_token", "token"}


def _infer_agent_from_command(remote_command: str) -> str:
    rc = (remote_command or "").strip()
    if rc in OPENCLAW_PRESETS:
        return AGENT_OPENCLAW
    if rc in HERMES_PRESETS:
        return AGENT_HERMES
    return AGENT_CUSTOM


def _coerce_ssh_command(agent: str, remote_command: str) -> tuple[str, str]:
    """Enforce valid remote_command; may reset agent if custom command is invalid."""
    rc = (remote_command or "").strip()
    if agent == AGENT_CUSTOM:
        if validate_custom_remote_command(rc):
            return agent, rc
        return DEFAULT_AGENT, DEFAULT_COMMAND
    allowed = AGENT_PRESETS.get(agent, OPENCLAW_PRESETS)
    if rc in allowed:
        return agent, rc
    return agent, allowed[0]


def _sanitize(profile: dict[str, Any]) -> dict[str, Any]:
    """Remove any forbidden keys and enforce schema types."""
    had_agent_key = "agent" in profile

    clean: dict[str, Any] = deepcopy(_PROFILE_DEFAULTS)
    for key, default in _PROFILE_DEFAULTS.items():
        if key in profile:
            value = profile[key]
            # Type coercion
            if isinstance(default, int):
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    value = default
            elif isinstance(default, str):
                value = str(value) if value is not None else default
            clean[key] = value

    # Hard strip any secret fields that snuck in
    for bad_key in _FORBIDDEN_KEYS:
        clean.pop(bad_key, None)

    # Normalise connection_type
    if clean["connection_type"] not in ("ssh", "websocket"):
        clean["connection_type"] = "ssh"

    # SSH-only validation
    if clean["connection_type"] == "ssh":
        port = int(clean["port"])
        clean["port"] = max(1, min(65535, port))

        agent = clean.get("agent", DEFAULT_AGENT)
        if agent not in AGENTS:
            agent = DEFAULT_AGENT

        # Migrate legacy profiles with no agent field
        if not had_agent_key:
            agent = _infer_agent_from_command(clean["remote_command"])

        clean["agent"], clean["remote_command"] = _coerce_ssh_command(agent, clean["remote_command"])

    # WebSocket-only: ensure ws_url starts with ws:// or wss://
    if clean["connection_type"] == "websocket":
        ws_url = clean.get("ws_url", "")
        if ws_url and not (ws_url.startswith("ws://") or ws_url.startswith("wss://")):
            clean["ws_url"] = ""  # reject malformed URL

    return clean


def _ensure_config_dir() -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(_CONFIG_DIR, stat.S_IRWXU)  # 0o700


def _load_raw() -> list[dict[str, Any]]:
    if not _PROFILES_FILE.exists():
        return []
    try:
        data = json.loads(_PROFILES_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return data
    except (json.JSONDecodeError, OSError):
        return []


def _save_raw(profiles: list[dict[str, Any]]) -> None:
    _ensure_config_dir()
    # Write to temp file first, then atomic rename
    tmp = _PROFILES_FILE.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    tmp.replace(_PROFILES_FILE)


# ── Public API ────────────────────────────────────────────────────────────────

def load_profiles() -> list[dict[str, Any]]:
    """Load and sanitize all profiles from disk."""
    raw = _load_raw()
    return [_sanitize(p) for p in raw]


def save_profiles(profiles: list[dict[str, Any]]) -> None:
    """Sanitize and save profile list to disk."""
    clean = [_sanitize(p) for p in profiles]
    _save_raw(clean)


def new_profile(**kwargs: Any) -> dict[str, Any]:
    """Create a new profile dict with a fresh UUID, applying any kwargs."""
    profile = deepcopy(_PROFILE_DEFAULTS)
    profile["id"] = str(uuid.uuid4())
    profile.update(kwargs)
    return _sanitize(profile)


def new_ws_profile(**kwargs: Any) -> dict[str, Any]:
    """Create a new WebSocket profile dict with a fresh UUID."""
    profile = deepcopy(_PROFILE_DEFAULTS)
    profile["id"]              = str(uuid.uuid4())
    profile["connection_type"] = "websocket"
    profile["group"]           = "WebSocket"
    profile.update(kwargs)
    return _sanitize(profile)


def get_profile_by_id(profile_id: str) -> dict[str, Any] | None:
    for p in load_profiles():
        if p["id"] == profile_id:
            return p
    return None


def add_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Add a profile, generating an ID if missing. Returns the saved profile."""
    if not profile.get("id"):
        profile["id"] = str(uuid.uuid4())
    profile = _sanitize(profile)
    profiles = load_profiles()
    # Prevent duplicate IDs
    profiles = [p for p in profiles if p["id"] != profile["id"]]
    profiles.append(profile)
    save_profiles(profiles)
    return profile


def update_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Update an existing profile by ID. Raises KeyError if not found."""
    profile = _sanitize(profile)
    profiles = load_profiles()
    for i, p in enumerate(profiles):
        if p["id"] == profile["id"]:
            profiles[i] = profile
            save_profiles(profiles)
            return profile
    raise KeyError(f"Profile ID not found: {profile['id']}")


def delete_profile(profile_id: str) -> bool:
    """Delete profile by ID. Returns True if deleted."""
    profiles = load_profiles()
    new_list = [p for p in profiles if p["id"] != profile_id]
    if len(new_list) == len(profiles):
        return False
    save_profiles(new_list)
    return True


def duplicate_profile(profile_id: str) -> dict[str, Any] | None:
    """Duplicate a profile with a new ID and '(copy)' suffix."""
    orig = get_profile_by_id(profile_id)
    if orig is None:
        return None
    copy = deepcopy(orig)
    copy["id"] = str(uuid.uuid4())
    copy["name"] = orig["name"] + " (copy)"
    return add_profile(copy)


def get_groups() -> list[str]:
    """Return sorted list of distinct group names."""
    profiles = load_profiles()
    groups = sorted({p["group"] for p in profiles if p["group"]})
    return groups or ["Default"]


def get_profiles_by_group() -> dict[str, list[dict[str, Any]]]:
    """Return profiles keyed by group, sorted."""
    result: dict[str, list[dict[str, Any]]] = {}
    for p in load_profiles():
        g = p["group"] or "Default"
        result.setdefault(g, []).append(p)
    return dict(sorted(result.items()))


# ── SSH config importer ───────────────────────────────────────────────────────

def import_from_ssh_config(ssh_config_path: Path | None = None) -> list[dict[str, Any]]:
    """
    Parse ~/.ssh/config and return a list of profile dicts (not yet saved).
    Skips wildcard hosts. Ignores any password/secret fields.
    """
    path = ssh_config_path or (Path.home() / ".ssh" / "config")
    if not path.exists():
        return []

    imported: list[dict[str, Any]] = []
    current: dict[str, Any] = {}

    _keyword_map = {
        "hostname":     "host",
        "user":         "user",
        "port":         "port",
        "identityfile": "identity_file",
    }

    def _flush(block: dict[str, Any]) -> None:
        if not block.get("_host") or block["_host"] == "*":
            return
        profile = new_profile(
            name=block["_host"],
            host=block.get("host", block["_host"]),
            user=block.get("user", ""),
            port=int(block.get("port", 22)),
            identity_file=block.get("identity_file", ""),
            remote_command=DEFAULT_COMMAND,
            agent=DEFAULT_AGENT,
            group="Imported",
        )
        imported.append(profile)

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Split on first whitespace
        parts = re.split(r"\s+", line, maxsplit=1)
        if len(parts) < 2:
            continue
        keyword, value = parts[0].lower(), parts[1].strip()

        if keyword == "host":
            if current:
                _flush(current)
            current = {"_host": value}
        elif keyword in _keyword_map and current:
            mapped = _keyword_map[keyword]
            # Strip leading ~ for identity files
            if mapped == "identity_file":
                value = str(Path(value).expanduser())
            current[mapped] = value

    if current:
        _flush(current)

    return imported


def import_and_save_from_ssh_config() -> tuple[int, int]:
    """
    Import from ~/.ssh/config, skip profiles with duplicate hosts.
    Returns (imported_count, skipped_count).
    """
    new_profiles = import_from_ssh_config()
    existing = load_profiles()
    existing_hosts = {p["host"].lower() for p in existing}

    added = 0
    skipped = 0
    for p in new_profiles:
        if p["host"].lower() in existing_hosts:
            skipped += 1
        else:
            add_profile(p)
            existing_hosts.add(p["host"].lower())
            added += 1

    return added, skipped
