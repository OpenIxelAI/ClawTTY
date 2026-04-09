# ClawTTY v4 — Roadmap

> Universal AI Agent Console by IxelAI
> One app. Every agent. Every machine.

---

## Vision

ClawTTY is the desktop command center for AI coding agents. It gives you a unified interface to launch, monitor, manage, and interact with any AI agent — whether it's running locally, on a remote server, or inside a container. 

It's the app you open when you sit down to work.

---

## Current State (v3)

**Stack:** Tauri v2 (Rust) + React/TypeScript frontend + Python sidecar

**What exists:**
- Tauri shell builds to `.deb`/`.rpm`
- React components: Sidebar, TabBar, TerminalPane, ChatPane, ProfileDrawer, CommandPalette, StatusDashboard, Settings
- Python backend: WebSocket client (ed25519 handshake, OpenClaw protocol), SSH client, config, credentials, audit
- Profile system with groups
- IxelOS palette integrated

**What's incomplete:**
- Sidecar IPC bridge (Python ↔ Tauri frontend) — the critical gap
- Agent auto-detection
- Session persistence
- Diff view
- Real-time agent status

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  ClawTTY Desktop                     │
│                                                      │
│  ┌──────────┐  ┌──────────────────────────────────┐ │
│  │ Sidebar   │  │  Main Pane                       │ │
│  │           │  │                                  │ │
│  │ Agents    │  │  ┌─────────┐  ┌──────────────┐  │ │
│  │ Sessions  │  │  │Terminal │  │  Chat / Diff  │  │ │
│  │ Groups    │  │  │ (xterm) │  │   (React)     │  │ │
│  │ Status    │  │  └─────────┘  └──────────────┘  │ │
│  │           │  │                                  │ │
│  └──────────┘  │  TabBar: sessions + agents        │ │
│                └──────────────────────────────────┘ │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  Python Sidecar (IPC via stdin/stdout JSON)    │  │
│  │  • WebSocket gateway client                    │  │
│  │  • SSH connections (paramiko)                  │  │
│  │  • Agent discovery                             │  │
│  │  • Session state                               │  │
│  │  • Credential vault                            │  │
│  └────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Frontend:** React + TypeScript + Tailwind + Framer Motion + xterm.js
**Backend:** Python sidecar (WebSocket, SSH, agent management)
**Shell:** Tauri v2 (Rust — native window, IPC, keychain, file system)

---

## Phase 1 — Foundation (Get It Working)

**Goal:** App opens, connects to one agent, you can chat.

- [ ] **Sidecar IPC bridge** — JSON-RPC over stdin/stdout between Tauri and Python
  - Tauri `Command` → spawns Python sidecar
  - Bidirectional message passing
  - Error handling + reconnect
- [ ] **Single agent connection** — Connect to OpenClaw gateway via WebSocket
  - Reuse existing `ws_client.py` protocol
  - Display chat messages in `ChatPane`
  - Send messages from input bar
- [ ] **xterm.js terminal** — Embed a real terminal for SSH sessions
  - PTY over IPC
  - Resize handling
  - Copy/paste
- [ ] **Profile CRUD** — Create/edit/delete agent profiles via `ProfileDrawer`
  - Store in `~/.config/clawtty/profiles.json`
  - Token stored in system keychain via Tauri plugin

---

## Phase 2 — Multi-Agent Experience

**Goal:** Multiple agents running simultaneously, tabbed interface, real-time status.

- [ ] **Agent auto-detection** — Scan system for installed agent CLIs
  - Check PATH for: `openclaw`, `claude`, `codex`, `gemini`, `cursor`
  - Read their config files for connection details
  - Show detected agents in sidebar with install status
- [ ] **Multi-session tabs** — Open multiple agent sessions simultaneously
  - Each tab = one agent session (chat or terminal)
  - Tab bar with agent name, status indicator, close button
  - Keyboard shortcuts: `Ctrl+1-9` to switch, `Ctrl+W` to close
- [ ] **Real-time status detection** — Per-agent status indicators
  - `●` running (green) — actively generating
  - `◐` waiting (yellow) — waiting for user input
  - `○` idle (dim) — connected but not active
  - `✗` disconnected (red)
  - Poll via WebSocket events or process status
- [ ] **Session persistence** — Sessions survive app close
  - Background process manager keeps agents alive
  - Reopen app → reconnect to existing sessions
  - Optional: auto-save conversation history

---

## Phase 3 — Power Features

**Goal:** Features that make ClawTTY indispensable for daily work.

- [ ] **Git worktrees** — Parallel branches per agent
  - "New session on branch" button
  - Auto `git worktree add` with agent-specific directory
  - Visual branch indicator per session tab
  - Cleanup on session delete
- [ ] **Diff view** — See what each agent changed
  - `git diff` rendered inline with syntax highlighting
  - Toggle between chat view and diff view per session
  - File tree of changes on the left
  - Accept/reject hunks directly from the UI
- [ ] **Session forking** — Branch a conversation
  - Fork button on any message
  - Creates a new tab with conversation history up to that point
  - Explore different approaches without losing context
- [ ] **Docker sandboxing** — Optional container isolation
  - "Sandboxed" toggle when creating a session
  - Mount project directory read-write
  - Share auth credentials via volume mount
  - Visual indicator for sandboxed sessions
- [ ] **Command palette** — `Ctrl+K` quick launcher
  - Search agents, sessions, profiles
  - Quick actions: new session, switch tab, toggle diff, run command
  - Fuzzy matching

---

## Phase 4 — Integration & Polish

**Goal:** Deep integration with the IxelAI ecosystem and premium UX.

- [ ] **Ixel MAT integration** — Consensus from the GUI
  - `/full` and `/consensus` available from any session
  - Compare responses in a split-pane view
  - Synthesize across agents visually
- [ ] **Remote agent management** — Connect to agents on other machines
  - SSH tunnel + WebSocket forwarding
  - Agent health monitoring across machines
  - One-click deploy agent to remote
- [ ] **Notifications** — Desktop notifications for agent events
  - Agent finished generating
  - Agent waiting for input
  - Agent errored
  - Customizable per agent
- [ ] **Session groups** — Organize by project
  - Group sessions by project/repository
  - Collapse/expand groups in sidebar
  - Per-group settings (default agent, branch strategy)
- [ ] **Themes** — IxelOS palette + custom themes
  - Built-in: Dark (default), Light, Midnight, Nord
  - Custom theme support via JSON
  - Live preview in settings
- [ ] **Export & sharing** — Session logs and diffs
  - Export conversation as Markdown
  - Export diff as patch file
  - Share session via link (future: IxelAI cloud)

---

## Phase 5 — Distribution

**Goal:** Anyone can install and use ClawTTY in under a minute.

- [ ] **Cross-platform builds** — Linux (.deb, .rpm, AppImage), macOS (.dmg), Windows (.msi)
- [ ] **Auto-update** — Tauri built-in updater
- [ ] **Homebrew** — `brew install clawtty`
- [ ] **One-liner install** — `curl | bash` for Linux/macOS
- [ ] **First-run wizard** — Detect agents, configure profiles, connect
- [ ] **Documentation site** — Hosted on GitHub Pages or clawtty.dev
- [ ] **Demo video** — 60-second showcase of multi-agent workflow

---

## Design Principles

1. **Keyboard-first, mouse-friendly** — Every action has a shortcut. Nothing requires a mouse.
2. **Fast** — Sub-100ms response for all UI interactions. No loading spinners for local operations.
3. **Persistent** — Sessions don't die when you close the window. Your agents keep working.
4. **Agent-agnostic** — Works with any AI agent CLI. Not locked to one provider.
5. **Beautiful** — IxelOS aesthetic. Every pixel intentional. Animations that feel alive.
6. **Secure** — Tokens in keychain. ed25519 handshakes. Audit logs. No plaintext secrets.

---

## IxelOS Palette

| Token | Hex | Usage |
|---|---|---|
| `bg` | `#070b14` | App background |
| `surface` | `#0d1b2a` | Cards, panels, sidebar |
| `moon` | `#c8d8e8` | Primary text |
| `blue` | `#7eb8d4` | Links, active states |
| `violet` | `#9b7fc7` | Accents, highlights |
| `gold` | `#d4af37` | Warnings, branding |
| `dim` | `#6b7d94` | Secondary text, borders |
| `green` | `#4ade80` | Success, connected |
| `red` | `#e05252` | Error, disconnected |

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Desktop shell | Tauri v2 | Native windows, small binary, cross-platform |
| Frontend | React + TypeScript | Component model, ecosystem, type safety |
| Styling | Tailwind CSS | Utility-first, consistent, fast iteration |
| Animations | Framer Motion | Smooth, declarative, production-quality |
| Terminal | xterm.js | Real terminal emulation in the browser |
| Icons | Lucide | Clean, consistent, MIT licensed |
| Backend | Python sidecar | WebSocket/SSH clients, agent management |
| IPC | JSON-RPC (stdin/stdout) | Simple, debuggable, language-agnostic |
| Keychain | Tauri keychain plugin | Native OS secret storage |
| Build | Cargo + Vite | Fast builds, hot reload in dev |

---

*Built by IxelAI — tools for people who take AI seriously.*
