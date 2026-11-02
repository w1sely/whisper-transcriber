#!/usr/bin/env bash
# Build script for Linux standalone executable (ELF binary)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR" || exit 1

echo "===================================================="
echo " Building Whisper Transcriber for Linux (ELF)"
echo "===================================================="

pip3 install pyinstaller
pyinstaller --noconfirm --onedir --windowed --name "transcriber-linux" --collect-all whisper --collect-all yt_dlp src/app.py

if [ -f "dist/transcriber-linux/transcriber-linux" ]; then
    echo ""
    echo "[SUCCESS] Binary successfully built: dist/transcriber-linux/transcriber-linux"
    chmod +x dist/transcriber-linux/transcriber-linux
else
    echo ""
    echo "[ERROR] Build failed."
fi
