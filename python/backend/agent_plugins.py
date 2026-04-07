"""
agent_plugins.py — Agent command plugin system for ClawTTY.

Each agent (openclaw, hermes, custom) has a plugin definition that describes:
  - Display name and version
  - Available commands with labels, descriptions, keyboard shortcuts
  - How to fetch the latest commands from the agent's source

Plugins can be bundled (built-in) or fetched live from GitHub/docs.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import NamedTuple

PLUGINS_CACHE = Path.home() / ".config" / "clawtty" / "agent_plugins.json"
PLUGINS_CACHE.parent.mkdir(parents=True, exist_ok=True)

# ── Data model ────────────────────────────────────────────────────────────────

class AgentCommand(NamedTuple):
    label: str          # Short label for macro button e.g. "Chat"
    command: str        # Full command string e.g. "hermes chat"
    description: str    # Tooltip / help text
    shortcut: str = ""  # Optional keyboard shortcut


class AgentPlugin(NamedTuple):
    id: str             # "openclaw" | "hermes" | "custom"
    name: str           # Display name
    version: str        # Cached version string
    color: str          # Accent color (hex)
    commands: list[AgentCommand]
    fetch_url: str = "" # URL to fetch latest commands from


# ── Built-in plugin definitions ───────────────────────────────────────────────

BUILTIN_PLUGINS: dict[str, AgentPlugin] = {
    "openclaw": AgentPlugin(
        id="openclaw",
        name="OpenClaw",
        version="latest",
        color="#d4af37",  # gold
        commands=[
            AgentCommand("TUI",      "openclaw tui",      "Launch OpenClaw terminal UI",          "Ctrl+4"),
            AgentCommand("Status",   "openclaw status",   "Show OpenClaw status",                 "Ctrl+1"),
            AgentCommand("Sessions", "openclaw sessions", "List active sessions",                 "Ctrl+2"),
            AgentCommand("Logs",     "openclaw logs",     "Tail OpenClaw logs",                   "Ctrl+3"),
        ],
        fetch_url="https://raw.githubusercontent.com/openclaw/openclaw/main/docs/cli.md",
    ),

    "hermes": AgentPlugin(
        id="hermes",
        name="Hermes",
        version="latest",
        color="#9b7fc7",  # purple
        commands=[
            AgentCommand("Chat",     "hermes",            "Launch Hermes interactive TUI",        ""),
            AgentCommand("Status",   "hermes status",     "Show agent, auth, and platform status",""),
            AgentCommand("Sessions", "hermes sessions",   "Browse session history",               ""),
            AgentCommand("Logs",     "hermes logs",       "Tail Hermes logs",                     ""),
            AgentCommand("Doctor",   "hermes doctor",     "Diagnose config and dependency issues",""),
            AgentCommand("Update",   "hermes update",     "Pull latest and reinstall deps",       ""),
            AgentCommand("Gateway",  "hermes gateway run","Run the messaging gateway",            ""),
            AgentCommand("Skills",   "hermes skills",     "Browse and manage skills",             ""),
            AgentCommand("Model",    "hermes model",      "Switch model/provider",                ""),
            AgentCommand("Config",   "hermes config",     "View and edit configuration",          ""),
            AgentCommand("Insights", "hermes insights",   "Token/cost/activity analytics",        ""),
            AgentCommand("Memory",   "hermes memory",     "Configure memory provider",            ""),
        ],
        fetch_url="https://hermes-agent.nousresearch.com/docs/reference/cli-commands",
    ),
}


# ── Plugin registry ───────────────────────────────────────────────────────────

def get_plugin(agent_id: str) -> AgentPlugin | None:
    """Return plugin for agent_id, checking cache first then builtins."""
    cached = _load_cache()
    if agent_id in cached:
        return _dict_to_plugin(cached[agent_id])
    return BUILTIN_PLUGINS.get(agent_id)


def get_commands(agent_id: str) -> list[AgentCommand]:
    """Return command list for agent_id."""
    plugin = get_plugin(agent_id)
    return plugin.commands if plugin else []


def get_preset_commands(agent_id: str) -> tuple[str, ...]:
    """Return just the command strings as a tuple (for config.py compatibility)."""
    return tuple(cmd.command for cmd in get_commands(agent_id))


def all_agents() -> list[AgentPlugin]:
    """Return all known agent plugins."""
    result = dict(BUILTIN_PLUGINS)
    cached = _load_cache()
    for agent_id, data in cached.items():
        result[agent_id] = _dict_to_plugin(data)
    return list(result.values())


# ── Cache ─────────────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    if PLUGINS_CACHE.exists():
        try:
            return json.loads(PLUGINS_CACHE.read_text())
        except Exception:
            pass
    return {}


def _save_cache(data: dict) -> None:
    try:
        PLUGINS_CACHE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def _plugin_to_dict(plugin: AgentPlugin) -> dict:
    return {
        "id": plugin.id,
        "name": plugin.name,
        "version": plugin.version,
        "color": plugin.color,
        "commands": [
            {"label": c.label, "command": c.command,
             "description": c.description, "shortcut": c.shortcut}
            for c in plugin.commands
        ],
        "fetch_url": plugin.fetch_url,
    }


def _dict_to_plugin(d: dict) -> AgentPlugin:
    return AgentPlugin(
        id=d["id"],
        name=d["name"],
        version=d.get("version", "unknown"),
        color=d.get("color", "#7eb8d4"),
        commands=[
            AgentCommand(
                label=c["label"],
                command=c["command"],
                description=c.get("description", ""),
                shortcut=c.get("shortcut", ""),
            )
            for c in d.get("commands", [])
        ],
        fetch_url=d.get("fetch_url", ""),
    )


# ── Live fetch ────────────────────────────────────────────────────────────────

def refresh_plugin(agent_id: str, timeout: int = 8) -> tuple[bool, str]:
    """
    Fetch the latest command list for agent_id from its source.
    Returns (success, message).

    Currently parses the installed binary's --help output for accuracy.
    Falls back to builtin definitions if fetch fails.
    """
    import subprocess
    import shutil

    binary = agent_id  # "openclaw" or "hermes"
    if not shutil.which(binary):
        return False, f"{binary} not found on PATH"

    try:
        result = subprocess.run(
            [binary, "--help"],
            capture_output=True, text=True, timeout=timeout
        )
        output = result.stdout + result.stderr

        # Parse commands from help output
        commands = _parse_help_commands(agent_id, output)
        if not commands:
            return False, "Could not parse commands from --help output"

        builtin = BUILTIN_PLUGINS.get(agent_id)
        plugin = AgentPlugin(
            id=agent_id,
            name=builtin.name if builtin else agent_id.title(),
            version=_get_version(binary),
            color=builtin.color if builtin else "#7eb8d4",
            commands=commands,
            fetch_url=builtin.fetch_url if builtin else "",
        )

        # Save to cache
        cache = _load_cache()
        cache[agent_id] = _plugin_to_dict(plugin)
        _save_cache(cache)

        return True, f"Updated {len(commands)} commands for {agent_id}"

    except subprocess.TimeoutExpired:
        return False, f"{binary} --help timed out"
    except Exception as exc:
        return False, str(exc)


def _get_version(binary: str) -> str:
    import subprocess
    try:
        r = subprocess.run([binary, "version"], capture_output=True, text=True, timeout=5)
        line = (r.stdout + r.stderr).strip().splitlines()[0]
        return line[:60]
    except Exception:
        return "unknown"


def _parse_help_commands(agent_id: str, help_text: str) -> list[AgentCommand]:
    """Parse subcommands from --help output."""
    commands: list[AgentCommand] = []
    in_commands = False

    # Map of subcommand → friendly label
    label_map = {
        "tui": "TUI", "chat": "Chat", "status": "Status",
        "sessions": "Sessions", "logs": "Logs", "doctor": "Doctor",
        "update": "Update", "gateway": "Gateway", "skills": "Skills",
        "model": "Model", "config": "Config", "insights": "Insights",
        "memory": "Memory", "setup": "Setup", "version": "Version",
    }

    import re
    lines = help_text.splitlines()

    # Strategy 1: argparse style — {cmd1,cmd2,...} block (Hermes)
    full_text = " ".join(lines)
    match = re.search(r'\{([^}]+)\}', full_text)
    if match:
        subcmds = match.group(1).split(",")
        # Collect descriptions from indented lines like "    chat    description"
        desc_map: dict[str, str] = {}
        for line in lines:
            m2 = re.match(r'^\s{2,8}(\w[\w-]*)\s{2,}(.+)$', line)
            if m2:
                desc_map[m2.group(1)] = m2.group(2).strip()
        for sc in subcmds:
            sc = sc.strip()
            if sc and not sc.startswith("-"):
                label = label_map.get(sc, sc.title())
                cmd = f"{agent_id} {sc}"
                desc = desc_map.get(sc, f"Run {cmd}")
                commands.append(AgentCommand(label=label, command=cmd, description=desc))

    # Strategy 2: Commander.js style — "  cmd *    description" lines (OpenClaw)
    if not commands:
        in_commands = False
        for line in lines:
            if re.match(r'^Commands:', line):
                in_commands = True
                continue
            if in_commands:
                # Match "  cmdname *?    description"
                m = re.match(r'^  ([a-z][a-z0-9-]*)\s*\*?\s{2,}(.+)$', line)
                if m:
                    sc = m.group(1)
                    desc = m.group(2).strip()
                    label = label_map.get(sc, sc.title())
                    cmd = f"{agent_id} {sc}"
                    commands.append(AgentCommand(label=label, command=cmd, description=desc))
                elif line.startswith('  ') and not line.startswith('   '):
                    # Possible end of commands block
                    pass

    # If hermes with no subcommand = main TUI — add it first
    if agent_id == "hermes" and commands:
        commands.insert(0, AgentCommand(
            label="Chat", command="hermes",
            description="Launch Hermes interactive TUI",
        ))

    return commands if commands else []


# ── CLI helper ────────────────────────────────────────────────────────────────

def refresh_all() -> dict[str, tuple[bool, str]]:
    """Refresh all known agents. Returns {agent_id: (success, msg)}."""
    results = {}
    for agent_id in BUILTIN_PLUGINS:
        results[agent_id] = refresh_plugin(agent_id)
    return results
