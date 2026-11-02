# 🎙️ Whisper Transcriber

<p align="center">
  <strong>High-performance, cross-platform desktop application for local AI audio transcription with silence trimming and hardware acceleration.</strong>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?logo=python&logoColor=white" alt="Python Versions"></a>
  <a href="https://github.com/w1sely/whisper-transcriber/releases"><img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-success" alt="Platforms"></a>
  <a href="https://developer.nvidia.com/cuda"><img src="https://img.shields.io/badge/Hardware%20Accel-NVIDIA%20CUDA%20%7C%20Apple%20Silicon%20MPS-orange" alt="Hardware Acceleration"></a>
  <a href="https://github.com/openai/whisper"><img src="https://img.shields.io/badge/Engine-OpenAI%20Whisper-412991?logo=openai&logoColor=white" alt="Whisper"></a>
  <a href="https://ffmpeg.org/"><img src="https://img.shields.io/badge/Audio%20Processing-FFmpeg-007808?logo=ffmpeg&logoColor=white" alt="FFmpeg"></a>
  <a href="https://github.com/yt-dlp/yt-dlp"><img src="https://img.shields.io/badge/URL%20Downloader-yt--dlp-FF0000?logo=youtube&logoColor=white" alt="yt-dlp"></a>
  <a href="https://github.com/w1sely/whisper-transcriber/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-All%20Rights%20Reserved-red" alt="License"></a>
</p>

---

## 📖 Overview

**Whisper Transcriber** is a secure, standalone desktop application engineered for fast, offline speech-to-text transcription. It pairs **OpenAI Whisper** with **FFmpeg** audio preprocessing and **yt-dlp** media downloading, offering full hardware acceleration across **NVIDIA GPUs (CUDA with TF32)**, **Apple Silicon chips (Metal MPS)**, and a resilient **CPU fallback**.

Transcribe local audio files (`.mp3`, `.wav`, `.m4a`, etc.) or paste media links directly from **VK Video, YouTube, Rutube, Vimeo, SoundCloud**, and 1700+ websites. All Whisper inference runs entirely on your local machine.

---

## 📥 Releases & Installers

Pre-built binaries and standalone distribution packages:

| Platform | Package Format | Download / Run Link | Hardware Acceleration | Compatibility |
| :--- | :--- | :--- | :--- | :--- |
| **🪟 Windows** | Portable Archive (`.zip` with `Transcriber.exe`) | [**⬇️ Download for Windows (x64)**](https://github.com/w1sely/whisper-transcriber/releases/latest/download/Transcriber-Windows-x64.zip)<br>*(Extract and launch `Transcriber.exe`)* | NVIDIA CUDA (RTX / GTX) + CPU | Windows 10, 11 (64-bit) |
| **🐧 Linux** | Run Script (`linux/run.sh`) & Build Script | [**🚀 Linux Launcher & Setup Guide**](https://github.com/w1sely/whisper-transcriber/tree/main/linux)<br>*(Run: `chmod +x linux/run.sh && ./linux/run.sh`)* | NVIDIA CUDA / ROCm / CPU | Ubuntu, Debian, Fedora, Arch Linux |
| **🍏 macOS** | Finder Launcher (`.command`) & Build Script | [**🚀 macOS Launcher & Setup Guide**](https://github.com/w1sely/whisper-transcriber/tree/main/macos)<br>*(Launch: double-click `macos/run_mac.command`)* | Apple Silicon (M1/M2/M3/M4 Metal MPS) | macOS 12.0+ (Monterey, Ventura, Sonoma, Sequoia) |

---

## 🎯 How to Get Started (Choose Your OS)

### 🪟 Case 1: Windows (Easiest — Standalone `.exe`)

> **No Python or complex setup required!**

1. **Download the archive**: Click [**⬇️ Download for Windows (x64)**](https://github.com/w1sely/whisper-transcriber/releases/latest/download/Transcriber-Windows-x64.zip).
2. **Extract**: Unpack `Transcriber-Windows-x64.zip` to any folder on your computer.
3. **Run**: Double-click `Transcriber.exe` (or `Transcriber.lnk`).
4. **Done!** The app automatically detects your NVIDIA GPU (CUDA) and is immediately ready to transcribe.

*(Alternative for developers who prefer running from source)*:
```cmd
git clone https://github.com/w1sely/whisper-transcriber.git
cd whisper-transcriber
pip install -r requirements-cuda.txt
windows\run.bat
```

---

### 🐧 Case 2: Linux (Ubuntu, Debian, Fedora, Arch Linux)

1. **Install FFmpeg and Python Tkinter**:
   ```bash
   # Ubuntu / Debian / Linux Mint:
   sudo apt update && sudo apt install -y ffmpeg python3-tk python3-pip

   # Arch Linux / Manjaro:
   sudo pacman -S ffmpeg tk python-pip

   # Fedora / RHEL:
   sudo dnf install -y ffmpeg python3-tkinter python3-pip
   ```
2. **Clone the repository & install Python packages**:
   ```bash
   git clone https://github.com/w1sely/whisper-transcriber.git
   cd whisper-transcriber

   # For NVIDIA GPUs (CUDA):
   pip3 install -r requirements-cuda.txt

   # For CPU-only or AMD:
   pip3 install -r requirements.txt
   ```
3. **Launch the application**:
   ```bash
   chmod +x linux/run.sh && ./linux/run.sh
   ```
   *Tip: To build an offline single-file executable for Linux, run `chmod +x linux/build_linux.sh && ./linux/build_linux.sh`.*

---

### 🍏 Case 3: macOS (Apple Silicon M1-M4 & Intel)

1. **Install FFmpeg via Homebrew**:
   ```zsh
   brew install ffmpeg python-tk
   ```
2. **Clone the repository & install dependencies**:
   ```zsh
   git clone https://github.com/w1sely/whisper-transcriber.git
   cd whisper-transcriber
   pip3 install -r requirements-macos.txt
   ```
3. **Launch in 1 Click**:
   Simply **double-click `macos/run_mac.command`** in Finder!
   * The app will automatically initialize Apple Silicon Metal Performance Shaders (MPS) on M1/M2/M3/M4 chips for fast hardware-accelerated transcription.
   * *(Optional)* To compile a native macOS `.app` bundle: `chmod +x macos/build_macos.sh && ./macos/build_macos.sh`.

---

## ✨ Key Features

* **⚡ Native Hardware Acceleration**:
  * **Windows & Linux**: NVIDIA CUDA with TensorFloat-32 (TF32) tensor core acceleration.
  * **macOS**: Apple Silicon Metal Performance Shaders (MPS) for M1/M2/M3/M4 processors.
  * **CPU Fallback**: Automatic, graceful downgrade to CPU inference if an accelerator is missing or runs out of memory.
* **🌐 Direct URL Media Downloading (yt-dlp)**:
  * Seamless audio extraction from web video/audio links (VK Video, YouTube, Rutube, Vimeo, SoundCloud, and 1700+ websites).
  * Automatically converts downloaded streams to 192 kbps MP3 via FFmpeg with real-time download speed, percentage, and ETA tracking.
  * Automated title sanitization and seamless 1-click download & transcribe workflow.
* **🔇 Silence Removal & Audio Normalization**:
  * Integrated FFmpeg pipeline (`silenceremove`) strips silent pauses and converts input into 16 kHz mono before model inference.
  * Significantly reduces hallucination rates and accelerates total processing time.
* **🧠 Smart Model Management**:
  * Real-time local cache inspection (`~/.cache/whisper`).
  * Live model status tags: `[✓ Cached]` or `[⬇ Download Required]`.
  * Visual network download progress indicator (reporting MB and percentage) directly in the GUI.
* **🛡️ Security & Fault Tolerance**:
  * **Path Traversal Protection**: Strict filename sanitization via `os.path.basename` prevents unauthorized filesystem navigation.
  * **Atomic File Writes**: Transcripts are written to temporary buffers before atomic file replacement, guaranteeing zero corrupted files upon power loss.
  * **VRAM Leak Prevention**: Explicit memory release (`torch.cuda.empty_cache()` / `torch.mps.empty_cache()`) during model switches prevents CUDA Out of Memory (OOM) errors.
* **💻 Clean, Non-Blocking Interface**:
  * Interactive dark mode GUI with minimize, maximize, and clean exit.
  * Real-time segment transcription streaming directly into the GUI console.
  * Single-click actions to open output directories, view generated `.txt` files, or copy transcripts to the clipboard.

---

## 📂 Repository Architecture

```text
whisper-transcriber/
├── src/                          # Universal cross-platform application core
│   └── app.py                    # Main GUI implementation (Tkinter + PyTorch + Whisper)
│
├── windows/                      # Windows platform bundle
│   ├── run.bat                   # Double-click launcher
│   ├── build_exe.bat             # Standalone Transcriber.exe build script
│   └── README_WINDOWS.md         # Windows configuration guide
│
├── linux/                        # Linux platform bundle
│   ├── run.sh                    # Shell launcher script
│   ├── build_linux.sh            # ELF binary compilation script
│   ├── transcriber.desktop       # Desktop entry for system application menus
│   └── README_LINUX.md           # Ubuntu/Debian/Arch configuration guide
│
├── macos/                        # macOS platform bundle
│   ├── run_mac.command           # Double-click Finder launcher
│   ├── build_macos.sh            # Native .app bundle compilation script
│   └── README_MACOS.md           # Apple Silicon MPS configuration guide
│
├── tests/                        # Comprehensive automated test suite
│   ├── test_cross_platform.py    # Path security, FFmpeg, VRAM & transcription tests
│   ├── test_all_platforms.py     # CPU fallback, POSIX line endings & failure recovery
│   └── test_url_downloader.py    # yt-dlp URL downloading, sanitization & network tests
│
├── dist/                         # Distribution build artifacts
│   └── Transcriber/Transcriber.exe
│
├── app.py                        # Root universal entry point
├── requirements.txt              # Standard base dependencies
├── requirements-cuda.txt         # Dependencies with NVIDIA CUDA wheel index
├── requirements-macos.txt        # Dependencies tailored for Apple Silicon Metal
├── .gitattributes                # Enforces POSIX LF line endings for scripts
├── .gitignore                    # Production Git ignore filters
└── LICENSE                       # Proprietary copyright notice
```

---


## 📊 Supported Models

| Model Key | Parameters | VRAM Required | English / Multilingual | Relative Speed | Recommended Use Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`turbo`** *(Default)* | 809 M | ~1.5 GB | Multilingual | **~8x** | **Recommended**: High accuracy with ultra-fast inference |
| **`large-v3`** | 1550 M | ~3.0 GB | Multilingual | ~1x | Maximum precision for complex terminology and accents |
| **`medium`** | 769 M | ~1.5 GB | Multilingual | ~2x | Balanced resource usage for mid-tier GPUs |
| **`small`** | 244 M | ~500 MB | Multilingual | ~4x | Fast processing on low-VRAM GPUs or lightweight setups |
| **`base`** | 74 M | ~150 MB | Multilingual | ~16x | Lightweight, efficient speech recognition |
| **`tiny`** | 39 M | ~80 MB | Multilingual | ~32x | Ultra-lightweight CPU-friendly transcription |

---

## 🧪 Automated Testing & Verification

The test suite validates hardware accelerators, memory cleanup, and security guarantees:

```bash
# Run cross-platform core tests
python tests/test_cross_platform.py

# Run CPU fallback, POSIX line endings, and error handling tests
python tests/test_all_platforms.py

# Run URL downloader, yt-dlp integration, and exception tests
python tests/test_url_downloader.py
```

### Coverage Highlights:
* `test_01_security_path_traversal`: Confirms that malicious input paths (e.g. `../../etc/passwd`) are neutralized.
* `test_02_ffmpeg_preprocessing`: Validates 16 kHz mono conversion and silence removal.
* `test_03_hardware_acceleration`: Confirms proper CUDA / MPS device initialization and zero memory leaks upon model unloading.
* `test_04_transcription_and_atomic_write`: Verifies end-to-end inference and atomic `.txt` and `.json` file generation.
* `test_05_posix_line_endings`: Verifies all Linux and macOS scripts strictly adhere to POSIX LF line endings.
* `test_url_downloader`: Validates yt-dlp URL validation, playlist safety (noplaylist), web title sanitization, and graceful failure on unreachable links.

---

## 📄 License & Intellectual Property

**Copyright (c) 2026 w1sely. All Rights Reserved.**

This software and associated documentation files are proprietary. Unauthorized copying, distribution, modification, public display, or reverse engineering of this source code or binary distribution is strictly prohibited without prior written permission from the author.
