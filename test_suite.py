import os
import sys
import time
import json
import subprocess
import unittest

# Настройка UTF-8 для вывода в консоль Windows
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

    # === ТЕСТ 1: Безопасность и санитизация путей (Path Traversal Protection) ===
    def test_01_security_filename_sanitization(self):
        print("\n[ТЕСТ 1] Проверка безопасности и санитизации имен файлов...")
        
        test_cases = [
            ("../../etc/passwd", "passwd"),
            ("..\\..\\Windows\\System32\\cmd.exe", "cmd.exe"),
            ("my<test>:file/name|is?bad*.wav", "my_test__file_name_is_bad_.wav"),
            ("...spaces_and_dots...   ", "spaces_and_dots"),
            (":::???***", "transcription_final"),
            ("", "transcription_final"),
            ("Обычное_Имя_123", "Обычное_Имя_123")
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
            self.assertEqual(resolved_dir, os.path.abspath(self.output_dir), f"Path traversal обнаружен для: {raw_input}")
            print(f"  [OK] Вход: '{raw_input}' -> Санитизировано: '{base_name}'")

    # === ТЕСТ 2: FFmpeg обработка (Вырезка тишины, моно 16 кГц) ===
    def test_02_ffmpeg_preprocessing(self):
        print("\n[ТЕСТ 2] Проверка FFmpeg: конвертация в 16 кГц моно и вырезка тишины...")
        self.assertTrue(os.path.exists(self.test_audio), "Тестовый аудиофайл не найден")

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
        self.assertEqual(res.returncode, 0, f"Ошибка FFmpeg: {res.stderr.decode('utf-8', errors='ignore')}")
        self.assertTrue(os.path.exists(cleaned_audio), "Очищенный файл не создан")
        self.assertGreater(os.path.getsize(cleaned_audio), 1000, "Размер очищенного файла подозрительно мал")

        probe_res = subprocess.run(["ffmpeg", "-i", cleaned_audio], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out_str = probe_res.stderr.decode("utf-8", errors="ignore")
        self.assertIn("16000 Hz", out_str, "Частота дискретизации должна быть 16000 Hz")
        self.assertIn("mono", out_str, "Канал должен быть mono")
        print("  [OK] FFmpeg успешно создал 16kHz mono аудио без тишины.")

    # === ТЕСТ 3: GPU (CUDA) и управление видеопамятью (VRAM) ===
    def test_03_gpu_and_vram_lifecycle(self):
        print("\n[ТЕСТ 3] Проверка GPU (CUDA RTX 5070) и очистки видеопамяти...")
        self.assertTrue(torch.cuda.is_available(), "CUDA должна быть доступна на машине")
        
        gpu_name = torch.cuda.get_device_name(0)
        print(f"  [OK] Обнаружена видеокарта: {gpu_name}")

        torch.cuda.empty_cache()
        mem_start = torch.cuda.memory_allocated()

        t0 = time.time()
        model = whisper.load_model("turbo", device="cuda")
        t_load = time.time() - t0
        mem_loaded = torch.cuda.memory_allocated()
        print(f"  [OK] Модель 'turbo' загружена за {t_load:.2f} сек. Память: {(mem_loaded - mem_start)/1024**2:.1f} МБ")

        self.assertGreater(mem_loaded, mem_start, "Видеопамять должна быть занята моделью")

        del model
        torch.cuda.empty_cache()
        mem_after = torch.cuda.memory_allocated()
        freed_mb = (mem_loaded - mem_after) / 1024**2
        print(f"  [OK] Модель выгружена, освобождено VRAM: {freed_mb:.1f} МБ")
        self.assertLess(mem_after, mem_loaded, "Память VRAM должна освобождаться")

    # === ТЕСТ 4: Сквозная транскрибация речи и валидация файлов ===
    def test_04_end_to_end_transcription(self):
        print("\n[ТЕСТ 4] Сквозная транскрибация аудиозаписи...")
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
        print(f"  [OK] Распознанный текст: \"{text}\"")
        print(f"  [OK] Время распознавания: {t_trans:.2f} сек (для 6.5 сек аудио)")

        self.assertTrue(len(text) > 0, "Текст не должен быть пустым")
        
        base_name = "test_transcription_result"
        txt_path = os.path.join(self.output_dir, f"{base_name}.txt")
        json_path = os.path.join(self.output_dir, f"{base_name}.json")

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result["segments"], f, ensure_ascii=False, indent=2)

        self.assertTrue(os.path.exists(txt_path), "Файл .txt должен существовать")
        self.assertTrue(os.path.exists(json_path), "Файл .json должен существовать")

        with open(json_path, "r", encoding="utf-8") as f:
            loaded_json = json.load(f)
        self.assertIsInstance(loaded_json, list)
        self.assertGreater(len(loaded_json), 0)
        self.assertIn("start", loaded_json[0])
        self.assertIn("end", loaded_json[0])
        self.assertIn("text", loaded_json[0])
        print(f"  [OK] JSON таймкоды валидны: {len(loaded_json)} сегмент(ов).")

    # === ТЕСТ 5: Обработка исключений и поврежденных файлов ===
    def test_05_exception_handling(self):
        print("\n[ТЕСТ 5] Проверка обработки исключений и битых файлов...")
        
        # 1. Несуществующий файл
        with self.assertRaises(Exception):
            model = whisper.load_model("turbo", device="cuda")
            model.transcribe("non_existent_file_xyz_123.wav")
        print("  [OK] Исключение на несуществующий файл корректно перехватывается.")

        # 2. Поврежденный файл
        corrupt_file = os.path.join(self.output_dir, "corrupt.wav")
        with open(corrupt_file, "wb") as f:
            f.write(b"NOT_A_VALID_WAV_HEADER_DATA")

        res = subprocess.run(["ffmpeg", "-y", "-i", corrupt_file, os.path.join(self.output_dir, "out_corrupt.wav")],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertNotEqual(res.returncode, 0, "FFmpeg должен возвращать ошибку на поврежденном файле")
        print("  [OK] Ошибка поврежденного медиафайла в FFmpeg корректно определяется.")


def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestWhisperTranscriber)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
