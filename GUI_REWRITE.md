# ClawTTY — GUI Rewrite Plan

## Goal
Replace CustomTkinter with a modern, industry-standard stack.
ClawTTY should look like a premium product — elegant, alive, intentional.
Not a dev tool. A product people want to open.

## Stack Decision: Tauri v2

**Why Tauri:**
- Industry standard for modern desktop apps (used by 1Password, Zed, etc.)
- Native OS windows — looks right on Linux, macOS, Windows
- Tiny binary (no bundled Chromium like Electron)
- Web frontend = full CSS control = IxelOS aesthetic
- Rust backend = fast, safe, cross-platform
- Python SSH/WS logic bridges via sidecar or IPC

**Frontend: React + TypeScript**
- Industry standard
- Component-based = clean, reusable widgets
- Tailwind CSS for styling
- Framer Motion for animations (smooth, alive feel)

**Icons: Lucide or Phosphor Icons**
- Clean, consistent, modern
- Not emoji, not flat Bootstrap icons
- Phosphor has weight variants (thin/regular/bold/fill) — perfect for IxelOS vibe

## Design Direction

### Vibe
- **Elegant, dark, premium** — think Linear, Vercel dashboard, Raycast
- Not "dark mode Bootstrap" — intentional spacing, typography, hierarchy
- Subtle animations — connection state changes, profile hover, status pulses
- Everything feels *alive* not static

### IxelOS Palette (carry over)
- Background: `#070b14` space black
- Surface: `#0d1b2a` midnight navy  
- Text primary: `#c8d8e8` moonstone
- Accent: `#7eb8d4` lunar blue
- Purple: `#9b7fc7` violet
- Gold: `#d4af37` (OpenClaw accent)
- Success: `#4ade80` green
- Error: `#e05252` ember red

### Typography
- **Inter** or **Geist** — clean, modern, readable
- Not system font, not monospace for UI labels
- Mono font for terminal output only (JetBrains Mono / Fira Code)

### Layout Improvements
- Sidebar: profile cards with agent badge, subtle hover glow, connection status dot
- Session area: proper terminal embed (xterm.js) — real terminal, not a text widget
- Status dashboard: card grid, animated pulse on online agents
- Command palette: `Cmd+K` / `Ctrl+K` quick connect — like Raycast/Linear
- Smooth transitions between panels — no jarring redraws

### Key Widget Upgrades
| Current (CTk) | New (Tauri/React) |
|---|---|
| CTkButton | Styled button with hover/active states |
| CTkEntry | Floating label input, focus ring |
| CTkOptionMenu | Custom dropdown with search |
| Text widget (terminal) | xterm.js (real terminal emulator) |
| CTkLabel status dot | Animated pulse dot (CSS keyframes) |
| Sidebar profile list | Card list with avatar/icon, agent badge, status |
| Tab bar | Pill tabs with close button, drag to reorder |

## What Stays (Python backend)
- SSH connection logic (`python/backend/ssh.py`)
- WebSocket client (`python/backend/ws_client.py`)
- Credential/keychain management (`python/backend/credentials.py`)
- Profile config (`python/backend/config.py`)
- Audit logging (`python/backend/audit.py`)
- CLI subcommands (`python/backend/cli.py`)

These become a Python sidecar process that Tauri talks to via IPC/stdio.

## Build Order
1. ✅ Finish 4 remaining features in CustomTkinter (current)
2. ✅ Ship v1.0.0 with current UI
3. 🔄 Tauri rewrite → v2.0.0
   - Set up Tauri + React + TypeScript scaffold
   - Port Python backend as sidecar
   - Build new UI components
   - xterm.js terminal integration
   - Full IxelOS design system

## Reference Apps (aesthetic inspiration)
- **Raycast** — command palette, clean sidebar, premium feel
- **Linear** — card layouts, subtle animations, dark theme done right  
- **Warp terminal** — modern terminal UI, agent-aware
- **Zed editor** — minimal, fast, elegant
