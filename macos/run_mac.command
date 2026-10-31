#!/bin/zsh
# macOS Launcher - запуск двойным кликом в Finder

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR" || exit 1

echo "===================================================="
echo " Запуск Whisper Transcriber на macOS"
echo "===================================================="

# Проверка Python3
if command -v python3 &>/dev/null; then
    python3 src/app.py
elif command -v python &>/dev/null; then
    python src/app.py
else
    echo "Ошибка: Python 3 не обнаружен. Установите Python через Homebrew или python.org"
    read -p "Нажмите Enter для выхода..."
fi
