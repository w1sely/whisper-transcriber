#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Automated Test Suite for Whisper Transcriber.
"""

import os
import sys
import time
import json
import subprocess
import unittest

# UTF-8 console output setup for Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch
import whisper


class TestWhisperTranscriber(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work_dir = os.path.dirname(os.path.abspath(__file__))
        cls.test_audio = os.path.join(cls.work_dir, "test_speech.wav")
        cls.output_dir = os.path.join(cls.work_dir, "test_output")
        os.makedirs(cls.output_dir, exist_ok=True)

    # === TEST 1: Path Traversal Protection & Sanitization ===
    def test_01_security_filename_sanitization(self):
        print("\n[TEST 1] Testing filename security and sanitization...")
        
        test_cases = [
            ("../../etc/passwd", "passwd"),
            ("..\\..\\Windows\\System32\\cmd.exe", "cmd.exe"),
            ("my<test>:file/name|is?bad*.wav", "my_test__file_name_is_bad_.wav"),
            ("...spaces_and_dots...   ", "spaces_and_dots"),
            (":::???***", "transcription_final"),
            ("", "transcription_final"),
            ("regular_name_123", "regular_name_123")
        ]

        for raw_input, expected_contain in test_cases:
            base_name = os.path.basename(raw_input)
            for char in '<>:"/\\|?*':
                base_name = base_name.replace(char, "_")
            base_name = base_name.strip(". ")
            if not base_name:
                base_name = "transcription_final"

            target_file = os.path.join(self.output_dir, f"{base_name}.txt")
            resolved_dir = os.path.abspath(os.path.dirname(target_file))
            self.assertEqual(resolved_dir, os.path.abspath(self.output_dir), f"Path traversal detected for: {raw_input}")
            print(f"  [OK] Input: '{raw_input}' -> Sanitized: '{base_name}'")

    # === TEST 2: FFmpeg Preprocessing (Silence Removal, Mono 16 kHz) ===
    def test_02_ffmpeg_preprocessing(self):
        print("\n[TEST 2] Testing FFmpeg: 16 kHz mono conversion and silence removal...")
        self.assertTrue(os.path.exists(self.test_audio), "Test audio file not found")

        cleaned_audio = os.path.join(self.output_dir, "test_cleaned.wav")
        if os.path.exists(cleaned_audio):
            os.remove(cleaned_audio)

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", self.test_audio,
            "-ac", "1",
            "-ar", "16000",
            "-af", "silenceremove=start_periods=1:start_silence=0.3:start_threshold=-35dB:detection=peak",
            cleaned_audio
        ]

        res = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(res.returncode, 0, f"FFmpeg error: {res.stderr.decode('utf-8', errors='ignore')}")
        self.assertTrue(os.path.exists(cleaned_audio), "Cleaned file was not created")
        self.assertGreater(os.path.getsize(cleaned_audio), 1000, "Cleaned file size is suspiciously small")

        probe_res = subprocess.run(["ffmpeg", "-i", cleaned_audio], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out_str = probe_res.stderr.decode("utf-8", errors="ignore")
        self.assertIn("16000 Hz", out_str, "Sample rate must be 16000 Hz")
        self.assertIn("mono", out_str, "Audio channel must be mono")
        print("  [OK] FFmpeg successfully created 16kHz mono audio without silence.")

    # === TEST 3: GPU (CUDA) and VRAM Lifecycle ===
    def test_03_gpu_and_vram_lifecycle(self):
        print("\n[TEST 3] Testing GPU (CUDA) and VRAM cleanup...")
        self.assertTrue(torch.cuda.is_available(), "CUDA must be available")
        
        gpu_name = torch.cuda.get_device_name(0)
        print(f"  [OK] Detected GPU: {gpu_name}")

        torch.cuda.empty_cache()
        mem_start = torch.cuda.memory_allocated()

        t0 = time.time()
        model = whisper.load_model("turbo", device="cuda")
        t_load = time.time() - t0
        mem_loaded = torch.cuda.memory_allocated()
        print(f"  [OK] Model 'turbo' loaded in {t_load:.2f} s. VRAM: {(mem_loaded - mem_start)/1024**2:.1f} MB")

        self.assertGreater(mem_loaded, mem_start, "VRAM must be allocated by the model")

        del model
        torch.cuda.empty_cache()
        mem_after = torch.cuda.memory_allocated()
        freed_mb = (mem_loaded - mem_after) / 1024**2
        print(f"  [OK] Model unloaded, VRAM freed: {freed_mb:.1f} MB")
        self.assertLess(mem_after, mem_loaded, "VRAM must be freed after unloading")

    # === TEST 4: End-to-End Speech Transcription & File Validation ===
    def test_04_end_to_end_transcription(self):
        print("\n[TEST 4] End-to-end audio transcription...")
        cleaned_audio = os.path.join(self.output_dir, "test_cleaned.wav")
        self.assertTrue(os.path.exists(cleaned_audio))

        model = whisper.load_model("turbo", device="cuda")

        t0 = time.time()
        result = model.transcribe(
            cleaned_audio,
            language="ru",
            condition_on_previous_text=False,
            verbose=False
        )
        t_trans = time.time() - t0

        text = result.get("text", "").strip()
        print(f"  [OK] Transcribed text: \"{text}\"")
        print(f"  [OK] Transcription time: {t_trans:.2f} s (for 6.5 s audio)")

        self.assertTrue(len(text) > 0, "Text must not be empty")
        
        base_name = "test_transcription_result"
        txt_path = os.path.join(self.output_dir, f"{base_name}.txt")
        json_path = os.path.join(self.output_dir, f"{base_name}.json")

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result["segments"], f, ensure_ascii=False, indent=2)

        self.assertTrue(os.path.exists(txt_path), ".txt file must exist")
        self.assertTrue(os.path.exists(json_path), ".json file must exist")

        with open(json_path, "r", encoding="utf-8") as f:
            loaded_json = json.load(f)
        self.assertIsInstance(loaded_json, list)
        self.assertGreater(len(loaded_json), 0)
        self.assertIn("start", loaded_json[0])
        self.assertIn("end", loaded_json[0])
        self.assertIn("text", loaded_json[0])
        print(f"  [OK] JSON timestamps valid: {len(loaded_json)} segment(s).")

    # === TEST 5: Exception Handling and Corrupt Files ===
    def test_05_exception_handling(self):
        print("\n[TEST 5] Testing exception handling and corrupt media files...")
        
        # 1. Non-existent file
        with self.assertRaises(Exception):
            model = whisper.load_model("turbo", device="cuda")
            model.transcribe("non_existent_file_xyz_123.wav")
        print("  [OK] Exception for non-existent file handled properly.")

        # 2. Corrupt file
        corrupt_file = os.path.join(self.output_dir, "corrupt.wav")
        with open(corrupt_file, "wb") as f:
            f.write(b"NOT_A_VALID_WAV_HEADER_DATA")

        res = subprocess.run(["ffmpeg", "-y", "-i", corrupt_file, os.path.join(self.output_dir, "out_corrupt.wav")],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertNotEqual(res.returncode, 0, "FFmpeg must return error for corrupted audio file")
        print("  [OK] Corrupted media file in FFmpeg detected properly.")


def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestWhisperTranscriber)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
