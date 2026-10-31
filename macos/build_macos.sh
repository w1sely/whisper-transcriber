#!/bin/zsh
# Сборка нативного .app бандла для macOS (Intel / Apple Silicon M1-M4)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR" || exit 1

echo "===================================================="
echo " Сборка Whisper Transcriber для macOS (.app Bundle)"
echo "===================================================="

pip3 install pyinstaller
pyinstaller --noconfirm --onedir --windowed --name "WhisperTranscriber" --collect-all whisper src/app.py

if [ -d "dist/WhisperTranscriber.app" ]; then
    echo ""
    echo "[УСПЕХ] macOS Application Bundle собран: dist/WhisperTranscriber.app"
else
    echo ""
    echo "[ОШИБКА] Сборка приложения завершилась с ошибкой."
fi
