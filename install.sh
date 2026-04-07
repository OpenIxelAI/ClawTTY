#!/usr/bin/env bash
# ClawTTY — Universal AI Agent SSH Console
# One-liner install: curl -fsSL https://raw.githubusercontent.com/YOUR_USER/clawtty/main/install.sh | bash

set -euo pipefail

CLAWTTY_REPO="https://github.com/OpenIxelAI/ClawTTY"
CLAWTTY_VERSION="main"
INSTALL_DIR="$HOME/.local/share/clawtty"
BIN_DIR="$HOME/.local/bin"
PYTHON_MIN="3.10"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'

info()    { echo -e "${CYAN}▸${RESET} $*"; }
success() { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET} $*"; }
error()   { echo -e "${RED}✗${RESET} $*"; exit 1; }
header()  { echo -e "\n${BOLD}$*${RESET}"; }

main() {
# ── Banner ────────────────────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}"
cat << 'EOF'
 ██████╗██╗      █████╗ ██╗    ██╗████████╗████████╗██╗   ██╗
██╔════╝██║     ██╔══██╗██║    ██║╚══██╔══╝╚══██╔══╝╚██╗ ██╔╝
██║     ██║     ███████║██║ █╗ ██║   ██║      ██║    ╚████╔╝
██║     ██║     ██╔══██║██║███╗██║   ██║      ██║     ╚██╔╝
╚██████╗███████╗██║  ██║╚███╔███╔╝   ██║      ██║      ██║
 ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝    ╚═╝      ╚═╝      ╚═╝
EOF
echo -e "${RESET}"
echo -e "  ${DIM}Universal AI Agent Console  ·  v3${RESET}"
echo -e "  ${DIM}https://github.com/OpenIxelAI/ClawTTY${RESET}"

# ── Detect OS ─────────────────────────────────────────────────────────────────
header "Detecting system..."
OS="unknown"
PKG=""

if [[ -f /etc/os-release ]]; then
    source /etc/os-release
    case "$ID" in
        fedora|rhel|centos)   OS="fedora";  PKG="dnf" ;;
        ubuntu|debian|mint)   OS="debian";  PKG="apt" ;;
        arch|manjaro)         OS="arch";    PKG="pacman" ;;
        darwin)               OS="macos" ;;
        *)                    OS="unknown" ;;
    esac
fi

# macOS detection
if [[ "$(uname)" == "Darwin" ]]; then
    OS="macos"
    PKG="brew"
fi

info "OS: ${ID:-$(uname)} | Package manager: ${PKG:-none detected}"

# ── Check Python ──────────────────────────────────────────────────────────────
header "Checking Python..."

PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        MAJOR=${VER%%.*}; MINOR=${VER##*.}
        if [[ $MAJOR -ge 3 && $MINOR -ge 10 ]]; then
            PYTHON="$cmd"
            success "Found $cmd ($VER)"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    warn "Python $PYTHON_MIN+ not found. Installing..."
    case "$OS" in
        fedora)  sudo dnf install -y python3 ;;
        debian)  sudo apt-get install -y python3 python3-pip ;;
        arch)    sudo pacman -S --noconfirm python ;;
        macos)   brew install python3 ;;
        *)       error "Please install Python $PYTHON_MIN+ manually and re-run." ;;
    esac
    PYTHON="python3"
fi

# ── Install system deps ───────────────────────────────────────────────────────
header "Installing system dependencies..."

case "$OS" in
    fedora)
        info "Installing via dnf..."
        sudo dnf install -y \
            python3-tkinter \
            libsecret \
            python3-secretstorage \
            git \
            openssh-clients 2>/dev/null || true
        ;;
    debian)
        info "Installing via apt..."
        sudo apt-get update -qq
        sudo apt-get install -y \
            python3-tk \
            libsecret-1-0 \
            python3-secretstorage \
            git \
            openssh-client 2>/dev/null || true
        ;;
    arch)
        info "Installing via pacman..."
        sudo pacman -S --noconfirm \
            tk \
            libsecret \
            python-secretstorage \
            git \
            openssh 2>/dev/null || true
        ;;
    macos)
        info "Installing via brew..."
        brew install python-tk git openssh 2>/dev/null || true
        ;;
    *)
        warn "Unknown OS — skipping system deps. Install python3-tkinter, libsecret, git manually if needed."
        ;;
esac

success "System dependencies done"

# ── Install / update ClawTTY ──────────────────────────────────────────────────
header "Installing ClawTTY..."

if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Existing install found — updating..."
    git -C "$INSTALL_DIR" pull --ff-only origin "$CLAWTTY_VERSION"
    success "Updated to latest"
else
    info "Cloning ClawTTY..."
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone --depth 1 --branch "$CLAWTTY_VERSION" "$CLAWTTY_REPO" "$INSTALL_DIR" 2>/dev/null || \
    git clone --depth 1 "$CLAWTTY_REPO" "$INSTALL_DIR"
    success "Cloned to $INSTALL_DIR"
fi

# ── Install Python dependencies ───────────────────────────────────────────────
header "Installing Python dependencies..."

if [[ "$OS" == "macos" ]]; then
    # macOS: use --break-system-packages or venv
    if "$PYTHON" -m pip install --user \
        "customtkinter>=5.2.0" \
        "paramiko>=3.4.0" \
        "secretstorage>=3.3.0" \
        "keyring>=24.0.0" 2>/dev/null; then
        success "Python packages installed"
    else
        warn "pip install failed — trying with --break-system-packages..."
        "$PYTHON" -m pip install --user --break-system-packages \
            "customtkinter>=5.2.0" \
            "paramiko>=3.4.0" \
            "secretstorage>=3.3.0" \
            "keyring>=24.0.0"
    fi
else
    "$PYTHON" -m pip install --user \
        "customtkinter>=5.2.0" \
        "paramiko>=3.4.0" \
        "secretstorage>=3.3.0" \
        "keyring>=24.0.0" || \
    "$PYTHON" -m pip install --user --break-system-packages \
        "customtkinter>=5.2.0" \
        "paramiko>=3.4.0" \
        "secretstorage>=3.3.0" \
        "keyring>=24.0.0"
fi

success "Python dependencies installed"

# ── Create launcher ───────────────────────────────────────────────────────────
header "Creating launcher..."

mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/clawtty" << EOF
#!/usr/bin/env bash
exec $PYTHON "$INSTALL_DIR/clawtty.py" "\$@"
EOF

chmod +x "$BIN_DIR/clawtty"
success "Launcher created at $BIN_DIR/clawtty"

# ── Create .desktop entry (Linux only) ───────────────────────────────────────
if [[ "$OS" != "macos" ]]; then
    DESKTOP_DIR="$HOME/.local/share/applications"
    mkdir -p "$DESKTOP_DIR"
    cat > "$DESKTOP_DIR/clawtty.desktop" << EOF
[Desktop Entry]
Name=ClawTTY
Comment=Universal AI Agent SSH Console
Exec=$BIN_DIR/clawtty
Icon=$INSTALL_DIR/assets/icon.png
Terminal=false
Type=Application
Categories=Network;System;
Keywords=SSH;AI;Agent;OpenClaw;Hermes;
EOF
    success "Desktop entry created"
fi

# ── PATH check ────────────────────────────────────────────────────────────────
header "Checking PATH..."

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not in your PATH"
    SHELL_RC=""
    [[ -f "$HOME/.zshrc" ]]    && SHELL_RC="$HOME/.zshrc"
    [[ -f "$HOME/.bashrc" ]]   && SHELL_RC="$HOME/.bashrc"

    if [[ -n "$SHELL_RC" ]]; then
        echo "" >> "$SHELL_RC"
        echo '# ClawTTY' >> "$SHELL_RC"
        echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$SHELL_RC"
        info "Added $BIN_DIR to PATH in $SHELL_RC"
        info "Run: source $SHELL_RC"
    else
        warn "Add this to your shell rc manually:"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
else
    success "$BIN_DIR already in PATH"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}${BOLD}  ClawTTY installed successfully!${RESET}"
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  Start it:   ${CYAN}clawtty${RESET}"
echo -e "  Update:     ${CYAN}clawtty --update${RESET}  (or re-run this script)"
echo -e "  Docs:       ${CYAN}$INSTALL_DIR/README.md${RESET}"
echo ""
}

main "$@"
