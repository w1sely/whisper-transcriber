# 🍏 Whisper Transcriber — macOS Guide

## Supported Hardware
* **Apple Silicon**: Mac with M1, M2, M3, M4 chips (Metal Performance Shaders / MPS hardware acceleration).
* **Intel**: Mac with Intel x86_64 processors (CPU mode).

## Setup & Dependencies

1. Install Homebrew (if not already installed):
   ```zsh
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
2. Install system packages:
   ```zsh
   brew install ffmpeg python-tk
   ```
3. Install Python dependencies:
   ```zsh
   pip3 install -r ../requirements-macos.txt
   ```

## Running the Application
* **Via Finder**: Double-click `macos/run_mac.command`.
* **Via Terminal**:
  ```zsh
  python3 app.py
  ```

## Compiling Native `.app` Bundle
```zsh
chmod +x macos/build_macos.sh
./macos/build_macos.sh
```
The output application bundle will be created at `dist/WhisperTranscriber.app`.
