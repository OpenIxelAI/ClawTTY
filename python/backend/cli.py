"""
ClawTTY CLI — subcommand dispatcher
Usage: clawtty [command] [args]
"""

import sys
import os
import json
import subprocess
import shutil
from pathlib import Path
from .platform_info import platform_label, use_keyring_backend, is_windows

VERSION = "3.0.0"
REPO_URL = "git@github.com:OpenIxelAI/ClawTTY.git"
INSTALL_DIR = Path.home() / ".local" / "share" / "clawtty"
AUDIT_LOG   = Path.home() / ".local" / "share" / "clawtty" / "audit.log"
PROFILES_FILE = Path.home() / ".config" / "clawtty" / "profiles.json"

# ── Colors ────────────────────────────────────────────────────────────────────
R = "\033[0m"
CYAN   = "\033[0;36m"
GREEN  = "\033[0;32m"
YELLOW = "\033[1;33m"
RED    = "\033[0;31m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
PURPLE = "\033[0;35m"

def c(color, text): return f"{color}{text}{R}"

# ── Banner ────────────────────────────────────────────────────────────────────
BANNER = f"""
{CYAN}{BOLD} ██████╗██╗      █████╗ ██╗    ██╗████████╗████████╗██╗   ██╗
██╔════╝██║     ██╔══██╗██║    ██║╚══██╔══╝╚══██╔══╝╚██╗ ██╔╝
██║     ██║     ███████║██║ █╗ ██║   ██║      ██║    ╚████╔╝
██║     ██║     ██╔══██║██║███╗██║   ██║      ██║     ╚██╔╝
╚██████╗███████╗██║  ██║╚███╔███╔╝   ██║      ██║      ██║
 ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝    ╚═╝      ╚═╝      ╚═╝{R}
  {DIM}Universal AI Agent Console  ·  v{VERSION}{R}
  {DIM}https://github.com/OpenIxelAI/ClawTTY{R}
"""

# ── Help ──────────────────────────────────────────────────────────────────────
HELP = f"""
{CYAN}{BOLD}ClawTTY{R} — Universal AI Agent Console  {DIM}v{VERSION}{R}

{BOLD}USAGE{R}
  clawtty [command] [args]

{BOLD}COMMANDS{R}
  {CYAN}(no command){R}              Launch the GUI
  {CYAN}help{R}                      Show this help
  {CYAN}version{R}                   Show version info
  {CYAN}update{R}                    Pull latest from GitHub and restart
  {CYAN}doctor{R}                    Check system dependencies and config
  {CYAN}profiles{R}                  List all saved profiles
  {CYAN}connect{R} {YELLOW}<name>{R}           Open GUI focused on a profile
  {CYAN}sshconnect{R} {YELLOW}<name>{R}        SSH directly in this terminal (no GUI)
  {CYAN}status{R}                    Show running ClawTTY sessions
  {CYAN}logs{R}                      Tail the audit log
  {CYAN}config{R}                    Open settings in GUI
  {CYAN}agent{R} list                 List all agent plugins + commands
  {CYAN}agent{R} refresh [id]         Fetch latest commands from agent binary
  {CYAN}agent{R} commands <id>        Show all commands for an agent
  {CYAN}uninstall{R}                  Remove ClawTTY from this machine

{BOLD}EXAMPLES{R}
  clawtty                        # Open the GUI
  clawtty connect home-server    # Open GUI on home-server profile
  clawtty sshconnect vps         # SSH into vps right now
  clawtty doctor                 # Make sure everything works
  clawtty update                 # Get the latest version

{BOLD}AGENTS SUPPORTED{R}
  {CYAN}openclaw{R}   openclaw tui / status / sessions / logs
  {PURPLE}hermes{R}     hermes / hermes chat / status / sessions / logs
  {YELLOW}custom{R}     any command you define per profile

  Run {CYAN}clawtty agent list{R} to see all available commands per agent.

{DIM}Docs: https://github.com/OpenIxelAI/ClawTTY{R}
"""

# ── Helpers ───────────────────────────────────────────────────────────────────
def load_profiles() -> list:
    if not PROFILES_FILE.exists():
        return []
    try:
        data = json.loads(PROFILES_FILE.read_text())
        profiles = []
        for group in data.get("groups", []):
            profiles.extend(group.get("profiles", []))
        return profiles
    except Exception:
        return []

def find_profile(name: str) -> dict | None:
    name_lower = name.lower()
    for p in load_profiles():
        if p.get("name", "").lower() == name_lower:
            return p
    return None

def gui_main_path() -> Path:
    # Find clawtty.py relative to this file
    here = Path(__file__).parent.parent
    return here / "clawtty.py"

# ── Commands ──────────────────────────────────────────────────────────────────
def cmd_help():
    print(BANNER)
    print(HELP)

def cmd_version():
    print(BANNER)
    print(f"{c(CYAN+BOLD, 'ClawTTY')} {c(DIM, 'v'+VERSION)}")
    print(f"  Install dir : {INSTALL_DIR}")
    print(f"  Profiles    : {PROFILES_FILE}")
    print(f"  Audit log   : {AUDIT_LOG}")
    print(f"  Repo        : {REPO_URL}\n")

def cmd_update():
    print(c(CYAN, "▸ Pulling latest from GitHub..."))
    if not INSTALL_DIR.exists():
        print(c(RED, "✗ Install dir not found. Re-run the installer."))
        sys.exit(1)
    result = subprocess.run(
        ["git", "-C", str(INSTALL_DIR), "pull", "--ff-only"],
        capture_output=False
    )
    if result.returncode == 0:
        print(c(GREEN, "✓ Updated! Restarting ClawTTY..."))
        os.execv(sys.argv[0], sys.argv)
    else:
        print(c(RED, "✗ Update failed. Check your connection or run: git -C ~/.local/share/clawtty pull"))
        sys.exit(1)

def cmd_doctor():
    print(f"\n{c(BOLD, 'ClawTTY Doctor')} — checking your setup...\n")

    checks = []
    platform_name = platform_label()
    checks.append((True, f"Platform detected: {platform_name}", ""))

    # Python version
    import sys as _sys
    v = _sys.version_info
    ok = v.major == 3 and v.minor >= 10
    checks.append((ok, f"Python {v.major}.{v.minor}.{v.micro}", "Need Python 3.10+"))

    # SSH
    ssh = shutil.which("ssh")
    checks.append((bool(ssh), f"ssh found at {ssh}" if ssh else "ssh not found", "Install openssh-client"))

    # customtkinter
    try:
        import customtkinter
        checks.append((True, f"customtkinter {customtkinter.__version__}", ""))
    except ImportError:
        checks.append((False, "customtkinter not installed", "pip install customtkinter"))

    # paramiko
    try:
        import paramiko
        checks.append((True, f"paramiko {paramiko.__version__}", ""))
    except ImportError:
        checks.append((False, "paramiko not installed", "pip install paramiko"))

    # keychain backend
    if use_keyring_backend():
        try:
            import keyring
            checks.append((True, f"keyring available ({keyring.__version__})", ""))
        except ImportError:
            checks.append((False, "keyring not installed", "pip install keyring"))
    else:
        try:
            import secretstorage
            checks.append((True, "secretstorage available", ""))
        except ImportError:
            checks.append((False, "secretstorage not installed", "pip install secretstorage"))

    # terminal launcher availability
    if is_windows():
        wt = shutil.which("wt.exe")
        cmd = shutil.which("cmd.exe")
        checks.append((bool(wt or cmd), f"terminal launcher: {wt or cmd or 'missing'}", "Install Windows Terminal"))
    else:
        term = shutil.which("konsole") or shutil.which("gnome-terminal") or shutil.which("kitty") or shutil.which("alacritty") or shutil.which("xterm")
        checks.append((bool(term), f"terminal launcher: {term or 'missing'}", "Install a supported terminal emulator"))

    # Profiles file
    exists = PROFILES_FILE.exists()
    count = len(load_profiles())
    checks.append((True, f"Profiles: {count} saved ({PROFILES_FILE})", ""))

    # Audit log
    checks.append((True, f"Audit log: {AUDIT_LOG}", ""))

    # Print results
    all_ok = True
    for ok, msg, fix in checks:
        icon = c(GREEN, "✓") if ok else c(RED, "✗")
        print(f"  {icon}  {msg}")
        if not ok:
            all_ok = False
            print(f"      {c(YELLOW, '→')} {fix}")

    print()
    if all_ok:
        print(c(GREEN, "  All checks passed. ClawTTY is ready."))
    else:
        print(c(YELLOW, "  Some checks failed. Fix the issues above and re-run."))
    print()

def cmd_profiles():
    profiles = load_profiles()
    if not profiles:
        print(c(YELLOW, "\n  No profiles saved yet. Open ClawTTY and add one.\n"))
        return

    print(f"\n{c(BOLD, 'Saved Profiles')} ({len(profiles)})\n")
    for p in profiles:
        name    = p.get("name", "unnamed")
        host    = p.get("host", "?")
        user    = p.get("username", "?")
        port    = p.get("port", 22)
        agent   = p.get("agent", "openclaw")
        cmd     = p.get("remote_command", "")
        agent_color = CYAN if agent == "openclaw" else PURPLE if agent == "hermes" else YELLOW
        print(f"  {c(BOLD, name)}")
        print(f"    {c(DIM, 'host')}    {user}@{host}:{port}")
        print(f"    {c(DIM, 'agent')}   {c(agent_color, agent)}  {c(DIM, cmd)}")
        print()

def cmd_connect(name: str):
    profile = find_profile(name)
    if not profile:
        print(c(RED, f"\n✗ Profile '{name}' not found. Run 'clawtty profiles' to see all.\n"))
        sys.exit(1)
    print(c(CYAN, f"▸ Opening GUI for profile: {name}"))
    subprocess.Popen([sys.executable, str(gui_main_path()), "--profile", name])

def cmd_sshconnect(name: str):
    profile = find_profile(name)
    if not profile:
        print(c(RED, f"\n✗ Profile '{name}' not found. Run 'clawtty profiles' to see all.\n"))
        sys.exit(1)

    host    = profile.get("host", "")
    user    = profile.get("username", "")
    port    = profile.get("port", 22)
    cmd     = profile.get("remote_command", "")
    keyfile = profile.get("key_path", "")
    agent   = profile.get("agent", "openclaw")

    if not host or not user:
        print(c(RED, "✗ Profile is missing host or username."))
        sys.exit(1)

    ssh_cmd = ["ssh", "-t", "-p", str(port)]
    if keyfile:
        ssh_cmd += ["-i", keyfile]
    ssh_cmd += [f"{user}@{host}"]
    if cmd:
        ssh_cmd += [cmd]

    agent_color = CYAN if agent == "openclaw" else PURPLE if agent == "hermes" else YELLOW
    print(f"\n{c(CYAN, '▸')} Connecting to {c(BOLD, name)} ({user}@{host}:{port})")
    print(f"  Agent : {c(agent_color, agent)}  {c(DIM, cmd)}\n")

    os.execvp("ssh", ssh_cmd)

def cmd_status():
    result = subprocess.run(["pgrep", "-a", "-f", "clawtty.py"], capture_output=True, text=True)
    lines = [l for l in result.stdout.strip().splitlines() if str(os.getpid()) not in l]
    if lines:
        print(f"\n{c(BOLD, 'Running ClawTTY processes')}\n")
        for line in lines:
            print(f"  {c(CYAN, '▸')} {line}")
        print()
    else:
        print(c(DIM, "\n  No ClawTTY processes running.\n"))

def cmd_logs():
    if not AUDIT_LOG.exists():
        print(c(YELLOW, f"\n  No audit log yet at {AUDIT_LOG}\n"))
        return
    print(f"\n{c(BOLD, 'Audit Log')} — {AUDIT_LOG}\n")
    try:
        subprocess.run(["tail", "-n", "50", str(AUDIT_LOG)])
    except KeyboardInterrupt:
        pass

def cmd_config():
    print(c(CYAN, "▸ Opening ClawTTY settings..."))
    subprocess.Popen([sys.executable, str(gui_main_path()), "--settings"])

def cmd_agent(args: list[str]):
    from .agent_plugins import all_agents, refresh_plugin, refresh_all, get_commands

    if not args or args[0] == "list":
        print(f"\n{c(BOLD, 'Available Agent Plugins')}\n")
        for plugin in all_agents():
            color = CYAN if plugin.id == "openclaw" else PURPLE if plugin.id == "hermes" else YELLOW
            print(f"  {c(color+BOLD, plugin.name):<30} {c(DIM, plugin.version)}")
            for cmd in plugin.commands[:4]:  # show first 4
                print(f"    {c(color, '▸')} {cmd.command:<35} {c(DIM, cmd.description[:50])}")
            if len(plugin.commands) > 4:
                print(f"    {c(DIM, f'... and {len(plugin.commands)-4} more')}")
            print()

    elif args[0] == "refresh":
        target = args[1] if len(args) > 1 else None
        if target:
            print(c(CYAN, f"▸ Refreshing {target} commands..."))
            ok, msg = refresh_plugin(target)
            icon = c(GREEN, "✓") if ok else c(RED, "✗")
            print(f"  {icon}  {msg}")
        else:
            print(c(CYAN, "▸ Refreshing all agent commands..."))
            results = refresh_all()
            for agent_id, (ok, msg) in results.items():
                icon = c(GREEN, "✓") if ok else c(RED, "✗")
                print(f"  {icon}  {c(BOLD, agent_id)}: {msg}")
        print()

    elif args[0] == "commands":
        if len(args) < 2:
            print(c(RED, "\n✗ Usage: clawtty agent commands <agent-id>\n"))
            sys.exit(1)
        agent_id = args[1]
        cmds = get_commands(agent_id)
        if not cmds:
            print(c(RED, f"\n✗ No plugin found for '{agent_id}'\n"))
            sys.exit(1)
        color = CYAN if agent_id == "openclaw" else PURPLE if agent_id == "hermes" else YELLOW
        print(f"\n{c(BOLD, agent_id.title())} commands ({len(cmds)} total)\n")
        for cmd in cmds:
            shortcut = f"  {c(DIM, cmd.shortcut)}" if cmd.shortcut else ""
            print(f"  {c(color, '▸')} {cmd.command:<35} {c(DIM, cmd.description[:60])}{shortcut}")
        print()

    else:
        print(c(RED, f"\n✗ Unknown agent subcommand: '{args[0]}'"))
        print(f"  Usage: clawtty agent [list|refresh|commands <id>]\n")
        sys.exit(1)


def cmd_uninstall():
    print(f"\n{c(YELLOW+BOLD, 'Uninstall ClawTTY')}\n")
    print(f"  This will remove:")
    print(f"    {INSTALL_DIR}")
    print(f"    {Path.home() / '.local' / 'bin' / 'clawtty'}")
    print(f"    {Path.home() / '.local' / 'share' / 'applications' / 'clawtty.desktop'}")
    print(f"\n  Profiles at {PROFILES_FILE} will {c(BOLD, 'NOT')} be deleted.\n")

    confirm = input(f"  {c(YELLOW, 'Type YES to confirm: ')}").strip()
    if confirm != "YES":
        print(c(DIM, "  Cancelled.\n"))
        return

    paths = [
        INSTALL_DIR,
        Path.home() / ".local" / "bin" / "clawtty",
        Path.home() / ".local" / "share" / "applications" / "clawtty.desktop",
    ]
    for p in paths:
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            print(c(GREEN, f"  ✓ Removed {p}"))

    print(f"\n{c(GREEN, '  ClawTTY uninstalled.')} Your profiles are still at {PROFILES_FILE}\n")

# ── Dispatcher ────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]

    if not args:
        # No subcommand — launch GUI
        return False  # tells clawtty.py to continue with GUI launch

    cmd = args[0].lower()

    if cmd in ("help", "--help", "-h"):
        cmd_help()
    elif cmd in ("version", "--version", "-v"):
        cmd_version()
    elif cmd == "update":
        cmd_update()
    elif cmd == "doctor":
        cmd_doctor()
    elif cmd == "profiles":
        cmd_profiles()
    elif cmd == "connect":
        if len(args) < 2:
            print(c(RED, "\n✗ Usage: clawtty connect <profile-name>\n"))
            sys.exit(1)
        cmd_connect(args[1])
    elif cmd == "sshconnect":
        if len(args) < 2:
            print(c(RED, "\n✗ Usage: clawtty sshconnect <profile-name>\n"))
            sys.exit(1)
        cmd_sshconnect(args[1])
    elif cmd == "status":
        cmd_status()
    elif cmd == "logs":
        cmd_logs()
    elif cmd == "config":
        cmd_config()
    elif cmd == "agent":
        cmd_agent(args[1:])
    elif cmd == "uninstall":
        cmd_uninstall()
    else:
        print(c(RED, f"\n✗ Unknown command: '{cmd}'"))
        print(f"  Run {c(CYAN, 'clawtty help')} to see all commands.\n")
        sys.exit(1)

    return True  # CLI handled it, don't launch GUI
