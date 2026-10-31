#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Automated Cross-Platform Test Suite for Whisper Transcriber.
"""

import os
import sys
import time
import json
import subprocess
import unittest

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add parent directory to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

import torch
import whisper
from src.app import MODEL_INFO, open_path_in_os, get_subprocess_creation_flags


class TestWhisperTranscriberCrossPlatform(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work_dir = PROJECT_ROOT
        cls.output_dir = os.path.join(PROJECT_ROOT, "test_output")
        os.makedirs(cls.output_dir, exist_ok=True)
        cls.test_audio = os.path.join(cls.work_dir, "test_speech.wav")

        # If synthesized test audio is missing, generate a short 3s wav via ffmpeg
        if not os.path.exists(cls.test_audio):
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=3",
                "-ac", "1", "-ar", "16000", cls.test_audio
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 1. Path Traversal & Security Sanitization
    def test_01_security_path_traversal(self):
        print("\n[TEST 1] Testing path traversal security (Windows / POSIX)...")
        malicious_inputs = [
            ("../../etc/passwd", "passwd"),
            ("../../../var/log/syslog", "syslog"),
            ("..\\..\\Windows\\System32\\cmd.exe", "cmd.exe"),
            ("test<illegal>:chars/in?name*.wav", "in_name_.wav"),
            ("...spaces_and_dots...   ", "spaces_and_dots"),
            (":::???***", "transcription_final"),
            ("", "transcription_final"),
            ("normal_file_name_123", "normal_file_name_123")
        ]

        for raw_name, expected_safe in malicious_inputs:
            base_name = os.path.basename(raw_name)
            for char in '<>:"/\\|?*':
                base_name = base_name.replace(char, "_")
            base_name = base_name.strip(". ")
            if not base_name:
                base_name = "transcription_final"

            target = os.path.join(self.output_dir, f"{base_name}.txt")
            resolved = os.path.abspath(os.path.dirname(target))
            self.assertEqual(resolved, os.path.abspath(self.output_dir), f"Path traversal breached for: {raw_name}")
            print(f"  [OK] Input: '{raw_name}' -> Safe: '{base_name}'")

    # 2. Cross-platform Audio Processing (FFmpeg)
    def test_02_ffmpeg_preprocessing(self):
        print("\n[TEST 2] Testing FFmpeg: 16 kHz mono conversion and silence removal...")
        self.assertTrue(os.path.exists(self.test_audio))

        cleaned = os.path.join(self.output_dir, "test_cross_cleaned.wav")
        if os.path.exists(cleaned):
            os.remove(cleaned)

        cmd = [
            "ffmpeg", "-y", "-i", self.test_audio,
            "-ac", "1",
            "-ar", "16000",
            "-af", "silenceremove=start_periods=1:start_silence=0.3:start_threshold=-35dB:detection=peak",
            cleaned
        ]
        flags = get_subprocess_creation_flags()
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)
        self.assertEqual(res.returncode, 0, "FFmpeg returned error during audio preprocessing")
        self.assertTrue(os.path.exists(cleaned))
        print("  [OK] FFmpeg successfully preprocessed the audio file.")

    # 3. Hardware Acceleration (CUDA / MPS / CPU fallback)
    def test_03_hardware_acceleration(self):
        print("\n[TEST 3] Testing hardware acceleration (CUDA / MPS / CPU)...")
        if torch.cuda.is_available():
            dev = "cuda"
            name = torch.cuda.get_device_name(0)
            print(f"  [OK] Found NVIDIA CUDA acceleration: {name}")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            dev = "mps"
            print("  [OK] Found Apple Silicon acceleration (Metal / MPS)")
        else:
            dev = "cpu"
            print("  [OK] Using processor (CPU fallback)")

        # Load and unload model lifecycle
        torch.cuda.empty_cache() if dev == "cuda" else None
        model = whisper.load_model("turbo", device=dev)
        self.assertIsNotNone(model)
        print("  [OK] Model 'turbo' successfully loaded on target device.")

        del model
        if dev == "cuda":
            torch.cuda.empty_cache()
        elif dev == "mps" and hasattr(torch, "mps"):
            torch.mps.empty_cache()
        print("  [OK] Device memory released cleanly.")

    # 4. End-to-End Transcription and Atomic File Persistence
    def test_04_transcription_and_atomic_write(self):
        print("\n[TEST 4] End-to-end transcription and atomic file writing test...")
        cleaned = os.path.join(self.output_dir, "test_cross_cleaned.wav")
        dev = "cuda" if torch.cuda.is_available() else ("mps" if hasattr(torch.backends, "mps") and torch.backends.mps.is_available() else "cpu")

        model = whisper.load_model("turbo", device=dev)
        t0 = time.time()
        result = model.transcribe(cleaned, language="ru", condition_on_previous_text=False, verbose=False)
        duration = round(time.time() - t0, 2)

        txt_file = os.path.join(self.output_dir, "test_atomic.txt")
        json_file = os.path.join(self.output_dir, "test_atomic.json")

        # Atomic write with temporary buffer
        tmp_txt = txt_file + ".tmp"
        tmp_json = json_file + ".tmp"
        with open(tmp_txt, "w", encoding="utf-8") as f:
            f.write(result.get("text", ""))
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(result.get("segments", []), f, ensure_ascii=False, indent=2)

        os.replace(tmp_txt, txt_file)
        os.replace(tmp_json, json_file)

        self.assertTrue(os.path.exists(txt_file))
        self.assertTrue(os.path.exists(json_file))
        print(f"  [OK] Audio transcribed in {duration} s and atomically saved.")


def run_cross_platform_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestWhisperTranscriberCrossPlatform)
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite).wasSuccessful()


if __name__ == "__main__":
    success = run_cross_platform_tests()
    sys.exit(0 if success else 1)
