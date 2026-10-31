# 🪟 Whisper Transcriber — Windows Guide

## Quick Start
* **Pre-compiled `.exe`**: Launch `dist\Transcriber\Transcriber.exe` or the root `Transcriber.lnk` shortcut.
* **From Command Line**: Execute `windows\run.bat` or `python app.py`.

## System Requirements
* Windows 10 or 11 (64-bit).
* NVIDIA GPU (GeForce RTX 20/30/40/50 series) for CUDA acceleration (CPU fallback is supported).
* FFmpeg: Install via `winget install Gyan.FFmpeg`.

## Compiling `.exe`
To recompile the standalone Windows executable, run:
```cmd
windows\build_exe.bat
```
The output will be placed in `dist\Transcriber\Transcriber.exe`.
