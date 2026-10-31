#!/bin/zsh
# macOS Launcher - double-click to launch in Finder

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR" || exit 1

echo "===================================================="
echo " Starting Whisper Transcriber on macOS"
echo "===================================================="

# Check Python3
if command -v python3 &>/dev/null; then
    python3 src/app.py
elif command -v python &>/dev/null; then
    python src/app.py
else
    echo "Error: Python 3 was not found. Please install Python via Homebrew or python.org"
    read -p "Press Enter to exit..."
fi
