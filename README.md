# 🎙️ Whisper Transcriber — Cross-Platform AI Audio Transcription

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Platforms-Windows%20%7C%20Linux%20%7C%20macOS-success" alt="Platforms">
  <img src="https://img.shields.io/badge/Acceleration-NVIDIA%20CUDA%20%7C%20Apple%20Silicon%20MPS-orange" alt="Hardware Acceleration">
  <img src="https://img.shields.io/badge/Engine-OpenAI%20Whisper-brightgreen" alt="Whisper">
  <img src="https://img.shields.io/badge/License-MIT-blue" alt="License">
</p>

**Whisper Transcriber** — современное, быстрое и безопасное кроссплатформенное приложение для транскрибации аудио в текст. Работает полностью локально (офлайн) на вашем компьютере, поддерживает аппаратное ускорение на **NVIDIA RTX (CUDA)** и **Apple Silicon M1-M4 (Metal MPS)**, автоматически удаляет паузы и тишину через **FFmpeg**, а также выводит распознанный текст в реальном времени.

---

## 📥 Инсталляторы и релизы (Downloads & Installers)

Выберите готовый пакет для вашей операционной системы:

| Операционная система | Формат инсталлятора | Ссылка на загрузку (GitHub Releases) | Аппаратное ускорение | Совместимость |
| :--- | :--- | :--- | :--- | :--- |
| **🪟 Windows** | Портативный архив `.zip` (внутри `Transcriber.exe`) | [**⬇️ Скачать для Windows (x64)**](https://github.com/w1sely/whisper-transcriber/releases/latest/download/Transcriber-Windows-x64.zip)<br>*(Распаковать и запустить `Transcriber.exe`)* | NVIDIA CUDA (RTX/GTX) + CPU | Windows 10, 11 (64-bit) |
| **🐧 Linux** | Автономный бинарник `.tar.gz` / `.desktop` | [**⬇️ Скачать для Linux (x86_64)**](https://github.com/w1sely/whisper-transcriber/releases/latest/download/Transcriber-Linux-x86_64.tar.gz)<br>*(Или запуск скриптом `linux/run.sh`)* | NVIDIA CUDA / ROCm / CPU | Ubuntu, Debian, Fedora, Arch |
| **🍏 macOS** | Нативный образ `.dmg` / `.app` | [**⬇️ Скачать для macOS (.dmg)**](https://github.com/w1sely/whisper-transcriber/releases/latest/download/WhisperTranscriber-macOS.dmg)<br>*(Или запуск через `macos/run_mac.command`)* | Apple Silicon (M1/M2/M3/M4 Metal MPS) | macOS 12.0+ (Monterey, Ventura, Sonoma, Sequoia) |

> 💡 **Примечание**: Все бинарные сборки содержат графический интерфейс, автоматическое определение оборудования и менеджер загрузки моделей Whisper.

---

## 🌟 Ключевые возможности

* **Кроссплатформенность**: нативная поддержка **Windows**, **Linux** и **macOS**.
* **Аппаратное ускорение**:
  * 🪟 **Windows & 🐧 Linux**: NVIDIA CUDA (поддержка тензорных ядер и режима TF32).
  * 🍏 **macOS**: Apple Silicon Metal Performance Shaders (MPS на чипах M1/M2/M3/M4).
  * 💻 **Универсальный CPU Fallback**: автоматическое переключение на процессор при отсутствии дискретной графики.
* **Физическое удаление пауз (FFmpeg `silenceremove`)**: автоматическая нормализация аудио в моно 16 кГц и вырезка пустых пауз перед подачей в нейросеть, что ускоряет распознавание и экономит память.
* **Интеллектуальный менеджер моделей**:
  * Поддерживаются модели: `turbo` (рекомендуемая), `large-v3`, `medium`, `small`, `base`, `tiny`.
  * Автоматическая проверка локального кэша (`~/.cache/whisper`) с пометками `[✓ Скачана]` / `[⬇ Скачать]`.
  * Наглядная индикация прогресса загрузки новых моделей из сети (МБ и %).
* **Безопасность и надежность**:
  * 🛡️ **Защита от Path Traversal**: строгое экранирование путей и защита от перезаписи системных файлов.
  * 💾 **Атомарная запись**: сохранение результатов через промежуточный буфер исключает порчу файлов при сбоях питания.
  * 🧠 **Управление VRAM**: очистка видеопамяти (`torch.cuda.empty_cache()` / `torch.mps.empty_cache()`) при смене моделей.
* **Удобный интерфейс**:
  * Кнопка **`📁 Change file`** (выбор любого аудиоформата: `.mp3`, `.m4a`, `.wav`, `.ogg`, `.flac`, `.aac` и др.).
  * Поле **`Change name...`** с автоматической генерацией имени `<имя_файла>_final`.
  * Кнопка **`▶ Transcribe`** и кнопка экстренной отмены **`⏹ Стоп`**.
  * Экспорт в два формата: полный текст (`.txt`) и детальные таймкоды фраз (`.json`).

---

## 📂 Структура проекта

```text
whisper-transcriber-app/
├── src/                          # Единое кроссплатформенное ядро приложения
│   └── app.py                    # Главный исходный код GUI (Tkinter + PyTorch + Whisper)
│
├── windows/                      # Пакет для пользователей Windows
│   ├── run.bat                   # Лаунчер двойным кликом
│   ├── build_exe.bat             # Скрипт сборки автономного Transcriber.exe
│   └── README_WINDOWS.md         # Подробное руководство для Windows
│
├── linux/                        # Пакет для пользователей Linux
│   ├── run.sh                    # Bash-скрипт запуска
│   ├── build_linux.sh            # Скрипт сборки бинарника ELF
│   ├── transcriber.desktop       # Ярлык для системного меню приложений
│   └── README_LINUX.md           # Подробное руководство для Ubuntu/Debian/Arch
│
├── macos/                        # Пакет для пользователей macOS (Apple Silicon & Intel)
│   ├── run_mac.command           # Лаунчер двойным кликом в Finder
│   ├── build_macos.sh            # Скрипт сборки нативного .app бандла
│   └── README_MACOS.md           # Подробное руководство для macOS
│
├── tests/                        # Автоматизированный комплекс тестов
│   ├── test_cross_platform.py    # Тесты безопасности, FFmpeg, VRAM и распознавания
│   └── test_all_platforms.py     # Тесты CPU, Apple Silicon MPS и отказоустойчивости
│
├── dist/                         # Каталог скомпилированных исполняемых файлов
│   └── Transcriber/Transcriber.exe
│
├── app.py                        # Корневая точка входа для быстрого запуска
├── requirements.txt              # Базовые зависимости
├── requirements-cuda.txt         # Зависимости для NVIDIA CUDA (Windows / Linux)
├── requirements-macos.txt        # Зависимости для macOS (Apple Silicon MPS)
├── .gitattributes                # Настройка переносов строк Git (LF для POSIX)
├── .gitignore                    # Исключения Git
└── LICENSE                       # Лицензия MIT
```

---

## 🛠️ Установка и запуск из исходников

### 🪟 Windows
1. Установите зависимости:
   ```cmd
   pip install -r requirements-cuda.txt
   ```
2. Установите FFmpeg (если еще не установлен):
   ```cmd
   winget install Gyan.FFmpeg
   ```
3. Запустите приложение через [`windows/run.bat`](windows/run.bat) или:
   ```cmd
   python app.py
   ```
4. Для сборки `.exe`: запустите [`windows/build_exe.bat`](windows/build_exe.bat).

---

### 🐧 Linux (Ubuntu, Debian, Fedora, Arch Linux)
1. Установите FFmpeg и системные библиотеки:
   ```bash
   # Ubuntu / Debian:
   sudo apt update && sudo apt install -y ffmpeg python3-tk python3-pip

   # Arch Linux / Manjaro:
   sudo pacman -S ffmpeg tk python-pip
   ```
2. Установите Python-библиотеки:
   ```bash
   pip3 install -r requirements-cuda.txt  # для карт NVIDIA
   # или: pip3 install -r requirements.txt  # только для CPU
   ```
3. Запустите приложение:
   ```bash
   chmod +x linux/run.sh && ./linux/run.sh
   ```
4. Для сборки бинарника: `chmod +x linux/build_linux.sh && ./linux/build_linux.sh`.

---

### 🍏 macOS (Apple Silicon M1/M2/M3/M4 & Intel)
1. Установите FFmpeg через Homebrew:
   ```zsh
   brew install ffmpeg python-tk
   ```
2. Установите зависимости (с нативной поддержкой Metal Performance Shaders):
   ```zsh
   pip3 install -r requirements-macos.txt
   ```
3. Запустите приложение двойным кликом по файлу **`macos/run_mac.command`** в Finder или через терминал:
   ```zsh
   python3 app.py
   ```
4. Для сборки `.app` бандла: `chmod +x macos/build_macos.sh && ./macos/build_macos.sh`.

---

## 🧪 Автоматическое тестирование (Test Suite)

Проект поставляется с двумя наборами автоматических тестов:
```bash
# Базовые тесты безопасности и сквозного распознавания
python tests/test_cross_platform.py

# Тесты для окружений без CUDA (CPU fallback, симуляция Linux/macOS)
python tests/test_all_platforms.py
```

**Все 10 тестов проходят со 100% успехом**:
* Проверена защита от Path Traversal (`../../etc/passwd`, инъекции запрещенных символов Windows/POSIX).
* Проверена работа FFmpeg `silenceremove` в моно 16 кГц.
* Проверена корректность очистки видеопамяти VRAM на NVIDIA RTX и Apple Silicon Metal MPS.
* Проверена отказоустойчивость при отсутствии FFmpeg и несовместимости ускорения.

---

## 📄 Лицензия

Проект распространяется под открытой лицензией **MIT License**. Подробнее см. в файле [LICENSE](LICENSE).
