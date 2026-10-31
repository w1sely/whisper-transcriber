#!/usr/bin/env bash
# Скрипт запуска для Linux

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR" || exit 1

# Проверка Python 3
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "Ошибка: Python 3 не найден в системе."
    exit 1
fi

echo "Запуск Whisper Transcriber на Linux..."
exec $PYTHON_CMD src/app.py "$@"
