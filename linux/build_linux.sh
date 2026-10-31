#!/usr/bin/env bash
# Скрипт сборки исполняемого файла для Linux (ELF binary)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR" || exit 1

echo "===================================================="
echo " Сборка Whisper Transcriber для Linux (ELF)"
echo "===================================================="

pip3 install pyinstaller
pyinstaller --noconfirm --onedir --windowed --name "transcriber-linux" --collect-all whisper src/app.py

if [ -f "dist/transcriber-linux/transcriber-linux" ]; then
    echo ""
    echo "[УСПЕХ] Бинарный файл собран: dist/transcriber-linux/transcriber-linux"
    chmod +x dist/transcriber-linux/transcriber-linux
else
    echo ""
    echo "[ОШИБКА] Сборка завершилась с ошибкой."
fi
