<p align="center">
  <img src="assets/ixel-logo.png" alt="Ixel" width="280">
</p>

# 🦞 ClawTTY — Universal AI Agent Console

> The SSH launcher built for the age of AI agents.

Connect to, manage, and monitor **any AI agent** running on any machine — from a $5 VPS to your home lab. Works with **OpenClaw**, **Hermes**, or any custom agent CLI. Not tied to any platform.

```bash
curl -fsSL https://raw.githubusercontent.com/OpenIxelAI/ClawTTY/main/install.sh | bash
```

---

## What It Is

ClawTTY is a PuTTY-style SSH launcher purpose-built for AI agent workflows. Save your machines as profiles, pick your agent (OpenClaw, Hermes, or custom), and connect in one click. It opens a real terminal session with security guardrails baked in from the start.

Think of it as the missing GUI for your AI agents — like AWS Console for EC2, but for agents.

---

## Features

- **Agent-agnostic** — OpenClaw, Hermes, or any custom command. Not locked to one platform.
- **Per-profile agent selection** — each host picks its own agent + command preset
- **One-click connect** — spawns your preferred terminal (konsole, gnome-terminal, kitty, alacritty, xterm)
- **Tabbed sessions** — multiple simultaneous connections in one window
- **Broadcast mode** — send a command to all sessions at once (agent-aware)
- **Quick macros** — one-click buttons for Status / Sessions / Logs / TUI per agent
- **Native WebSocket mode** — connect directly to an agent gateway, no SSH needed *(in progress)*
- **Host key pinning** — SSH fingerprints verified and stored; mismatches blocked
- **Keychain integration** — credentials stored via libsecret, never in plaintext
- **Audit log** — every connection attempt logged locally
- **SSH config import** — bulk-import hosts from `~/.ssh/config`
- **SSH key generation** — generate ed25519/RSA keys and push with `ssh-copy-id`
- **Dark theme** — IxelOS-inspired design, light/dark toggle

---

## Supported Agents

| Agent | Preset Commands |
|---|---|
| **OpenClaw** | `openclaw tui` · `openclaw status` · `openclaw sessions` · `openclaw logs` |
| **Hermes** | `hermes tui` · `hermes status` · `hermes sessions` · `hermes logs` |
| **Custom** | Any command you type (guarded against shell metacharacters) |

---

## Install

**One-liner (Linux & macOS):**
```bash
curl -fsSL https://raw.githubusercontent.com/OpenIxelAI/ClawTTY/main/install.sh | bash
```

Works on Fedora, Ubuntu/Debian, Arch, and macOS. The installer handles Python, system deps, and drops a `clawtty` command on your PATH.

**Windows / WSL2:**
```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

**Then just run:**
```bash
clawtty
```

**Update anytime:**
```bash
curl -fsSL https://raw.githubusercontent.com/OpenIxelAI/ClawTTY/main/install.sh | bash
```
*(Re-running the installer updates in place)*

---

## Requirements

- **OS:** Linux (Fedora, Ubuntu, Arch), macOS, Windows, or WSL2
- **Python:** 3.10+
- **SSH client:** `ssh`, `ssh-keygen`, `ssh-copy-id` on PATH
- **Terminal:** konsole, gnome-terminal, kitty, alacritty, or xterm

---

## File Locations

| File | Location |
|---|---|
| Profiles | `~/.config/clawtty/profiles.json` |
| Known hosts | `~/.local/share/clawtty/known_hosts` |
| Audit log | `~/.local/share/clawtty/audit.log` |
| Install dir | `~/.local/share/clawtty/` |
| Launcher | `~/.local/bin/clawtty` |

---

## Security

- **Preset agents** — only the four built-in commands allowed per agent, no arbitrary shell
- **Custom agent** — user-entered command with length cap + shell metacharacter blocking
- **No plaintext secrets** — libsecret/keychain only, profiles are credential-free
- **Host key pinning** — mismatches block connection, never silently proceed
- **Fail closed** — any validation failure refuses to connect
- **No telemetry** — zero network calls except the sessions you start

See [SECURITY.md](SECURITY.md) for the full threat model.

---

## Roadmap

- [x] OpenClaw + Hermes agent presets
- [x] Agent-agnostic profile system
- [x] Universal one-liner installer (Linux + macOS)
- [ ] **Native WebSocket mode** — direct gateway connect, no SSH needed
- [x] **Agent status dashboard** — online/offline, last active at a glance
- [x] **Windows/WSL2 support**
- [x] **Per-profile token vault** — API tokens in keychain
- [x] **Session log export**
- [ ] **GitHub release + demo video**

---

## License

MIT — see [LICENSE](LICENSE).

---

*Built by [OpenIxelAI](https://github.com/OpenIxelAI)*
