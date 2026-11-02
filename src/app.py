#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Whisper Transcriber - Cross-Platform GUI Audio Transcription
Supports: Windows (CUDA/CPU), Linux (CUDA/ROCm/CPU), macOS (Apple Silicon Metal/MPS/CPU).
Features: Local audio files + direct URL downloads (VK Video, YouTube, Rutube, SoundCloud, etc.) via yt-dlp.
"""

import os
import sys
import time
import json
import queue
import threading
import subprocess
import urllib.request
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Attempt to import torch and whisper
try:
    import torch
    import whisper
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    IMPORT_ERROR_MSG = str(e)

# Attempt to import yt-dlp
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False


class DownloadCancelledError(Exception):
    """Raised when a download is cancelled by user request."""
    pass


# Whisper model descriptions and sizes
MODEL_INFO = {
    "turbo": {"file": "large-v3-turbo.pt", "size": "1.5 GB", "desc": "Optimal (fast and accurate)"},
    "large-v3": {"file": "large-v3.pt", "size": "2.9 GB", "desc": "Maximum accuracy"},
    "medium": {"file": "medium.pt", "size": "1.4 GB", "desc": "Balanced accuracy"},
    "small": {"file": "small.pt", "size": "460 MB", "desc": "Lightweight model"},
    "base": {"file": "base.pt", "size": "140 MB", "desc": "Fast baseline"},
    "tiny": {"file": "tiny.pt", "size": "75 MB", "desc": "Ultra-lightweight"},
}


def open_path_in_os(path):
    """Cross-platform opening of a folder or file in the system file manager."""
    if not os.path.exists(path):
        return
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            # Linux and other Unix-like OS
            subprocess.run(["xdg-open", path], check=False)
    except Exception as e:
        print(f"Failed to open path {path}: {e}")


def get_subprocess_creation_flags():
    """Flags to suppress extra console windows (Windows NT)."""
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def format_download_error(err):
    """Formats yt-dlp exceptions into clear, actionable error descriptions."""
    raw = str(err).strip()
    if raw.startswith("ERROR: "):
        raw = raw[7:]

    # Strip verbose nested traceback from TransportError
    if " (caused by " in raw:
        raw = raw.split(" (caused by ")[0]

    lower = raw.lower()
    if any(k in lower for k in ["getaddrinfo failed", "failed to resolve", "connection refused", "timed out", "timeout", "network is unreachable", "connection to"]):
        hint = "\n\n💡 Tip: Unable to resolve or reach host. Check your internet connection or verify the URL domain."
    elif "access denied" in lower or "private" in lower or "login" in lower or "sign in" in lower:
        hint = "\n\n💡 Tip: This media is private, age-restricted, or requires user authorization."
    elif "not found" in lower or "404" in lower or "does not exist" in lower:
        hint = "\n\n💡 Tip: Media not found (HTTP 404). The video may have been deleted or the link is expired."
    elif "unsupported url" in lower:
        hint = "\n\n💡 Tip: The provided URL or service is not supported by yt-dlp. Make sure it points directly to the video/audio."
    else:
        hint = ""

    return f"{raw}{hint}"


class TextRedirector:
    """Redirects stdout/stderr to the GUI queue for real-time log rendering."""
    def __init__(self, log_queue, tag="stdout"):
        self.log_queue = log_queue
        self.tag = tag

    def write(self, string):
        if string:
            self.log_queue.put((string, self.tag))

    def flush(self):
        pass


class TranscriberApp:
    def __init__(self, root):
        self.root = root
        
        # --- SYSTEM WINDOW (OS WINDOW) ---
        self.root.title("Whisper Transcriber (Cross-Platform)")
        self.root.geometry("780x740")
        self.root.minsize(700, 600)
        
        # Intercept window close button (X)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.center_window()

        self.log_queue = queue.Queue()
        self.is_processing = False
        self.cancel_requested = False
        self.loaded_model = None
        self.loaded_model_name = None
        self.ffmpeg_proc = None

        # Base and downloads directories
        self.app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.downloads_dir = os.path.join(self.app_dir, "downloads")
        os.makedirs(self.downloads_dir, exist_ok=True)

        self.selected_file_path = None
        self.output_directory = None
        self.last_saved_txt = None
        self.last_downloaded_url = None

        # Whisper cache directory (default ~/.cache/whisper across all OS)
        self.whisper_cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "whisper")
        os.makedirs(self.whisper_cache_dir, exist_ok=True)

        # --- CROSS-PLATFORM HARDWARE DETECTION ---
        self.device_str = "cpu"
        self.device_display = "CPU"
        self.has_accel = False

        if DEPENDENCIES_AVAILABLE:
            if torch.cuda.is_available():
                # NVIDIA CUDA (Windows / Linux)
                gpu_name = torch.cuda.get_device_name(0)
                self.device_str = "cuda"
                self.device_display = f"GPU: {gpu_name} (CUDA)"
                self.has_accel = True
                try:
                    torch.backends.cuda.matmul.allow_tf32 = True
                    torch.backends.cudnn.allow_tf32 = True
                except Exception:
                    pass
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                # Apple Silicon Metal Performance Shaders (macOS M1/M2/M3/M4)
                self.device_str = "mps"
                self.device_display = "Apple Silicon (Metal MPS)"
                self.has_accel = True
            else:
                self.device_str = "cpu"
                self.device_display = "CPU"
        else:
            self.device_str = "cpu"
            self.device_display = "Error: torch / whisper not found"

        # Color palette (Modern Dark Theme)
        self.colors = {
            "bg": "#1e1e2e",
            "card_bg": "#252538",
            "card_border": "#36384f",
            "input_bg": "#181825",
            "input_fg": "#cdd6f4",
            "text": "#cdd6f4",
            "text_muted": "#9399b2",
            "accent": "#89b4fa",
            "btn_file": "#3b4261",
            "btn_file_hover": "#4a537a",
            "btn_transcribe": "#a6e3a1",
            "btn_transcribe_fg": "#11111b",
            "btn_transcribe_hover": "#94d38f",
            "btn_stop": "#f38ba8",
            "btn_stop_fg": "#11111b",
            "btn_sub": "#313244",
            "btn_sub_hover": "#45475a",
            "success": "#a6e3a1",
            "warning": "#f9e2af",
            "error": "#f38ba8",
            "log_bg": "#11111b",
            "log_fg": "#bac2de",
        }

        self.root.configure(bg=self.colors["bg"])
        self.setup_styles()
        self.build_ui()

        # Start log queue processing loop
        self.root.after(100, self.process_log_queue)
        os_name = "macOS" if sys.platform == "darwin" else ("Windows" if sys.platform == "win32" else "Linux")
        ytdlp_status = "Available" if YTDLP_AVAILABLE else "Not installed"
        self.log_system(f"Platform: {os_name} | Hardware Accel: {self.device_display} | yt-dlp: {ytdlp_status}")
        self.check_ffmpeg()

    def center_window(self):
        self.root.update_idletasks()
        w, h = 780, 740
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def on_closing(self):
        """Safely and completely close application on system close button."""
        self.cancel_requested = True
        self.is_processing = False
        if self.ffmpeg_proc and self.ffmpeg_proc.poll() is None:
            try:
                self.ffmpeg_proc.terminate()
            except Exception:
                pass
        self.root.destroy()
        os._exit(0)

    def setup_styles(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.style.configure(
            "TProgressbar",
            troughcolor=self.colors["input_bg"],
            background=self.colors["accent"],
            borderwidth=0,
            thickness=8
        )
        self.style.configure(
            "TCombobox",
            fieldbackground=self.colors["input_bg"],
            background=self.colors["card_bg"],
            foreground=self.colors["input_fg"],
            arrowcolor=self.colors["accent"],
            borderwidth=1,
            relief="flat"
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", self.colors["input_bg"])],
            selectbackground=[("readonly", self.colors["card_border"])],
            selectforeground=[("readonly", self.colors["input_fg"])]
        )

    def is_model_cached(self, model_key):
        """Check if model checkpoint exists in local cache."""
        info = MODEL_INFO.get(model_key)
        if not info:
            return False
        cache_path = os.path.join(self.whisper_cache_dir, info["file"])
        return os.path.exists(cache_path) and os.path.getsize(cache_path) > 1024 * 1024

    def get_model_combobox_values(self):
        """Build model list with cache status indicators."""
        values = []
        for key, info in MODEL_INFO.items():
            if self.is_model_cached(key):
                status = f"✓ Cached ({info['size']})"
            else:
                status = f"⬇ Download ({info['size']})"
            values.append(f"{key} [{status}]")
        return values

    def refresh_model_dropdown(self):
        """Update model status in combobox dropdown."""
        current_selection = self.combo_model.get().split()[0] if self.combo_model.get() else "turbo"
        values = self.get_model_combobox_values()
        self.combo_model['values'] = values
        for val in values:
            if val.startswith(current_selection + " "):
                self.combo_model.set(val)
                break

    def build_ui(self):
        main_frame = tk.Frame(self.root, bg=self.colors["bg"], padx=18, pady=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Header: Title + Help + Hardware indicator
        top_bar = tk.Frame(main_frame, bg=self.colors["bg"])
        top_bar.pack(fill=tk.X, pady=(0, 10))

        title_lbl = tk.Label(
            top_bar,
            text="🎙️ Whisper Transcriber",
            font=("Segoe UI", 15, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"]
        )
        title_lbl.pack(side=tk.LEFT)

        btn_doctor = tk.Button(
            top_bar,
            text="ℹ️ Help / OS Setup",
            font=("Segoe UI", 8, "bold"),
            bg=self.colors["btn_sub"],
            fg=self.colors["accent"],
            activebackground=self.colors["btn_sub_hover"],
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self.show_doctor_dialog
        )
        btn_doctor.pack(side=tk.RIGHT, padx=(8, 0))

        badge_color = self.colors["success"] if self.has_accel else self.colors["warning"]
        self.badge_gpu = tk.Label(
            top_bar,
            text=f"⚡ {self.device_display}",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["card_bg"],
            fg=badge_color,
            padx=10,
            pady=4,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors["card_border"]
        )
        self.badge_gpu.pack(side=tk.RIGHT)

        # 2. Control card
        ctrl_card = tk.Frame(
            main_frame,
            bg=self.colors["card_bg"],
            padx=16,
            pady=12,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors["card_border"]
        )
        ctrl_card.pack(fill=tk.X, pady=(0, 10))

        # Row 1: File selection
        file_row = tk.Frame(ctrl_card, bg=self.colors["card_bg"])
        file_row.pack(fill=tk.X, pady=(0, 6))

        self.btn_change_file = tk.Button(
            file_row,
            text="📁 Change file",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["btn_file"],
            fg="#ffffff",
            activebackground=self.colors["btn_file_hover"],
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=5,
            cursor="hand2",
            command=self.on_change_file
        )
        self.btn_change_file.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_selected_file = tk.Label(
            file_row,
            text="No file selected. Select local audio or enter URL below...",
            font=("Segoe UI", 9, "italic"),
            bg=self.colors["card_bg"],
            fg=self.colors["text_muted"],
            anchor="w"
        )
        self.lbl_selected_file.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Row 2: Output file name
        name_label_row = tk.Frame(ctrl_card, bg=self.colors["card_bg"])
        name_label_row.pack(fill=tk.X, pady=(2, 2))

        tk.Label(
            name_label_row,
            text="Change name (output file name without extension):",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["card_bg"],
            fg=self.colors["text"]
        ).pack(side=tk.LEFT)

        self.lbl_save_hint = tk.Label(
            name_label_row,
            text="Generates: <name>.txt and <name>.json",
            font=("Segoe UI", 8),
            bg=self.colors["card_bg"],
            fg=self.colors["text_muted"]
        )
        self.lbl_save_hint.pack(side=tk.RIGHT)

        name_entry_row = tk.Frame(ctrl_card, bg=self.colors["card_bg"])
        name_entry_row.pack(fill=tk.X, pady=(0, 8))

        self.entry_name = tk.Entry(
            name_entry_row,
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["input_bg"],
            fg=self.colors["accent"],
            insertbackground=self.colors["accent"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors["card_border"]
        )
        self.entry_name.pack(fill=tk.X, ipady=5)

        # Row 3: URL input (yt-dlp integration)
        url_label_row = tk.Frame(ctrl_card, bg=self.colors["card_bg"])
        url_label_row.pack(fill=tk.X, pady=(2, 2))

        tk.Label(
            url_label_row,
            text="🔗 Or Paste Media URL (VK Video, YouTube, Rutube, SoundCloud, etc.):",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["card_bg"],
            fg=self.colors["text"]
        ).pack(side=tk.LEFT)

        tk.Label(
            url_label_row,
            text="💡 Extracts MP3 automatically via yt-dlp",
            font=("Segoe UI", 8),
            bg=self.colors["card_bg"],
            fg=self.colors["text_muted"]
        ).pack(side=tk.RIGHT)

        url_input_row = tk.Frame(ctrl_card, bg=self.colors["card_bg"])
        url_input_row.pack(fill=tk.X, pady=(0, 8))

        self.entry_url = tk.Entry(
            url_input_row,
            font=("Segoe UI", 10),
            bg=self.colors["input_bg"],
            fg=self.colors["accent"],
            insertbackground=self.colors["accent"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors["card_border"]
        )
        self.entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 8))
        self.entry_url.bind("<Return>", lambda event: self.on_fetch_url())

        self.btn_fetch = tk.Button(
            url_input_row,
            text="⬇️ Fetch Audio",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["btn_file"],
            fg="#ffffff",
            activebackground=self.colors["btn_file_hover"],
            activeforeground="#ffffff",
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self.on_fetch_url
        )
        self.btn_fetch.pack(side=tk.RIGHT)

        # Row 4: Options
        opts_row = tk.Frame(ctrl_card, bg=self.colors["card_bg"])
        opts_row.pack(fill=tk.X, pady=(0, 8))

        tk.Label(opts_row, text="Model:", font=("Segoe UI", 9), bg=self.colors["card_bg"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(0, 4))
        self.combo_model = ttk.Combobox(
            opts_row,
            values=self.get_model_combobox_values(),
            state="readonly",
            width=26,
            font=("Segoe UI", 9)
        )
        self.refresh_model_dropdown()
        self.combo_model.pack(side=tk.LEFT, padx=(0, 14))

        tk.Label(opts_row, text="Language:", font=("Segoe UI", 9), bg=self.colors["card_bg"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(0, 4))
        self.combo_lang = ttk.Combobox(opts_row, values=["ru", "en", "auto"], width=6, font=("Segoe UI", 9))
        self.combo_lang.set("ru")
        self.combo_lang.pack(side=tk.LEFT, padx=(0, 14))

        self.var_silence = tk.BooleanVar(value=True)
        self.chk_silence = tk.Checkbutton(
            opts_row,
            text="FFmpeg silence trimming",
            variable=self.var_silence,
            font=("Segoe UI", 9),
            bg=self.colors["card_bg"],
            fg=self.colors["text"],
            activebackground=self.colors["card_bg"],
            selectcolor=self.colors["input_bg"]
        )
        self.chk_silence.pack(side=tk.LEFT)

        # Row 5: Actions (Transcribe + Stop)
        act_row = tk.Frame(ctrl_card, bg=self.colors["card_bg"])
        act_row.pack(fill=tk.X, pady=(2, 0))

        self.btn_transcribe = tk.Button(
            act_row,
            text="▶ Transcribe",
            font=("Segoe UI", 11, "bold"),
            bg=self.colors["btn_transcribe"],
            fg=self.colors["btn_transcribe_fg"],
            activebackground=self.colors["btn_transcribe_hover"],
            activeforeground=self.colors["btn_transcribe_fg"],
            relief="flat",
            pady=7,
            cursor="hand2",
            command=self.on_start_transcribe
        )
        self.btn_transcribe.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.btn_stop = tk.Button(
            act_row,
            text="⏹ Stop",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["btn_stop"],
            fg=self.colors["btn_stop_fg"],
            relief="flat",
            padx=16,
            pady=7,
            cursor="hand2",
            state=tk.DISABLED,
            command=self.on_stop_requested
        )
        self.btn_stop.pack(side=tk.RIGHT)

        self.progress_bar = ttk.Progressbar(
            ctrl_card,
            style="TProgressbar",
            mode="indeterminate"
        )
        self.progress_bar.pack(fill=tk.X, pady=(8, 4))

        self.lbl_status = tk.Label(
            ctrl_card,
            text="Ready. Select an audio file via 'Change file' or paste a URL.",
            font=("Segoe UI", 9),
            bg=self.colors["card_bg"],
            fg=self.colors["text_muted"]
        )
        self.lbl_status.pack(anchor="w")

        # 3. Terminal / Logs
        log_card = tk.Frame(
            main_frame,
            bg=self.colors["card_bg"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors["card_border"]
        )
        log_card.pack(fill=tk.BOTH, expand=True)

        log_top = tk.Frame(log_card, bg=self.colors["card_bg"], padx=10, pady=6)
        log_top.pack(fill=tk.X)

        tk.Label(
            log_top,
            text="📝 Transcription Output & Logs:",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["card_bg"],
            fg=self.colors["text"]
        ).pack(side=tk.LEFT)

        self.btn_open_folder = tk.Button(
            log_top,
            text="📁 Folder",
            font=("Segoe UI", 8),
            bg=self.colors["btn_sub"],
            fg=self.colors["text"],
            activebackground=self.colors["btn_sub_hover"],
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            state=tk.DISABLED,
            command=self.open_output_folder
        )
        self.btn_open_folder.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_open_txt = tk.Button(
            log_top,
            text="📄 Open .txt",
            font=("Segoe UI", 8),
            bg=self.colors["btn_sub"],
            fg=self.colors["text"],
            activebackground=self.colors["btn_sub_hover"],
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            state=tk.DISABLED,
            command=self.open_txt_file
        )
        self.btn_open_txt.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_copy = tk.Button(
            log_top,
            text="📋 Copy",
            font=("Segoe UI", 8),
            bg=self.colors["btn_sub"],
            fg=self.colors["text"],
            activebackground=self.colors["btn_sub_hover"],
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.copy_log
        )
        self.btn_copy.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_clear = tk.Button(
            log_top,
            text="🧹 Clear",
            font=("Segoe UI", 8),
            bg=self.colors["btn_sub"],
            fg=self.colors["text"],
            activebackground=self.colors["btn_sub_hover"],
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.clear_log
        )
        self.btn_clear.pack(side=tk.RIGHT)

        text_wrap = tk.Frame(log_card, bg=self.colors["log_bg"])
        text_wrap.pack(fill=tk.BOTH, expand=True)

        self.txt_log = tk.Text(
            text_wrap,
            bg=self.colors["log_bg"],
            fg=self.colors["log_fg"],
            font=("Consolas", 9),
            insertbackground=self.colors["accent"],
            selectbackground=self.colors["card_border"],
            relief="flat",
            padx=10,
            pady=8,
            wrap=tk.WORD
        )
        scrollbar = tk.Scrollbar(text_wrap, orient=tk.VERTICAL, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.txt_log.tag_config("system", foreground=self.colors["accent"])
        self.txt_log.tag_config("success", foreground=self.colors["success"])
        self.txt_log.tag_config("warning", foreground=self.colors["warning"])
        self.txt_log.tag_config("error", foreground=self.colors["error"])

    def check_ffmpeg(self):
        try:
            res = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                self.log_system("FFmpeg detected in system (PATH).")
        except FileNotFoundError:
            self.log_error("FFmpeg was NOT found in PATH! Click 'Help / OS Setup' for quick installation.")

    # --- CROSS-PLATFORM DIAGNOSTICS & SYSTEM SETUP COMMANDS ---
    def show_doctor_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("System Diagnostics & Installation Commands")
        dialog.geometry("680x560")
        dialog.minsize(620, 500)
        dialog.configure(bg=self.colors["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 340
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 280
        dialog.geometry(f"+{x}+{y}")

        pad = tk.Frame(dialog, bg=self.colors["bg"], padx=18, pady=16)
        pad.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            pad,
            text="🛠️ System Diagnostics & Installation Commands",
            font=("Segoe UI", 12, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"]
        ).pack(anchor="w", pady=(0, 10))

        status_box = tk.Frame(pad, bg=self.colors["card_bg"], padx=12, pady=10, highlightthickness=1, highlightbackground=self.colors["card_border"])
        status_box.pack(fill=tk.X, pady=(0, 12))

        accel_text = f"🟢 {self.device_display}" if self.has_accel else "🟡 Running on CPU (hardware acceleration unavailable)"
        tk.Label(status_box, text=f"• Accelerator: {accel_text}", font=("Segoe UI", 9), bg=self.colors["card_bg"], fg=self.colors["text"]).pack(anchor="w", pady=1)

        ffmpeg_installed = False
        try:
            ffmpeg_installed = (subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0)
        except Exception:
            pass
        ffmpeg_text = "🟢 FFmpeg detected" if ffmpeg_installed else "🔴 FFmpeg not found"
        tk.Label(status_box, text=f"• Media engine (FFmpeg): {ffmpeg_text}", font=("Segoe UI", 9), bg=self.colors["card_bg"], fg=self.colors["text"]).pack(anchor="w", pady=1)

        ytdlp_text = "🟢 yt-dlp installed" if YTDLP_AVAILABLE else "🔴 yt-dlp not found"
        tk.Label(status_box, text=f"• URL Downloader (yt-dlp): {ytdlp_text}", font=("Segoe UI", 9), bg=self.colors["card_bg"], fg=self.colors["text"]).pack(anchor="w", pady=1)

        tk.Label(pad, text="Terminal / Console Commands (click 'Copy'):", font=("Segoe UI", 9, "bold"), bg=self.colors["bg"], fg=self.colors["accent"]).pack(anchor="w", pady=(6, 4))

        def add_cmd_block(parent, title, cmd):
            frame = tk.Frame(parent, bg=self.colors["card_bg"], padx=10, pady=7, highlightthickness=1, highlightbackground=self.colors["card_border"])
            frame.pack(fill=tk.X, pady=3)

            tk.Label(frame, text=title, font=("Segoe UI", 8, "bold"), bg=self.colors["card_bg"], fg=self.colors["text_muted"]).pack(anchor="w")

            row = tk.Frame(frame, bg=self.colors["card_bg"])
            row.pack(fill=tk.X, pady=(2, 0))

            entry = tk.Entry(row, font=("Consolas", 9), bg=self.colors["input_bg"], fg=self.colors["accent"], relief="flat")
            entry.insert(0, cmd)
            entry.config(state="readonly")
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3, padx=(0, 8))

            def copy_this():
                self.root.clipboard_clear()
                self.root.clipboard_append(cmd)
                btn_cp.config(text="✓ Copied!", bg=self.colors["success"], fg="#11111b")
                dialog.after(1500, lambda: btn_cp.config(text="📋 Copy", bg=self.colors["btn_sub"], fg=self.colors["text"]))

            btn_cp = tk.Button(row, text="📋 Copy", font=("Segoe UI", 8), bg=self.colors["btn_sub"], fg=self.colors["text"], activebackground=self.colors["btn_sub_hover"], relief="flat", padx=10, pady=2, cursor="hand2", command=copy_this)
            btn_cp.pack(side=tk.RIGHT)

        # OS-specific setup commands
        if sys.platform == "darwin":
            # macOS
            add_cmd_block(pad, "1. Install PyTorch (Apple Silicon Metal MPS):", "pip3 install torch torchvision torchaudio")
            add_cmd_block(pad, "2. Install FFmpeg via Homebrew:", "brew install ffmpeg")
            add_cmd_block(pad, "3. Install Whisper library:", "pip3 install -U openai-whisper")
            add_cmd_block(pad, "4. Install yt-dlp (URL media downloader):", "pip3 install -U yt-dlp")
        elif sys.platform == "win32":
            # Windows
            add_cmd_block(pad, "1. Install PyTorch with CUDA (NVIDIA):", "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124")
            add_cmd_block(pad, "2. Install FFmpeg (Windows winget):", "winget install Gyan.FFmpeg")
            add_cmd_block(pad, "3. Install Whisper library:", "pip install -U openai-whisper")
            add_cmd_block(pad, "4. Install yt-dlp (URL media downloader):", "pip install -U yt-dlp")
        else:
            # Linux (Ubuntu / Debian / Arch / Fedora)
            add_cmd_block(pad, "1. Install PyTorch with CUDA (Linux NVIDIA):", "pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124")
            add_cmd_block(pad, "2. Install FFmpeg (Ubuntu / Debian):", "sudo apt update && sudo apt install -y ffmpeg")
            add_cmd_block(pad, "3. Install Whisper library:", "pip3 install -U openai-whisper")
            add_cmd_block(pad, "4. Install yt-dlp (URL media downloader):", "pip3 install -U yt-dlp")

        btn_close = tk.Button(
            pad,
            text="Close",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["btn_file"],
            fg="#ffffff",
            activebackground=self.colors["btn_file_hover"],
            relief="flat",
            pady=6,
            cursor="hand2",
            command=dialog.destroy
        )
        btn_close.pack(fill=tk.X, pady=(10, 0))

    def on_change_file(self):
        """Open file chooser dialog for local audio files."""
        filetypes = [
            ("Audio Files", "*.mp3 *.m4a *.wav *.ogg *.flac *.aac *.wma *.opus *.m4b"),
            ("All Files", "*.*")
        ]
        chosen = filedialog.askopenfilename(title="Select Audio File", filetypes=filetypes)
        if chosen:
            chosen = os.path.normpath(chosen)
            self.selected_file_path = chosen
            self.output_directory = os.path.dirname(chosen)

            filename = os.path.basename(chosen)
            self.lbl_selected_file.config(text=f"Selected: {filename}", fg=self.colors["text"], font=("Segoe UI", 9, "bold"))

            name_without_ext, _ = os.path.splitext(filename)
            default_base_name = f"{name_without_ext}_final"
            self.entry_name.delete(0, tk.END)
            self.entry_name.insert(0, default_base_name)

            # Clear URL input when a local file is picked to avoid confusion
            if hasattr(self, "entry_url"):
                self.entry_url.delete(0, tk.END)
            self.last_downloaded_url = None

            self.lbl_status.config(text=f"File ready: {filename}. Click 'Transcribe'.", fg=self.colors["accent"])
            self.log_system(f"Selected file: {chosen}")

    def on_fetch_url(self):
        """Handle click on 'Fetch Audio' button."""
        if self.is_processing:
            return

        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Enter URL", "Please enter or paste a media URL (VK Video, YouTube, Rutube, etc.) first.")
            return

        if not url.startswith(("http://", "https://")):
            messagebox.showwarning("Invalid URL", "The URL must start with http:// or https://")
            return

        if not YTDLP_AVAILABLE:
            messagebox.showerror(
                "yt-dlp Required",
                "The 'yt-dlp' library is required to download audio from URLs.\n\n"
                "Please install it in your terminal:\npip install -U yt-dlp"
            )
            return

        self.set_busy(True)
        self.lbl_status.config(text="Fetching audio from URL...", fg=self.colors["accent"])
        self.log_system(f"Initiating URL download: {url}")
        threading.Thread(target=self._fetch_url_worker, args=(url,), daemon=True).start()

    def _fetch_url_worker(self, url):
        """Worker thread to download audio from URL and populate GUI fields."""
        try:
            mp3_file, title = self.download_audio_from_url(url)
            if mp3_file and os.path.exists(mp3_file):
                self.selected_file_path = mp3_file
                self.output_directory = os.path.dirname(mp3_file)
                self.last_downloaded_url = url
                filename = os.path.basename(mp3_file)

                clean_title = title
                for ch in '<>:"/\\|?*':
                    clean_title = clean_title.replace(ch, "_")
                clean_title = clean_title.strip(". ")
                default_base_name = f"{clean_title}_final"

                self.root.after(0, lambda: [
                    self.lbl_selected_file.config(text=f"Selected (URL): {filename}", fg=self.colors["text"], font=("Segoe UI", 9, "bold")),
                    self.entry_name.delete(0, tk.END),
                    self.entry_name.insert(0, default_base_name),
                    self.lbl_status.config(text=f"Audio ready: {filename}. Click 'Transcribe'.", fg=self.colors["success"]),
                    self.btn_open_folder.config(state=tk.NORMAL)
                ])
                self.log_success(f"Audio downloaded and saved: {mp3_file}")
        except DownloadCancelledError:
            self.log_warning("Audio download was canceled.")
            self.root.after(0, lambda: self.lbl_status.config(text="Download canceled.", fg=self.colors["warning"]))
        except Exception as e:
            if not self.cancel_requested:
                err_msg = format_download_error(e)
                self.log_error(f"Failed to fetch audio from URL: {err_msg}")
                self.root.after(0, lambda msg=err_msg: [
                    self.lbl_status.config(text=f"❌ Download error: {msg.splitlines()[0][:45]}...", fg=self.colors["error"]),
                    messagebox.showerror("Download Error", f"Failed to fetch audio from URL:\n\n{msg}")
                ])
        finally:
            self.root.after(0, lambda: self.set_busy(False))

    def download_audio_from_url(self, url, custom_name=None):
        """
        Downloads audio from supported video/audio URLs (VK Video, YouTube, Rutube, etc.)
        using yt-dlp and extracts it to MP3 via FFmpeg.
        """
        if not YTDLP_AVAILABLE:
            raise RuntimeError("yt-dlp is not installed. Please install it: pip install -U yt-dlp")

        downloads_dir = self.downloads_dir
        os.makedirs(downloads_dir, exist_ok=True)

        def progress_hook(d):
            if self.cancel_requested:
                raise DownloadCancelledError("Download canceled by user.")

            status = d.get('status')
            if status == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                speed = d.get('speed', 0) or 0
                eta = d.get('eta', 0) or 0

                percent = int(downloaded * 100 / total) if total > 0 else 0
                mb_done = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024) if total > 0 else 0
                speed_mb = speed / (1024 * 1024)

                if total > 0:
                    status_msg = f"Downloading audio: {percent}% ({mb_done:.1f}/{mb_total:.1f} MB at {speed_mb:.1f} MB/s, ETA {eta}s)"
                    self.root.after(0, lambda p=percent, s=status_msg: [
                        self.progress_bar.config(mode="determinate", maximum=100, value=p),
                        self.lbl_status.config(text=s, fg=self.colors["accent"])
                    ])
                else:
                    status_msg = f"Downloading audio: {mb_done:.1f} MB at {speed_mb:.1f} MB/s"
                    self.root.after(0, lambda s=status_msg: [
                        self.progress_bar.config(mode="indeterminate"),
                        self.lbl_status.config(text=s, fg=self.colors["accent"])
                    ])

            elif status == 'finished':
                self.root.after(0, lambda: [
                    self.progress_bar.config(mode="indeterminate"),
                    self.progress_bar.start(10),
                    self.lbl_status.config(text="Converting audio to MP3 with FFmpeg...", fg=self.colors["accent"])
                ])

        outtmpl = os.path.join(downloads_dir, f"{custom_name}.%(ext)s") if custom_name else os.path.join(downloads_dir, "%(title)s.%(ext)s")

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': outtmpl,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'downloaded_audio')

            final_file = None
            if 'requested_downloads' in info and info['requested_downloads']:
                final_file = info['requested_downloads'][0].get('filepath')

            if not final_file or not os.path.exists(final_file):
                prepared = ydl.prepare_filename(info)
                candidate = os.path.splitext(prepared)[0] + ".mp3"
                if os.path.exists(candidate):
                    final_file = candidate
                elif os.path.exists(prepared):
                    final_file = prepared

            return final_file, title

    def log(self, text, tag="stdout"):
        self.txt_log.insert(tk.END, text, tag)
        self.txt_log.see(tk.END)

    def log_system(self, msg):
        self.log_queue.put((f"[SYSTEM] {msg}\n", "system"))

    def log_success(self, msg):
        self.log_queue.put((f"[SUCCESS] {msg}\n", "success"))

    def log_warning(self, msg):
        self.log_queue.put((f"[WARNING] {msg}\n", "warning"))

    def log_error(self, msg):
        self.log_queue.put((f"[ERROR] {msg}\n", "error"))

    def process_log_queue(self):
        while not self.log_queue.empty():
            try:
                msg, tag = self.log_queue.get_nowait()
                self.log(msg, tag)
            except queue.Empty:
                break
        self.root.after(100, self.process_log_queue)

    def clear_log(self):
        self.txt_log.delete("1.0", tk.END)

    def copy_log(self):
        text = self.txt_log.get("1.0", tk.END).strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.lbl_status.config(text="Text copied to clipboard!", fg=self.colors["success"])

    def open_output_folder(self):
        if self.output_directory and os.path.isdir(self.output_directory):
            open_path_in_os(self.output_directory)

    def open_txt_file(self):
        if self.last_saved_txt and os.path.exists(self.last_saved_txt):
            open_path_in_os(self.last_saved_txt)

    def set_busy(self, busy=True):
        self.is_processing = busy
        if busy:
            self.cancel_requested = False
            self.btn_transcribe.config(
                text="⏳ Processing...",
                state=tk.DISABLED,
                bg=self.colors["btn_sub"],
                fg=self.colors["text_muted"]
            )
            self.btn_stop.config(state=tk.NORMAL)
            self.btn_change_file.config(state=tk.DISABLED)
            if hasattr(self, "btn_fetch"):
                self.btn_fetch.config(state=tk.DISABLED)
            if hasattr(self, "entry_url"):
                self.entry_url.config(state=tk.DISABLED)
            self.progress_bar.config(mode="indeterminate")
            self.progress_bar.start(10)
        else:
            self.btn_transcribe.config(
                text="▶ Transcribe",
                state=tk.NORMAL,
                bg=self.colors["btn_transcribe"],
                fg=self.colors["btn_transcribe_fg"]
            )
            self.btn_stop.config(state=tk.DISABLED)
            self.btn_change_file.config(state=tk.NORMAL)
            if hasattr(self, "btn_fetch"):
                self.btn_fetch.config(state=tk.NORMAL)
            if hasattr(self, "entry_url"):
                self.entry_url.config(state=tk.NORMAL)
            self.progress_bar.stop()

    def on_stop_requested(self):
        """Gracefully cancel download or transcription."""
        if not self.is_processing:
            return
        self.cancel_requested = True
        self.log_warning("Stop requested by user...")
        self.lbl_status.config(text="Stopping process...", fg=self.colors["warning"])
        if self.ffmpeg_proc and self.ffmpeg_proc.poll() is None:
            try:
                self.ffmpeg_proc.terminate()
            except Exception:
                pass

    def on_start_transcribe(self):
        if self.is_processing:
            return

        if not DEPENDENCIES_AVAILABLE:
            messagebox.showerror("Error", f"Missing torch / whisper dependencies:\n{IMPORT_ERROR_MSG}")
            return

        url = self.entry_url.get().strip() if hasattr(self, "entry_url") else ""
        has_new_url = bool(url and url.startswith(("http://", "https://")) and url != self.last_downloaded_url)

        source_url = None
        if has_new_url or (not self.selected_file_path and url):
            if not YTDLP_AVAILABLE:
                messagebox.showerror(
                    "yt-dlp Missing",
                    "The 'yt-dlp' library is required to download audio from URLs.\n\n"
                    "Please install it with:\npip install -U yt-dlp"
                )
                return
            if not url.startswith(("http://", "https://")):
                messagebox.showwarning("Invalid URL", "The URL must start with http:// or https://")
                return
            source_url = url
        elif self.selected_file_path and not os.path.exists(self.selected_file_path):
            messagebox.showerror(
                "File Not Found",
                f"Selected audio file does not exist on disk:\n\n{self.selected_file_path}\n\nPlease choose an existing file or enter a media URL."
            )
            return
        elif not self.selected_file_path:
            messagebox.showwarning(
                "Select Audio",
                "Please select an audio file using 'Change file' or paste a media URL (VK Video, YouTube, etc.)."
            )
            return

        raw_name = self.entry_name.get().strip()
        base_name = None
        if raw_name:
            clean = raw_name
            for char in '<>:"/\\|?*':
                clean = clean.replace(char, "_")
            base_name = clean.strip(". ")

        if not base_name and self.selected_file_path:
            filename = os.path.basename(self.selected_file_path)
            name_without_ext, _ = os.path.splitext(filename)
            base_name = f"{name_without_ext}_final"

        if base_name:
            self.entry_name.delete(0, tk.END)
            self.entry_name.insert(0, base_name)

        selected_model_val = self.combo_model.get().strip()
        model_name = selected_model_val.split()[0] if selected_model_val else "turbo"

        lang = self.combo_lang.get().strip() or "ru"
        use_silence = self.var_silence.get()

        self.set_busy(True)
        self.btn_open_folder.config(state=tk.DISABLED)
        self.btn_open_txt.config(state=tk.DISABLED)

        out_dir = self.output_directory if self.output_directory else self.downloads_dir

        threading.Thread(
            target=self.run_pipeline,
            args=(self.selected_file_path, out_dir, base_name, model_name, lang, use_silence, source_url),
            daemon=True
        ).start()

    def download_model_with_progress(self, model_name):
        """Download Whisper model checkpoint with real-time GUI progress tracking."""
        if not hasattr(whisper, "_MODELS") or model_name not in whisper._MODELS:
            return True

        url = whisper._MODELS[model_name]
        info = MODEL_INFO.get(model_name, {})
        dest_filename = info.get("file", url.split("/")[-1])
        dest_path = os.path.join(self.whisper_cache_dir, dest_filename)

        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1024 * 1024:
            return True

        self.log_system(f"Model '{model_name}' not found in cache. Starting download...")
        temp_path = dest_path + ".tmp"

        self.root.after(0, lambda: self.progress_bar.config(mode="determinate", maximum=100, value=0))

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Whisper-Transcriber/CrossPlatform"})
            with urllib.request.urlopen(req) as response, open(temp_path, "wb") as out_file:
                total_size = int(response.info().get("Content-Length", 0))
                downloaded = 0
                chunk_size = 512 * 1024
                last_update = 0

                while True:
                    if self.cancel_requested:
                        out_file.close()
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        self.log_warning("Model download canceled.")
                        return False

                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    if total_size > 0 and (now - last_update > 0.15):
                        last_update = now
                        percent = int(downloaded * 100 / total_size)
                        mb_done = downloaded / (1024 * 1024)
                        mb_tot = total_size / (1024 * 1024)
                        status_str = f"Downloading {model_name}: {mb_done:.1f} of {mb_tot:.1f} MB ({percent}%)"
                        self.root.after(0, lambda p=percent, s=status_str: [
                            self.progress_bar.config(value=p),
                            self.lbl_status.config(text=s, fg=self.colors["accent"])
                        ])

            os.replace(temp_path, dest_path)
            self.log_success(f"Model '{model_name}' successfully downloaded and cached!")
            self.root.after(0, self.refresh_model_dropdown)
            return True
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            self.log_error(f"Error downloading model: {e}")
            return False

    def run_pipeline(self, source_file, out_dir, base_name, model_name, lang, use_silence, source_url=None):
        old_stdout = sys.stdout
        old_stderr = sys.stderr

        redirector = TextRedirector(self.log_queue, tag="stdout")
        sys.stdout = redirector
        sys.stderr = redirector

        t0 = time.time()
        try:
            # 0. Download from URL if requested
            if source_url and (not source_file or not os.path.exists(source_file)):
                self.lbl_status.config(text="Downloading audio from URL...", fg=self.colors["accent"])
                self.log_system(f"Downloading audio from URL: {source_url}")
                try:
                    mp3_file, title = self.download_audio_from_url(source_url, custom_name=base_name)
                except DownloadCancelledError:
                    self.log_warning("Audio download was canceled.")
                    return
                except Exception as dl_err:
                    formatted_err = format_download_error(dl_err)
                    raise RuntimeError(formatted_err)

                if self.cancel_requested or not mp3_file or not os.path.exists(mp3_file):
                    return
                source_file = mp3_file
                out_dir = os.path.dirname(mp3_file)
                self.selected_file_path = mp3_file
                self.output_directory = out_dir
                self.last_downloaded_url = source_url

                if not base_name or base_name == "transcription_final":
                    clean_title = title
                    for ch in '<>:"/\\|?*':
                        clean_title = clean_title.replace(ch, "_")
                    clean_title = clean_title.strip(". ")
                    base_name = f"{clean_title}_final"
                    self.root.after(0, lambda n=base_name: [
                        self.entry_name.delete(0, tk.END),
                        self.entry_name.insert(0, n)
                    ])

                self.root.after(0, lambda fn=os.path.basename(mp3_file): self.lbl_selected_file.config(
                    text=f"Selected (URL): {fn}", fg=self.colors["text"], font=("Segoe UI", 9, "bold")
                ))

            if not source_file or not os.path.exists(source_file):
                raise RuntimeError("No valid audio file available for transcription.")

            if not base_name:
                filename = os.path.basename(source_file)
                name_without_ext, _ = os.path.splitext(filename)
                base_name = f"{name_without_ext}_final"

            self.lbl_status.config(text="Preparing audio file...", fg=self.colors["accent"])
            self.log_system(f"Starting processing: {os.path.basename(source_file)}")
            self.log_system(f"Outputs: {base_name}.txt and {base_name}.json")

            target_audio = source_file
            cleaned_audio = os.path.join(out_dir, f"{base_name}_cleaned.wav")

            # 1. FFmpeg preprocessing
            if use_silence:
                if self.cancel_requested:
                    return

                if not os.path.exists(cleaned_audio):
                    self.lbl_status.config(text="FFmpeg: trimming pauses and silence...", fg=self.colors["accent"])
                    self.log_system("Removing silence and converting to 16 kHz mono...")

                    ffmpeg_cmd = [
                        "ffmpeg", "-y", "-i", source_file,
                        "-ac", "1",
                        "-ar", "16000",
                        "-af", "silenceremove=start_periods=1:start_silence=0.3:start_threshold=-35dB:detection=peak",
                        cleaned_audio
                    ]
                    flags = get_subprocess_creation_flags()
                    try:
                        self.ffmpeg_proc = subprocess.Popen(
                            ffmpeg_cmd,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE,
                            creationflags=flags
                        )
                        _, stderr_bytes = self.ffmpeg_proc.communicate()
                    except FileNotFoundError:
                        self.log_error("FFmpeg not found in PATH! Click 'Help / OS Setup' for quick installation.")
                        raise RuntimeError("FFmpeg not found. Please install FFmpeg.")

                    if self.cancel_requested:
                        self.log_warning("Process canceled during FFmpeg preprocessing.")
                        if os.path.exists(cleaned_audio):
                            os.remove(cleaned_audio)
                        return

                    if self.ffmpeg_proc.returncode == 0:
                        self.log_success(f"Audio preprocessed: {os.path.basename(cleaned_audio)}")
                        target_audio = cleaned_audio
                    else:
                        err_text = stderr_bytes.decode("utf-8", errors="ignore")
                        self.log_warning(f"FFmpeg returned warning: {err_text[:120]}")
                        target_audio = source_file
                else:
                    self.log_system(f"Using pre-existing cleaned file: {os.path.basename(cleaned_audio)}")
                    target_audio = cleaned_audio
            else:
                target_audio = source_file

            if self.cancel_requested:
                return

            # 2. Check and download model
            if not self.is_model_cached(model_name):
                download_ok = self.download_model_with_progress(model_name)
                if not download_ok or self.cancel_requested:
                    return

            self.root.after(0, lambda: [
                self.progress_bar.config(mode="indeterminate"),
                self.progress_bar.start(10)
            ])

            # 3. Load model into memory and manage VRAM / Metal
            device = self.device_str

            if self.loaded_model is not None and self.loaded_model_name != model_name:
                self.log_system(f"Unloading previous model '{self.loaded_model_name}' from memory...")
                del self.loaded_model
                self.loaded_model = None
                if device == "cuda":
                    torch.cuda.empty_cache()
                elif device == "mps" and hasattr(torch, "mps"):
                    torch.mps.empty_cache()

            if self.loaded_model is None:
                self.lbl_status.config(text=f"Loading model '{model_name}' on {device.upper()}...", fg=self.colors["accent"])
                self.log_system(f"Loading model '{model_name}' into memory...")
                try:
                    self.loaded_model = whisper.load_model(model_name, device=device)
                    self.loaded_model_name = model_name
                    self.log_system(f"Model '{model_name}' ready on {device.upper()}!")
                except Exception as load_err:
                    if device != "cpu":
                        self.log_warning(f"Failed to initialize {device.upper()}: {load_err}. Falling back to CPU...")
                        device = "cpu"
                        self.device_str = "cpu"
                        self.loaded_model = whisper.load_model(model_name, device="cpu")
                        self.loaded_model_name = model_name
                        self.log_system(f"Model '{model_name}' successfully loaded on CPU!")
                    else:
                        raise load_err
            else:
                self.log_system(f"Model '{model_name}' already active in memory.")

            if self.cancel_requested:
                return

            # 4. Whisper transcription
            self.lbl_status.config(text="Transcribing... Live segments stream below.", fg=self.colors["accent"])
            self.log_system(f"Transcribing (language: {lang}). Streamed transcript:")
            self.log_system("-" * 60)

            t_trans = time.time()
            transcribe_kwargs = {
                "audio": target_audio,
                "condition_on_previous_text": False,
                "verbose": True,
                "fp16": (device == "cuda")
            }
            if lang and lang != "auto":
                transcribe_kwargs["language"] = lang

            result = self.loaded_model.transcribe(**transcribe_kwargs)

            if self.cancel_requested:
                self.log_warning("Transcription stopped by user.")
                return

            self.log_system("-" * 60)
            elapsed_trans = round(time.time() - t_trans, 2)
            self.log_success(f"Recognition completed in: {elapsed_trans} s.")

            # 5. Atomic file persistence
            txt_path = os.path.join(out_dir, f"{base_name}.txt")
            json_path = os.path.join(out_dir, f"{base_name}.json")

            tmp_txt = txt_path + ".tmp"
            tmp_json = json_path + ".tmp"

            with open(tmp_txt, "w", encoding="utf-8") as f:
                f.write(result.get("text", ""))

            with open(tmp_json, "w", encoding="utf-8") as f:
                json.dump(result.get("segments", []), f, ensure_ascii=False, indent=2)

            os.replace(tmp_txt, txt_path)
            os.replace(tmp_json, json_path)

            self.log_success(f"Files saved successfully:\n{txt_path}\n{json_path}")
            self.last_saved_txt = txt_path

            total_elapsed = round(time.time() - t0, 2)
            self.log_success(f"🎉 Complete! Total elapsed time: {total_elapsed} s.")

            self.root.after(0, lambda: [
                self.lbl_status.config(text=f"✅ Complete in {total_elapsed} s!", fg=self.colors["success"]),
                self.btn_open_folder.config(state=tk.NORMAL),
                self.btn_open_txt.config(state=tk.NORMAL)
            ])

        except Exception as e:
            if not self.cancel_requested:
                err_str = str(e)
                self.log_error(f"Error: {err_str}")
                self.root.after(0, lambda: [
                    self.lbl_status.config(text=f"❌ Error: {err_str}", fg=self.colors["error"]),
                    messagebox.showerror("Error", err_str)
                ])
            else:
                self.log_warning("Process was stopped.")
                self.root.after(0, lambda: self.lbl_status.config(text="Process stopped.", fg=self.colors["warning"]))
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.ffmpeg_proc = None
            self.root.after(0, lambda: self.set_busy(False))


def main():
    root = tk.Tk()
    app = TranscriberApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
