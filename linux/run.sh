#!/usr/bin/env bash
# Launch script for Linux

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR" || exit 1

# Check Python 3
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python 3 was not found on your system."
    exit 1
fi

echo "Starting Whisper Transcriber on Linux..."
exec $PYTHON_CMD src/app.py "$@"
