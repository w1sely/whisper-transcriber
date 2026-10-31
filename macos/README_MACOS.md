# 🍏 Whisper Transcriber — macOS Guide

## Поддерживаемые устройства
* **Apple Silicon:** Mac на базе M1, M2, M3, M4 (аппаратное ускорение Metal Performance Shaders / MPS).
* **Intel:** Mac на базе процессоров Intel x86_64 (CPU-режим).

## Установка зависимостей

1. Установите Homebrew (если еще не установлен):
   ```zsh
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
2. Установите системные библиотеки:
   ```zsh
   brew install ffmpeg python-tk
   ```
3. Установите зависимости Python:
   ```zsh
   pip3 install -r ../requirements-macos.txt
   ```

## Запуск
* **Через Finder:** дважды кликните по файлу `macos/run_mac.command`.
* **Через Терминал:**
  ```zsh
  python3 app.py
  ```

## Сборка нативного .app бандла
```zsh
chmod +x macos/build_macos.sh
./macos/build_macos.sh
```
Готовое приложение будет создано в `dist/WhisperTranscriber.app`.
