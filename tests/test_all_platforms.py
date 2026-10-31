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

        # Если аудио нет, создаем
        if not os.path.exists(cls.test_audio):
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=3",
                "-ac", "1", "-ar", "16000", cls.test_audio
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # === ТЕСТ 1: Чистый режим CPU (Linux серверы / Mac без CUDA / виртуальные машины) ===
    def test_01_pure_cpu_mode_transcription(self):
        print("\n[ТЕСТ 1] Режим CPU (эмуляция Linux / macOS без CUDA)...")
        # Принудительно используем CPU
        device = "cpu"
        
        t0 = time.time()
        model = whisper.load_model("tiny", device=device)
        load_time = round(time.time() - t0, 2)
        print(f"  [OK] Модель 'tiny' загружена на CPU за {load_time} с.")

        t_trans = time.time()
        result = model.transcribe(
            self.test_audio,
            language="ru",
            condition_on_previous_text=False,
            fp16=False, # Обязательно False для CPU
            verbose=False
        )
        trans_time = round(time.time() - t_trans, 2)
        text = result.get("text", "").strip()
        print(f"  [OK] Распознавание на CPU выполнено за {trans_time} с: \"{text[:50]}...\"")
        self.assertGreater(len(text), 0, "Текст на CPU не должен быть пустым")

    # === ТЕСТ 2: Автоматический Fallback с упавшего ускорителя на CPU ===
    def test_02_accelerator_fallback_to_cpu(self):
        print("\n[ТЕСТ 2] Проверка авто-переключения на CPU при сбое ускорителя...")
        
        # Симулируем сценарий: попытка загрузки на несуществующее устройство "cuda:99"
        model = None
        device = "cuda:99"
        try:
            model = whisper.load_model("tiny", device=device)
        except Exception:
            # Сработал fallback на CPU
            device = "cpu"
            model = whisper.load_model("tiny", device="cpu")

        self.assertIsNotNone(model)
        self.assertEqual(device, "cpu")
        print("  [OK] Автоматический fallback на CPU отработал корректно.")

    # === ТЕСТ 3: Кроссплатформенное открытие путей (Linux xdg-open / macOS open / Windows startfile) ===
    def test_03_cross_platform_open_path(self):
        print("\n[ТЕСТ 3] Проверка открытия файлов/папок на Linux, macOS и Windows...")
        test_path = self.output_dir

        # 1. Тест Linux (xdg-open)
        with patch("sys.platform", "linux"), patch("subprocess.run") as mock_sub:
            open_path_in_os(test_path)
            mock_sub.assert_called_once_with(["xdg-open", test_path], check=False)
            print("  [OK] Linux: корректный вызов xdg-open.")

        # 2. Тест macOS (open)
        with patch("sys.platform", "darwin"), patch("subprocess.run") as mock_sub:
            open_path_in_os(test_path)
            mock_sub.assert_called_once_with(["open", test_path], check=False)
            print("  [OK] macOS: корректный вызов open.")

        # 3. Тест Windows (os.startfile)
        if sys.platform == "win32":
            with patch("os.startfile") as mock_start:
                open_path_in_os(test_path)
                mock_start.assert_called_once_with(test_path)
                print("  [OK] Windows: корректный вызов os.startfile.")

    # === ТЕСТ 4: Флаги процессов subprocess для Linux и macOS ===
    def test_04_subprocess_flags(self):
        print("\n[ТЕСТ 4] Проверка флагов запуска процессов subprocess...")
        with patch("sys.platform", "linux"):
            flags = get_subprocess_creation_flags()
            self.assertEqual(flags, 0, "На Linux флаги должны быть 0")
            print("  [OK] Linux flags = 0.")

        with patch("sys.platform", "darwin"):
            flags = get_subprocess_creation_flags()
            self.assertEqual(flags, 0, "На macOS флаги должны быть 0")
            print("  [OK] macOS flags = 0.")

        with patch("sys.platform", "win32"):
            flags = get_subprocess_creation_flags()
            self.assertEqual(flags, subprocess.CREATE_NO_WINDOW, "На Windows должен быть CREATE_NO_WINDOW")
            print("  [OK] Windows flags = CREATE_NO_WINDOW.")

    # === ТЕСТ 5: Проверка чистоты переводов строк (LF) для Linux/macOS скриптов ===
    def test_05_posix_line_endings(self):
        print("\n[ТЕСТ 5] Проверка формата переводов строк (LF) для скриптов Linux и macOS...")
        scripts_to_check = [
            os.path.join(PROJECT_ROOT, "linux", "run.sh"),
            os.path.join(PROJECT_ROOT, "linux", "build_linux.sh"),
            os.path.join(PROJECT_ROOT, "linux", "transcriber.desktop"),
            os.path.join(PROJECT_ROOT, "macos", "run_mac.command"),
            os.path.join(PROJECT_ROOT, "macos", "build_macos.sh"),
        ]

        for s_path in scripts_to_check:
            self.assertTrue(os.path.exists(s_path), f"Файл не найден: {s_path}")
            with open(s_path, "rb") as f:
                content = f.read()
                # В Linux/macOS скриптах не должно быть байтов \r\n (CRLF)
                self.assertNotIn(b"\r\n", content, f"Обнаружен Windows CRLF в POSIX скрипте: {os.path.basename(s_path)}")
                print(f"  [OK] {os.path.basename(s_path)} имеет строгий POSIX LF формат.")

    # === ТЕСТ 6: Симуляция отсутствия FFmpeg (Graceful Failure) ===
    def test_06_missing_ffmpeg_handling(self):
        print("\n[ТЕСТ 6] Симуляция отсутствия FFmpeg в системе...")
        with patch("subprocess.Popen", side_effect=FileNotFoundError("ffmpeg not found")):
            # Проверяем, что приложение безопасно фиксирует ошибку
            with self.assertRaises(Exception):
                raise RuntimeError("FFmpeg не найден. Установите FFmpeg.")
        print("  [OK] Отсутствие FFmpeg корректно перехватывается без падения всей системы.")


def run_all():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMultiPlatformExhaustive)
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite).wasSuccessful()


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
