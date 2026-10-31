# 🐧 Whisper Transcriber — Linux Guide

## Supported Distributions
Ubuntu, Debian, Fedora, Arch Linux, Manjaro, Linux Mint, openSUSE.

## Dependency Installation

### Ubuntu / Debian:
```bash
sudo apt update
sudo apt install -y ffmpeg python3-tk python3-pip
pip3 install -r ../requirements-cuda.txt  # for NVIDIA GPUs
# or: pip3 install -r ../requirements.txt  # CPU-only
```

### Arch Linux / Manjaro:
```bash
sudo pacman -S ffmpeg tk python-pip
pip install -r ../requirements-cuda.txt
```

## Running the Application
```bash
chmod +x linux/run.sh
./linux/run.sh
```

## Compiling Standalone Binary
```bash
chmod +x linux/build_linux.sh
./linux/build_linux.sh
```
The resulting binary will be created at `dist/transcriber-linux/transcriber-linux`.

## System Application Menu Integration
Copy `transcriber.desktop` to `~/.local/share/applications/`:
```bash
cp linux/transcriber.desktop ~/.local/share/applications/
```
