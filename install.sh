#!/usr/bin/env bash
# ============================================================
#  Enterprise AI Agent — One-Click Installer (Linux / macOS)
#  Supports: Ubuntu, Debian, Fedora, macOS, WSL
# ============================================================
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Enterprise AI Agent — One-Click Installer (Linux/Mac) ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# --- 1. Check Python >= 3.11 ---
echo -e "${BOLD}[1/4] Checking Python installation...${NC}"

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "  ${RED}✗ Python not found!${NC}"
    echo "    Install Python 3.11+ from https://python.org or your package manager:"
    echo "      Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "      Fedora:        sudo dnf install python3 python3-pip"
    echo "      macOS:         brew install python@3.12"
    exit 1
fi

PYVER=$("$PYTHON" --version 2>&1 | awk '{print $2}')
echo -e "  ${GREEN}✓${NC} Python $PYVER found"

# Check version >= 3.11
PY_MAJOR=$(echo "$PYVER" | cut -d. -f1)
PY_MINOR=$(echo "$PYVER" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    echo -e "  ${RED}✗ Python 3.11+ required! You have $PYVER${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Python version OK"

# --- 2. Create/activate venv ---
echo ""
echo -e "${BOLD}[2/4] Setting up virtual environment...${NC}"

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$ROOT_DIR/venv"

if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "  Creating venv..."
    "$PYTHON" -m venv "$VENV_DIR" || {
        echo -e "  ${RED}✗ Failed to create virtual environment${NC}"
        echo "    Make sure python3-venv is installed:"
        echo "      Ubuntu/Debian: sudo apt install python3-venv"
        exit 1
    }
    echo -e "  ${GREEN}✓${NC} venv created"
else
    echo -e "  ${GREEN}✓${NC} venv already exists"
fi

# Activate venv
source "$VENV_DIR/bin/activate"
echo -e "  ${GREEN}✓${NC} venv activated"

# --- 3. Install requirements ---
echo ""
echo -e "${BOLD}[3/4] Installing dependencies...${NC}"
pip install --upgrade pip -q
pip install -r "$ROOT_DIR/requirements.txt" || {
    echo -e "  ${RED}✗ Failed to install dependencies${NC}"
    exit 1
}
echo -e "  ${GREEN}✓${NC} Dependencies installed"

# --- 4. Run setup.py ---
echo ""
echo -e "${BOLD}[4/4] Running setup wizard...${NC}"
python "$ROOT_DIR/setup.py" || {
    echo -e "  ${YELLOW}! Setup wizard exited with an error (code: $?)${NC}"
    echo "    You can run it again manually: python setup.py"
}

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    INSTALL COMPLETE!                     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Start the platform:"
echo "    source venv/bin/activate"
echo "    python start.py"
echo ""
echo "  Dashboard:  http://localhost:8000"
echo "  API Docs:   http://localhost:8000/docs"
echo ""
