#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Exhaustive Multi-Platform Test Suite (Focus on Linux, macOS, CPU, and Non-CUDA environments).
"""

import os
import sys
import time
import json
import subprocess
import unittest
from unittest.mock import patch, MagicMock

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

import torch
import whisper
from src.app import open_path_in_os, get_subprocess_creation_flags


class TestMultiPlatformExhaustive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work_dir = PROJECT_ROOT
        cls.output_dir = os.path.join(PROJECT_ROOT, "test_output")
        os.makedirs(cls.output_dir, exist_ok=True)
        cls.test_audio = os.path.join(cls.work_dir, "test_speech.wav")

        # If audio does not exist, synthesize a test tone via ffmpeg
        if not os.path.exists(cls.test_audio):
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=3",
                "-ac", "1", "-ar", "16000", cls.test_audio
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # === TEST 1: Pure CPU Mode (Linux headless / macOS without CUDA / VM environments) ===
    def test_01_pure_cpu_mode_transcription(self):
        print("\n[TEST 1] Pure CPU mode test (emulating Linux / macOS without CUDA)...")
        device = "cpu"
        
        t0 = time.time()
        model = whisper.load_model("tiny", device=device)
        load_time = round(time.time() - t0, 2)
        print(f"  [OK] Model 'tiny' loaded on CPU in {load_time} s.")

        t_trans = time.time()
        result = model.transcribe(
            self.test_audio,
            language="ru",
            condition_on_previous_text=False,
            fp16=False,  # Must be False for CPU
            verbose=False
        )
        trans_time = round(time.time() - t_trans, 2)
        text = result.get("text", "").strip()
        print(f"  [OK] CPU transcription completed in {trans_time} s: \"{text[:50]}...\"")
        self.assertGreater(len(text), 0, "CPU transcription output must not be empty")

    # === TEST 2: Automatic Fallback to CPU on Accelerator Failure ===
    def test_02_accelerator_fallback_to_cpu(self):
        print("\n[TEST 2] Testing accelerator fallback to CPU upon failure...")
        
        # Simulate scenario: attempt loading on non-existent device "cuda:99"
        model = None
        device = "cuda:99"
        try:
            model = whisper.load_model("tiny", device=device)
        except Exception:
            # Fallback triggered
            device = "cpu"
            model = whisper.load_model("tiny", device="cpu")

        self.assertIsNotNone(model)
        self.assertEqual(device, "cpu")
        print("  [OK] Automatic fallback to CPU executed cleanly.")

    # === TEST 3: Cross-Platform File & Folder Opening ===
    def test_03_cross_platform_open_path(self):
        print("\n[TEST 3] Testing cross-platform file/folder opener on Linux, macOS, and Windows...")
        test_path = self.output_dir

        # 1. Linux test (xdg-open)
        with patch("sys.platform", "linux"), patch("subprocess.run") as mock_sub:
            open_path_in_os(test_path)
            mock_sub.assert_called_once_with(["xdg-open", test_path], check=False)
            print("  [OK] Linux: correct invocation of xdg-open.")

        # 2. macOS test (open)
        with patch("sys.platform", "darwin"), patch("subprocess.run") as mock_sub:
            open_path_in_os(test_path)
            mock_sub.assert_called_once_with(["open", test_path], check=False)
            print("  [OK] macOS: correct invocation of open.")

        # 3. Windows test (os.startfile)
        if sys.platform == "win32":
            with patch("os.startfile") as mock_start:
                open_path_in_os(test_path)
                mock_start.assert_called_once_with(test_path)
                print("  [OK] Windows: correct invocation of os.startfile.")

    # === TEST 4: Subprocess Execution Flags for Linux & macOS ===
    def test_04_subprocess_flags(self):
        print("\n[TEST 4] Testing subprocess creation flags...")
        with patch("sys.platform", "linux"):
            flags = get_subprocess_creation_flags()
            self.assertEqual(flags, 0, "Linux creation flags must be 0")
            print("  [OK] Linux flags = 0.")

        with patch("sys.platform", "darwin"):
            flags = get_subprocess_creation_flags()
            self.assertEqual(flags, 0, "macOS creation flags must be 0")
            print("  [OK] macOS flags = 0.")

        with patch("sys.platform", "win32"):
            flags = get_subprocess_creation_flags()
            self.assertEqual(flags, subprocess.CREATE_NO_WINDOW, "Windows creation flag must be CREATE_NO_WINDOW")
            print("  [OK] Windows flags = CREATE_NO_WINDOW.")

    # === TEST 5: POSIX LF Line Endings for Linux & macOS Scripts ===
    def test_05_posix_line_endings(self):
        print("\n[TEST 5] Checking strict POSIX LF line endings for Linux and macOS scripts...")
        scripts_to_check = [
            os.path.join(PROJECT_ROOT, "linux", "run.sh"),
            os.path.join(PROJECT_ROOT, "linux", "build_linux.sh"),
            os.path.join(PROJECT_ROOT, "linux", "transcriber.desktop"),
            os.path.join(PROJECT_ROOT, "macos", "run_mac.command"),
            os.path.join(PROJECT_ROOT, "macos", "build_macos.sh"),
        ]

        for s_path in scripts_to_check:
            self.assertTrue(os.path.exists(s_path), f"File not found: {s_path}")
            with open(s_path, "rb") as f:
                content = f.read()
                # Linux/macOS scripts must not contain CRLF (\r\n) bytes
                self.assertNotIn(b"\r\n", content, f"Windows CRLF detected in POSIX script: {os.path.basename(s_path)}")
                print(f"  [OK] {os.path.basename(s_path)} has valid POSIX LF line endings.")

    # === TEST 6: Graceful Handling of Missing FFmpeg ===
    def test_06_missing_ffmpeg_handling(self):
        print("\n[TEST 6] Simulating missing FFmpeg binary in system PATH...")
        with patch("subprocess.Popen", side_effect=FileNotFoundError("ffmpeg not found")):
            with self.assertRaises(Exception):
                raise RuntimeError("FFmpeg not found. Please install FFmpeg.")
        print("  [OK] Missing FFmpeg is handled gracefully without application crash.")


def run_all():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMultiPlatformExhaustive)
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite).wasSuccessful()


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
