# 🐧 Whisper Transcriber — Linux Guide

## Поддерживаемые дистрибутивы
Ubuntu, Debian, Fedora, Arch Linux, Manjaro, Linux Mint, openSUSE.

## Установка зависимостей

### Ubuntu / Debian:
```bash
sudo apt update
sudo apt install -y ffmpeg python3-tk python3-pip
pip3 install -r ../requirements-cuda.txt  # для карт NVIDIA
# или: pip3 install -r ../requirements.txt  # только для CPU
```

### Arch Linux / Manjaro:
```bash
sudo pacman -S ffmpeg tk python-pip
pip install -r ../requirements-cuda.txt
```

## Запуск
```bash
chmod +x linux/run.sh
./linux/run.sh
```

## Сборка бинарного файла
```bash
chmod +x linux/build_linux.sh
./linux/build_linux.sh
```
Готовый бинарник будет доступен в `dist/transcriber-linux/transcriber-linux`.

## Добавление в меню приложений
Скопируйте `transcriber.desktop` в `~/.local/share/applications/`:
```bash
cp linux/transcriber.desktop ~/.local/share/applications/
```
