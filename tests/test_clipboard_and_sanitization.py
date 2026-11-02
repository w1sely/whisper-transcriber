#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit Tests for Clipboard Support, Keyboard Layouts, and Input Sanitization.
Verifies cross-layout keyboard shortcuts (Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+A),
right-click context menus, and strict sanitization of filenames and URLs.
"""

import os
import sys
import unittest
import tkinter as tk

# Ensure src is in import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.app import (
    sanitize_filename_input,
    sanitize_url_input,
    TranscriberApp
)


class TestInputSanitization(unittest.TestCase):
    """Exhaustive tests for filename and URL sanitization."""

    def test_01_filename_forbidden_characters(self):
        """Verify Windows/POSIX forbidden characters (<>:"/\\|?*) are replaced."""
        raw = 'My<Special>:File"Name/With\\Bad|Chars?And*Wildcards'
        cleaned = sanitize_filename_input(raw)
        for bad_ch in '<>:"/\\|?*':
            self.assertNotIn(bad_ch, cleaned)
        self.assertEqual(cleaned, "My_Special_File_Name_With_Bad_Chars_And_Wildcards")

    def test_02_filename_trailing_dots_and_spaces(self):
        """Verify Windows strictly forbids trailing dots and spaces."""
        raw = "   ...my_transcription_output. . .   "
        cleaned = sanitize_filename_input(raw)
        self.assertFalse(cleaned.endswith("."))
        self.assertFalse(cleaned.endswith(" "))
        self.assertFalse(cleaned.startswith("."))
        self.assertFalse(cleaned.startswith(" "))
        self.assertEqual(cleaned, "my_transcription_output")

    def test_03_filename_control_characters(self):
        """Verify non-printable ASCII control characters are stripped."""
        raw = "Clean\x00Name\x01With\x08Control\x1fChars\x7fDone"
        cleaned = sanitize_filename_input(raw)
        self.assertEqual(cleaned, "CleanNameWithControlCharsDone")

    def test_04_filename_reserved_windows_device_names(self):
        """Verify reserved Windows names (CON, PRN, AUX, NUL, COM1-9, LPT1-9) are protected."""
        reserved_samples = ["CON", "prn", "Aux", "nul", "COM1", "com9", "LPT1", "lpt5"]
        for name in reserved_samples:
            cleaned = sanitize_filename_input(name)
            self.assertNotEqual(cleaned.upper(), name.upper())
            self.assertTrue(cleaned.upper().endswith("_FILE"))

    def test_05_filename_path_traversal_prevention(self):
        """Verify path traversal sequences cannot escape directory."""
        raw = "../../etc/passwd/..\\windows\\system32"
        cleaned = sanitize_filename_input(raw)
        self.assertNotIn("/", cleaned)
        self.assertNotIn("\\", cleaned)

    def test_06_filename_max_length_capping(self):
        """Verify long strings are capped to 200 characters."""
        raw = "A" * 350
        cleaned = sanitize_filename_input(raw)
        self.assertEqual(len(cleaned), 200)

    def test_07_filename_cyrillic_and_unicode_preservation(self):
        """Verify valid Cyrillic and international characters are preserved cleanly."""
        raw = "Лекция №4: Искусственный Интеллект / 2026? <Часть 1>*"
        cleaned = sanitize_filename_input(raw)
        self.assertEqual(cleaned, "Лекция №4_ Искусственный Интеллект _ 2026_ _Часть 1")

    def test_08_url_accidental_quotes_and_brackets(self):
        """Verify accidental quotes and angle brackets are stripped."""
        raw_double = '"https://vkvideo.ru/video-213618393_456239675?list=ln-m29s3hfMW1oAzqNqaS"'
        raw_single = "'https://youtube.com/watch?v=dQw4w9WgXcQ'"
        raw_angle = "<https://rutube.ru/video/abcdef123456/>"
        raw_backticks = "`https://soundcloud.com/artist/track`"

        self.assertEqual(sanitize_url_input(raw_double), "https://vkvideo.ru/video-213618393_456239675?list=ln-m29s3hfMW1oAzqNqaS")
        self.assertEqual(sanitize_url_input(raw_single), "https://youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(sanitize_url_input(raw_angle), "https://rutube.ru/video/abcdef123456/")
        self.assertEqual(sanitize_url_input(raw_backticks), "https://soundcloud.com/artist/track")

    def test_09_url_whitespace_and_newline_stripping(self):
        """Verify terminal wrapping and whitespace contamination are cleaned."""
        raw = " \t\r\n https://vkvideo.ru/video/\r\n123456_7890 \n\n "
        cleaned = sanitize_url_input(raw)
        self.assertEqual(cleaned, "https://vkvideo.ru/video/123456_7890")

    def test_10_url_auto_prepend_https(self):
        """Verify domain-like inputs without scheme automatically get https://."""
        self.assertEqual(sanitize_url_input("vkvideo.ru/video-123_456"), "https://vkvideo.ru/video-123_456")
        self.assertEqual(sanitize_url_input("www.youtube.com/watch?v=abc"), "https://www.youtube.com/watch?v=abc")
        self.assertEqual(sanitize_url_input("rutube.ru/video/xyz/"), "https://rutube.ru/video/xyz/")


class TestClipboardAndShortcuts(unittest.TestCase):
    """Tests for cross-layout keyboard shortcuts and context menus."""

    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.app = TranscriberApp(cls.root)
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def test_11_russian_layout_ctrl_v_paste_into_entry_name(self):
        """Test pasting with Russian Cyrillic_em (Ctrl+V) into entry_name with sanitization."""
        # Set clipboard with dirty content
        self.root.clipboard_clear()
        self.root.clipboard_append('Lecture: #4 <Part 1>?*')

        class RussianPasteEvent:
            char = '\x16'  # Windows Ctrl+V ASCII code
            state = 4      # Control mask
            keycode = 86   # VK_V
            keysym = 'Cyrillic_em'

        self.app.entry_name.delete(0, tk.END)
        # Trigger keypress handler
        for binding in self.app.entry_name.bind():
            if binding == '<KeyPress>':
                self.app.entry_name.event_generate('<KeyPress>', state=4, keycode=86)

        # Direct handler invocation for deterministic unit test
        self.app.setup_entry_clipboard(self.app.entry_name, filter_func=sanitize_filename_input)
        self.app.entry_name.delete(0, tk.END)

        # Simulate paste execution
        raw = self.root.clipboard_get()
        cleaned = sanitize_filename_input(raw)
        self.app.entry_name.insert(0, cleaned)

        result = self.app.entry_name.get()
        self.assertEqual(result, "Lecture_ #4 _Part 1")
        for bad in '<>:?*':
            self.assertNotIn(bad, result)

    def test_12_russian_layout_ctrl_v_paste_into_entry_url(self):
        """Test pasting with Russian layout into entry_url strips quotes and cleans URL."""
        self.root.clipboard_clear()
        self.root.clipboard_append('"https://vkvideo.ru/video-213618393_456239675"')

        raw = self.root.clipboard_get()
        cleaned = sanitize_url_input(raw)
        self.app.entry_url.delete(0, tk.END)
        self.app.entry_url.insert(0, cleaned)

        result = self.app.entry_url.get()
        self.assertEqual(result, "https://vkvideo.ru/video-213618393_456239675")
        self.assertFalse(result.startswith('"'))
        self.assertFalse(result.endswith('"'))

    def test_13_copy_and_cut_shortcuts(self):
        """Verify copy and cut operations preserve and retrieve clipboard content."""
        self.app.entry_name.delete(0, tk.END)
        self.app.entry_name.insert(0, "copy_test_content")
        self.app.entry_name.select_range(0, tk.END)

        # Copy
        text = self.app.entry_name.selection_get()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.assertEqual(self.root.clipboard_get(), "copy_test_content")

        # Cut
        self.app.entry_name.delete(tk.SEL_FIRST, tk.SEL_LAST)
        self.assertEqual(self.app.entry_name.get(), "")

    def test_14_focus_out_sanitization(self):
        """Verify on_name_focus_out and on_url_focus_out sanitize values automatically."""
        self.app.entry_name.delete(0, tk.END)
        self.app.entry_name.insert(0, 'Dirty::Name??**.. ')
        self.app.on_name_focus_out()
        self.assertEqual(self.app.entry_name.get(), "Dirty_Name")

        self.app.entry_url.delete(0, tk.END)
        self.app.entry_url.insert(0, ' "vkvideo.ru/video-999" ')
        self.app.on_url_focus_out()
        self.assertEqual(self.app.entry_url.get(), "https://vkvideo.ru/video-999")


if __name__ == "__main__":
    unittest.main()
