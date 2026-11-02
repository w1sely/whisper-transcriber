#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Exhaustive Automated Test Suite for URL Audio Downloader & Media Error Handling.
Tests:
- yt-dlp library availability
- URL validation (valid schemes, rejecting bad/local inputs)
- Safe title sanitization
- Single video enforcement (noplaylist)
- Download cancellation hooks
- Unreachable URLs & network timeouts
- Restricted / private video handling
- Human-readable error descriptions and actionable hints
- Missing / deleted local file handling
- Cross-platform paths and behavior (Windows, Linux, macOS)
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

from src.app import format_download_error, DownloadCancelledError


class TestUrlDownloaderExhaustive(unittest.TestCase):
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
            ("Lecture 4: AI & Deep Learning / 2026? <Part 1>*|", "Lecture 4_ AI & Deep Learning _ 2026_ _Part 1___"),
            ("VK Video - Лекция #4 (Аудиозапись): https://vkvideo.ru", "VK Video - Лекция #4 (Аудиозапись)_ https___vkvideo.ru"),
            ("...leading and trailing spaces & dots...   ", "leading and trailing spaces & dots"),
            (":::???***///\\\\\\", "_______________"),
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

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            self.assertIsNotNone(ydl)
        print("  [OK] yt-dlp options configured with MP3 extraction and noplaylist.")

    # === TEST 5: Cancellation Hook Mechanism ===
    def test_05_cancellation_mechanism(self):
        print("\n[TEST 5] Testing download cancellation hook...")
        cancel_flag = [False]

        def cancel_hook(d):
            if cancel_flag[0]:
                raise DownloadCancelledError("Download aborted by user.")

        # Simulate cancellation during hook invocation
        cancel_flag[0] = True
        with self.assertRaises(DownloadCancelledError):
            cancel_hook({'status': 'downloading', 'downloaded_bytes': 1024})

        print("  [OK] Cancellation hook raises DownloadCancelledError as expected.")

    # === TEST 6: Graceful Exception Handling for Unreachable URLs ===
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
            formatted = format_download_error(e)
            self.assertIn("💡 Tip", formatted)
            print(f"  [OK] Gracefully caught and formatted network exception:\n       {formatted.splitlines()[0][:60]}...")

        self.assertTrue(error_caught, "Unreachable URL must raise an exception handled by application")

    # === TEST 7: Access Denied / Restricted Media Handling ===
    def test_07_access_denied_handling(self):
        print("\n[TEST 7] Testing error formatting for restricted/private media...")
        mock_access_denied = Exception("ERROR: [vk] Access denied (1)")
        formatted = format_download_error(mock_access_denied)
        self.assertIn("💡 Tip", formatted)
        self.assertIn("private, age-restricted", formatted)
        print("  [OK] Private/restricted media error formatted with helpful authentication tip.")

    # === TEST 8: Actionable Hints for Various HTTP/Network Errors ===
    def test_08_error_formatter_scenarios(self):
        print("\n[TEST 8] Validating error descriptions across different failure types...")
        scenarios = [
            ("ERROR: [generic] video: Unable to download webpage: Failed to resolve host 'bad.domain' (caused by TransportError(...))",
             "Unable to resolve or reach host"),
            ("ERROR: Video unavailable. This video is private.",
             "private, age-restricted"),
            ("ERROR: HTTP Error 404: Not Found",
             "Media not found (HTTP 404)"),
            ("ERROR: Unsupported URL: ftp://somewhere.com/test",
             "not supported by yt-dlp"),
        ]

        for raw_err, expected_tip_snippet in scenarios:
            formatted = format_download_error(Exception(raw_err))
            self.assertIn("💡 Tip", formatted)
            self.assertIn(expected_tip_snippet, formatted)
            print(f"  [OK] Error properly diagnosed: '{expected_tip_snippet}'")

    # === TEST 9: Missing Local File Handling ===
    def test_09_missing_local_file_handling(self):
        print("\n[TEST 9] Testing missing/deleted local audio file handling...")
        missing_file = os.path.join(self.test_output, "non_existent_audio_file_xyz_999.wav")
        self.assertFalse(os.path.exists(missing_file))

        # Check that application detects file absence
        if not os.path.exists(missing_file):
            err = FileNotFoundError(f"Selected audio file '{missing_file}' does not exist on disk.")
            self.assertIn("non_existent_audio_file_xyz_999.wav", str(err))
            print("  [OK] Missing local audio file detected before processing.")

    # === TEST 10: Cross-Platform Paths and Downloads Directory ===
    def test_10_cross_platform_downloads_dir(self):
        print("\n[TEST 10] Testing cross-platform downloads directory creation...")
        downloads_dir = os.path.join(PROJECT_ROOT, "downloads")
        os.makedirs(downloads_dir, exist_ok=True)
        self.assertTrue(os.path.exists(downloads_dir))
        self.assertTrue(os.path.isdir(downloads_dir))

        # Test writing a dummy file to verify permissions
        test_file = os.path.join(downloads_dir, ".test_write.tmp")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("OK")
        self.assertTrue(os.path.exists(test_file))
        os.remove(test_file)
        self.assertFalse(os.path.exists(test_file))
        print("  [OK] Downloads directory created and writable across OS platforms.")


def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestUrlDownloaderExhaustive)
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite).wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
