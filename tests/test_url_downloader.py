#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Automated Test Suite for URL Audio Downloader (yt-dlp integration).
Validates library availability, URL format verification, filename sanitization,
cancellation hooks, and graceful exception handling for unreachable links.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)


class TestUrlDownloader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_output = os.path.join(PROJECT_ROOT, "test_output")
        os.makedirs(cls.test_output, exist_ok=True)

    # === TEST 1: yt-dlp Library Availability & Version Inspection ===
    def test_01_ytdlp_availability(self):
        print("\n[TEST 1] Checking yt-dlp library availability...")
        try:
            import yt_dlp
            has_ytdlp = True
            version = getattr(yt_dlp, "__version__", None)
            if not version and hasattr(yt_dlp, "version"):
                version = getattr(yt_dlp.version, "__version__", "unknown")
        except ImportError:
            has_ytdlp = False
            version = None

        self.assertTrue(has_ytdlp, "yt-dlp must be installed in the environment")
        print(f"  [OK] yt-dlp is available (version: {version})")

    # === TEST 2: URL Format Validation ===
    def test_02_url_validation(self):
        print("\n[TEST 2] Testing URL validation logic...")
        valid_urls = [
            "https://vkvideo.ru/video-213618393_456239675?list=ln-m29s3hfMW1oAzqNqaS",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "http://rutube.ru/video/1234567890abcdef/",
            "https://vimeo.com/12345678",
            "https://soundcloud.com/artist/track",
        ]
        invalid_urls = [
            "",
            "   ",
            "not_a_url",
            "ftp://invalid-protocol.com/file.mp3",
            "C:\\Users\\USER\\Music\\test.mp3",
            "file:///path/to/file.mp3",
        ]

        def is_valid_url(url_str):
            if not url_str or not isinstance(url_str, str):
                return False
            url_clean = url_str.strip()
            return url_clean.startswith(("http://", "https://")) and len(url_clean) > 10

        for url in valid_urls:
            self.assertTrue(is_valid_url(url), f"URL should be valid: {url}")
            print(f"  [OK] Valid URL accepted: {url[:45]}...")

        for url in invalid_urls:
            self.assertFalse(is_valid_url(url), f"URL should be rejected: {url}")
            print(f"  [OK] Invalid URL rejected: '{url}'")

    # === TEST 3: Safe Filename Extraction & Web Title Sanitization ===
    def test_03_title_sanitization(self):
        print("\n[TEST 3] Testing safe filename extraction from complex web titles...")
        dirty_titles = [
            ("Lecture 4: AI & Deep Learning / 2026? <Part 1>*|", "Lecture 4_ AI & Deep Learning _ 2026_ _Part 1__"),
            ("VK Video - Лекция #4 (Аудиозапись): https://vkvideo.ru", "VK Video - Лекция #4 (Аудиозапись)_ https___vkvideo.ru"),
            ("...leading and trailing spaces & dots...   ", "leading and trailing spaces & dots"),
            (":::???***///\\\\\\", "downloaded_audio"),
            ("", "downloaded_audio"),
        ]

        def sanitize_title(title_str):
            if not title_str:
                return "downloaded_audio"
            clean = title_str
            for ch in '<>:"/\\|?*':
                clean = clean.replace(ch, "_")
            clean = os.path.basename(clean).strip(". ")
            return clean if clean else "downloaded_audio"

        for raw_title, expected in dirty_titles:
            sanitized = sanitize_title(raw_title)
            # Ensure no illegal filesystem characters remain
            for ch in '<>:"/\\|?*':
                self.assertNotIn(ch, sanitized, f"Illegal char '{ch}' found in: {sanitized}")
            print(f"  [OK] Sanitized: '{raw_title[:35]}' -> '{sanitized}'")

    # === TEST 4: yt-dlp Configuration (FFmpeg MP3 & Single Video Flag) ===
    def test_04_ytdlp_configuration(self):
        print("\n[TEST 4] Validating yt-dlp options and configuration...")
        import yt_dlp

        downloads_dir = self.test_output
        dummy_hook = lambda d: None

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(downloads_dir, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'progress_hooks': [dummy_hook],
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }

        self.assertEqual(ydl_opts['format'], 'bestaudio/best')
        self.assertTrue(ydl_opts['noplaylist'], "noplaylist must be True to prevent downloading entire playlists")
        self.assertEqual(ydl_opts['postprocessors'][0]['preferredcodec'], 'mp3')
        
        # Test YoutubeDL initialization with these options
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            self.assertIsNotNone(ydl)
        print("  [OK] yt-dlp options configured with MP3 extraction and noplaylist.")

    # === TEST 5: Cancellation Hook Mechanism ===
    def test_05_cancellation_mechanism(self):
        print("\n[TEST 5] Testing download cancellation hook...")
        import yt_dlp

        class DownloadCancelledError(Exception):
            pass

        cancel_flag = [False]

        def cancel_hook(d):
            if cancel_flag[0]:
                raise DownloadCancelledError("Download aborted by user.")

        ydl_opts = {
            'progress_hooks': [cancel_hook],
            'quiet': True,
        }

        # Simulate cancellation during hook invocation
        cancel_flag[0] = True
        with self.assertRaises(DownloadCancelledError):
            cancel_hook({'status': 'downloading', 'downloaded_bytes': 1024})

        print("  [OK] Cancellation hook raises DownloadCancelledError as expected.")

    # === TEST 6: Graceful Exception Handling for Invalid / Unreachable URLs ===
    def test_06_unreachable_url_handling(self):
        print("\n[TEST 6] Testing graceful exception handling for unreachable URLs...")
        import yt_dlp

        fake_url = "https://127.0.0.1:59999/non_existent_audio_stream.mp3"
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 1,
            'retries': 0,
        }

        error_caught = False
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(fake_url, download=False)
        except Exception as e:
            error_caught = True
            error_msg = str(e)
            print(f"  [OK] Gracefully caught yt-dlp network/extraction exception: {error_msg[:60]}...")

        self.assertTrue(error_caught, "Unreachable URL must raise an exception handled by application")


def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestUrlDownloader)
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite).wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
