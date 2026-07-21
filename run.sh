#!/bin/bash
# Enterprise AI Agent Launcher

echo "========================================================"
echo "  Enterprise AI Agent - Launcher"
echo "========================================================"
echo ""

# Check python3 installation
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not in PATH."
    echo "Please install Python 3.10+ and try again."
    exit 1
fi

# Create virtual environment if missing
if [ ! -d "venv" ]; then
    echo "[INFO] Creating virtual environment (venv)..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment."
        exit 1
    fi
fi

# Activate virtual environment and install packages
echo "[INFO] Activating virtual environment..."
source venv/bin/activate

echo "[INFO] Checking / Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install dependencies."
    exit 1
fi

# Run setup if config is missing
if [ ! -f "config/settings.json" ]; then
    echo "[INFO] Running initial setup wizard..."
    python3 setup.py
fi

# Start the application
echo ""
echo "[SUCCESS] Starting Enterprise AI Agent..."
echo "========================================================"
python3 start.py
