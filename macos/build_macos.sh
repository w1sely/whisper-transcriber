#!/bin/zsh
# Build script for native .app bundle on macOS (Intel / Apple Silicon M1-M4)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR" || exit 1

echo "===================================================="
echo " Building Whisper Transcriber for macOS (.app Bundle)"
echo "===================================================="

pip3 install pyinstaller
pyinstaller --noconfirm --onedir --windowed --name "WhisperTranscriber" --collect-all whisper --collect-all yt_dlp src/app.py

if [ -d "dist/WhisperTranscriber.app" ]; then
    echo ""
    echo "[SUCCESS] macOS Application Bundle built: dist/WhisperTranscriber.app"
else
    echo ""
    echo "[ERROR] Application build failed."
fi
