#!/usr/bin/env bash
# ClawTTY v3 — Fedora installer
# Usage: bash install-fedora.sh
set -euo pipefail

APP_NAME="clawtty-v3"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "🦞  ClawTTY v3 — Fedora Installer"
echo "────────────────────────────────────"

# 1. Python deps
echo "→ Installing Python dependencies..."
pip install --user --quiet "customtkinter>=5.2.0" "secretstorage>=3.3.0" "paramiko>=3.4.0"
echo "  ✔ Dependencies installed"

# 2. Copy app files
echo "→ Installing app to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/clawtty.py" "$INSTALL_DIR/"
mkdir -p "$INSTALL_DIR/python"
cp -r "$SCRIPT_DIR/python/backend" "$INSTALL_DIR/python/"
echo "  ✔ App files installed"

# 3. Launcher script
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/clawtty" << 'LAUNCHER'
#!/usr/bin/env bash
exec python3 "$HOME/.local/share/clawtty-v3/clawtty.py" "$@"
LAUNCHER
chmod +x "$BIN_DIR/clawtty"
echo "  ✔ Launcher created at $BIN_DIR/clawtty"

# 4. Desktop entry
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/clawtty.desktop" << DESKTOP
[Desktop Entry]
Name=ClawTTY v3
Comment=PuTTY-style SSH launcher for AI agent CLIs (OpenClaw, Hermes, custom)
Exec=$BIN_DIR/clawtty
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=Network;RemoteAccess;Security;
Keywords=ssh;terminal;agent;remote;openclaw;hermes;
DESKTOP
echo "  ✔ Desktop entry created"

# 5. Ensure ~/.local/bin is on PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo ""
    echo "  ⚠  $BIN_DIR is not on your PATH."
    echo "     Add this to your ~/.bashrc or ~/.zshrc:"
    echo '     export PATH="$HOME/.local/bin:$PATH"'
fi

echo ""
echo "✅  ClawTTY v3 installed successfully!"
echo ""
echo "   Run:  clawtty"
echo "   Or find it in your application launcher."
echo ""
echo "   Config:    ~/.config/clawtty/profiles.json"
echo "   Audit log: ~/.local/share/clawtty/audit.log"
echo "   Known hosts: ~/.local/share/clawtty/known_hosts"
echo ""
