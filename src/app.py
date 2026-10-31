#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Whisper Transcriber - Cross-Platform GUI Audio Transcription
Supports: Windows (CUDA/CPU), Linux (CUDA/ROCm/CPU), macOS (Apple Silicon Metal/MPS/CPU).
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

# Попытка импорта torch и whisper
try:
    import torch
    import whisper
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    IMPORT_ERROR_MSG = str(e)


# Описание моделей Whisper и их размеры
MODEL_INFO = {
    "turbo": {"file": "large-v3-turbo.pt", "size": "1.5 ГБ", "desc": "Оптимальная (быстрая и точная)"},
    "large-v3": {"file": "large-v3.pt", "size": "2.9 ГБ", "desc": "Максимальная точность"},
    "medium": {"file": "medium.pt", "size": "1.4 ГБ", "desc": "Средняя точность"},
    "small": {"file": "small.pt", "size": "460 МБ", "desc": "Легкая модель"},
    "base": {"file": "base.pt", "size": "140 МБ", "desc": "Базовая быстрая"},
    "tiny": {"file": "tiny.pt", "size": "75 МБ", "desc": "Сверхлегкая"},
}


def open_path_in_os(path):
    """Кроссплатформенное открытие папки или файла в системном проводнике."""
    if not os.path.exists(path):
        return
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            # Linux и другие Unix-подобные ОС
            subprocess.run(["xdg-open", path], check=False)
    except Exception as e:
        print(f"Не удалось открыть путь {path}: {e}")


def get_subprocess_creation_flags():
    """Флаги для скрытия лишних консольных окон (Windows NT)."""
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


class TextRedirector:
    """Перенаправляет stdout/stderr в очередь GUI для отображения логов в реальном времени."""
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
        
        # --- СТАНДАРТНОЕ ОКНО СИСТЕМЫ (OS WINDOW) ---
        self.root.title("Whisper Transcriber (Cross-Platform)")
        self.root.geometry("760x700")
        self.root.minsize(680, 580)
        
        # Перехват закрытия окна на крестик
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.center_window()

        self.log_queue = queue.Queue()
        self.is_processing = False
        self.cancel_requested = False
        self.loaded_model = None
        self.loaded_model_name = None
        self.ffmpeg_proc = None

        # Папка кэша Whisper (стандартно ~/.cache/whisper на всех ОС)
        self.whisper_cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "whisper")
        os.makedirs(self.whisper_cache_dir, exist_ok=True)

        # --- КРОСС-ПЛАТФОРМЕННОЕ ОПРЕДЕЛЕНИЕ ОБОРУДОВАНИЯ ---
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
            self.device_display = "Ошибка: не найдены torch / whisper"

        # Цветовая гамма (Modern Dark Theme)
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

        # Запуск цикла чтения очереди логов
        self.root.after(100, self.process_log_queue)
        os_name = "macOS" if sys.platform == "darwin" else ("Windows" if sys.platform == "win32" else "Linux")
        self.log_system(f"Платформа: {os_name} | Аппаратное ускорение: {self.device_display}")
        self.check_ffmpeg()

    def center_window(self):
        self.root.update_idletasks()
        w, h = 760, 700
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def on_closing(self):
        """Полное и безопасное закрытие приложения по нажатию на системный крестик."""
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
        """Проверяет наличие файла модели в локальном кэше."""
        info = MODEL_INFO.get(model_key)
        if not info:
            return False
        cache_path = os.path.join(self.whisper_cache_dir, info["file"])
        return os.path.exists(cache_path) and os.path.getsize(cache_path) > 1024 * 1024

    def get_model_combobox_values(self):
        """Формирует список моделей с пометками о наличии."""
        values = []
        for key, info in MODEL_INFO.items():
            if self.is_model_cached(key):
                status = f"✓ Скачана ({info['size']})"
            else:
                status = f"⬇ Скачать ({info['size']})"
            values.append(f"{key} [{status}]")
        return values

    def refresh_model_dropdown(self):
        """Обновляет статус моделей в выпадающем списке."""
        current_selection = self.combo_model.get().split()[0] if self.combo_model.get() else "turbo"
        values = self.get_model_combobox_values()
        self.combo_model['values'] = values
        for val in values:
            if val.startswith(current_selection + " "):
                self.combo_model.set(val)
                break

    def build_ui(self):
        main_frame = tk.Frame(self.root, bg=self.colors["bg"], padx=18, pady=14)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Шапка: Заголовок + Справка + Индикатор ускорения
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
            text="ℹ️ Справка / Команды ОС",
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

        # 2. Карточка управления
        ctrl_card = tk.Frame(
            main_frame,
            bg=self.colors["card_bg"],
            padx=16,
            pady=14,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors["card_border"]
        )
        ctrl_card.pack(fill=tk.X, pady=(0, 10))

        # Выбор файла
        file_row = tk.Frame(ctrl_card, bg=self.colors["card_bg"])
        file_row.pack(fill=tk.X, pady=(0, 10))

        self.btn_change_file = tk.Button(
            file_row,
            text="📁 Change file",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["btn_file"],
            fg="#ffffff",
            activebackground=self.colors["btn_file_hover"],
            activeforeground="#ffffff",
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
            command=self.on_change_file
        )
        self.btn_change_file.pack(side=tk.LEFT, padx=(0, 12))

        self.lbl_selected_file = tk.Label(
            file_row,
            text="Файл не выбран. Нажмите «Change file»...",
            font=("Segoe UI", 9, "italic"),
            bg=self.colors["card_bg"],
            fg=self.colors["text_muted"],
            anchor="w"
        )
        self.lbl_selected_file.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Поле имени
        name_label_row = tk.Frame(ctrl_card, bg=self.colors["card_bg"])
        name_label_row.pack(fill=tk.X, pady=(2, 2))

        tk.Label(
            name_label_row,
            text="Change name (имя итогового файла без расширения):",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["card_bg"],
            fg=self.colors["text"]
        ).pack(side=tk.LEFT)

        self.lbl_save_hint = tk.Label(
            name_label_row,
            text="Создаст: <имя>.txt и <имя>.json",
            font=("Segoe UI", 8),
            bg=self.colors["card_bg"],
            fg=self.colors["text_muted"]
        )
        self.lbl_save_hint.pack(side=tk.RIGHT)

        name_entry_row = tk.Frame(ctrl_card, bg=self.colors["card_bg"])
        name_entry_row.pack(fill=tk.X, pady=(0, 10))

        self.entry_name = tk.Entry(
            name_entry_row,
            font=("Segoe UI", 11, "bold"),
            bg=self.colors["input_bg"],
            fg=self.colors["accent"],
            insertbackground=self.colors["accent"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors["card_border"]
        )
        self.entry_name.pack(fill=tk.X, ipady=6)

        # Опции
        opts_row = tk.Frame(ctrl_card, bg=self.colors["card_bg"])
        opts_row.pack(fill=tk.X, pady=(0, 10))

        tk.Label(opts_row, text="Модель:", font=("Segoe UI", 9), bg=self.colors["card_bg"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(0, 4))
        self.combo_model = ttk.Combobox(
            opts_row,
            values=self.get_model_combobox_values(),
            state="readonly",
            width=26,
            font=("Segoe UI", 9)
        )
        self.refresh_model_dropdown()
        self.combo_model.pack(side=tk.LEFT, padx=(0, 14))

        tk.Label(opts_row, text="Язык:", font=("Segoe UI", 9), bg=self.colors["card_bg"], fg=self.colors["text"]).pack(side=tk.LEFT, padx=(0, 4))
        self.combo_lang = ttk.Combobox(opts_row, values=["ru", "en", "auto"], width=6, font=("Segoe UI", 9))
        self.combo_lang.set("ru")
        self.combo_lang.pack(side=tk.LEFT, padx=(0, 14))

        self.var_silence = tk.BooleanVar(value=True)
        self.chk_silence = tk.Checkbutton(
            opts_row,
            text="FFmpeg вырезка тишины",
            variable=self.var_silence,
            font=("Segoe UI", 9),
            bg=self.colors["card_bg"],
            fg=self.colors["text"],
            activebackground=self.colors["card_bg"],
            selectcolor=self.colors["input_bg"]
        )
        self.chk_silence.pack(side=tk.LEFT)

        # Действия (Transcribe + Stop)
        act_row = tk.Frame(ctrl_card, bg=self.colors["card_bg"])
        act_row.pack(fill=tk.X, pady=(2, 0))

        self.btn_transcribe = tk.Button(
            act_row,
            text="▶ Transcribe",
            font=("Segoe UI", 12, "bold"),
            bg=self.colors["btn_transcribe"],
            fg=self.colors["btn_transcribe_fg"],
            activebackground=self.colors["btn_transcribe_hover"],
            activeforeground=self.colors["btn_transcribe_fg"],
            relief="flat",
            pady=8,
            cursor="hand2",
            command=self.on_start_transcribe
        )
        self.btn_transcribe.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.btn_stop = tk.Button(
            act_row,
            text="⏹ Стоп",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["btn_stop"],
            fg=self.colors["btn_stop_fg"],
            relief="flat",
            padx=16,
            pady=8,
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
            text="Готов к работе. Выберите файл через «Change file»",
            font=("Segoe UI", 9),
            bg=self.colors["card_bg"],
            fg=self.colors["text_muted"]
        )
        self.lbl_status.pack(anchor="w")

        # 3. Терминал / Лог
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
            text="📝 Результат и журнал транскрибации:",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["card_bg"],
            fg=self.colors["text"]
        ).pack(side=tk.LEFT)

        self.btn_open_folder = tk.Button(
            log_top,
            text="📁 Папка",
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
            text="📄 Открыть .txt",
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
            text="📋 Копировать",
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
            text="🧹 Очистить",
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

        self.selected_file_path = None
        self.output_directory = None
        self.last_saved_txt = None

    def check_ffmpeg(self):
        try:
            res = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                self.log_system("FFmpeg обнаружен в системе (PATH).")
        except FileNotFoundError:
            self.log_error("FFmpeg НЕ найден в PATH! Нажмите кнопку «Справка / Команды ОС» для быстрой установки.")

    # --- КРОСС-ПЛАТФОРМЕННАЯ ДИАГНОСТИКА И КОМАНДЫ ДЛЯ СИСТЕМЫ ---
    def show_doctor_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Диагностика системы и команды установки")
        dialog.geometry("660x540")
        dialog.minsize(600, 480)
        dialog.configure(bg=self.colors["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 330
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 270
        dialog.geometry(f"+{x}+{y}")

        pad = tk.Frame(dialog, bg=self.colors["bg"], padx=18, pady=16)
        pad.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            pad,
            text="🛠️ Команды установки для вашей операционной системы",
            font=("Segoe UI", 12, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"]
        ).pack(anchor="w", pady=(0, 10))

        status_box = tk.Frame(pad, bg=self.colors["card_bg"], padx=12, pady=10, highlightthickness=1, highlightbackground=self.colors["card_border"])
        status_box.pack(fill=tk.X, pady=(0, 12))

        accel_text = f"🟢 {self.device_display}" if self.has_accel else "🟡 Работает на CPU (аппаратное ускорение не задействовано)"
        tk.Label(status_box, text=f"• Ускоритель: {accel_text}", font=("Segoe UI", 9), bg=self.colors["card_bg"], fg=self.colors["text"]).pack(anchor="w", pady=1)

        ffmpeg_installed = False
        try:
            ffmpeg_installed = (subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0)
        except Exception:
            pass
        ffmpeg_text = "🟢 FFmpeg обнаружен" if ffmpeg_installed else "🔴 FFmpeg не найден"
        tk.Label(status_box, text=f"• Медиа-библиотека: {ffmpeg_text}", font=("Segoe UI", 9), bg=self.colors["card_bg"], fg=self.colors["text"]).pack(anchor="w", pady=1)

        tk.Label(pad, text="Команды для Терминала / Консоли (кликните «Копировать»):", font=("Segoe UI", 9, "bold"), bg=self.colors["bg"], fg=self.colors["accent"]).pack(anchor="w", pady=(6, 4))

        def add_cmd_block(parent, title, cmd):
            frame = tk.Frame(parent, bg=self.colors["card_bg"], padx=10, pady=8, highlightthickness=1, highlightbackground=self.colors["card_border"])
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
                btn_cp.config(text="✓ Скопировано!", bg=self.colors["success"], fg="#11111b")
                dialog.after(1500, lambda: btn_cp.config(text="📋 Копировать", bg=self.colors["btn_sub"], fg=self.colors["text"]))

            btn_cp = tk.Button(row, text="📋 Копировать", font=("Segoe UI", 8), bg=self.colors["btn_sub"], fg=self.colors["text"], activebackground=self.colors["btn_sub_hover"], relief="flat", padx=10, pady=2, cursor="hand2", command=copy_this)
            btn_cp.pack(side=tk.RIGHT)

        # Команды зависят от ОС
        if sys.platform == "darwin":
            # macOS
            add_cmd_block(pad, "1. Установка PyTorch (с поддержкой Apple Silicon Metal MPS):", "pip3 install torch torchvision torchaudio")
            add_cmd_block(pad, "2. Установка FFmpeg через Homebrew:", "brew install ffmpeg")
            add_cmd_block(pad, "3. Установка библиотеки Whisper:", "pip3 install -U openai-whisper")
        elif sys.platform == "win32":
            # Windows
            add_cmd_block(pad, "1. Установка PyTorch с CUDA (NVIDIA):", "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124")
            add_cmd_block(pad, "2. Установка FFmpeg (Windows winget):", "winget install Gyan.FFmpeg")
            add_cmd_block(pad, "3. Установка библиотеки Whisper:", "pip install -U openai-whisper")
        else:
            # Linux (Ubuntu / Debian / Arch / Fedora)
            add_cmd_block(pad, "1. Установка PyTorch с CUDA (Linux NVIDIA):", "pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124")
            add_cmd_block(pad, "2. Установка FFmpeg (Ubuntu / Debian):", "sudo apt update && sudo apt install -y ffmpeg")
            add_cmd_block(pad, "3. Установка FFmpeg (Arch Linux / Manjaro):", "sudo pacman -S ffmpeg")
            add_cmd_block(pad, "4. Установка Whisper:", "pip3 install -U openai-whisper")

        btn_close = tk.Button(
            pad,
            text="Закрыть",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["btn_file"],
            fg="#ffffff",
            activebackground=self.colors["btn_file_hover"],
            relief="flat",
            pady=6,
            cursor="hand2",
            command=dialog.destroy
        )
        btn_close.pack(fill=tk.X, pady=(12, 0))

    def on_change_file(self):
        """Открытие диалога выбора файла."""
        filetypes = [
            ("Аудиофайлы", "*.mp3 *.m4a *.wav *.ogg *.flac *.aac *.wma *.opus *.m4b"),
            ("Все файлы", "*.*")
        ]
        chosen = filedialog.askopenfilename(title="Выберите аудиофайл", filetypes=filetypes)
        if chosen:
            chosen = os.path.normpath(chosen)
            self.selected_file_path = chosen
            self.output_directory = os.path.dirname(chosen)

            filename = os.path.basename(chosen)
            self.lbl_selected_file.config(text=f"Выбран: {filename}", fg=self.colors["text"], font=("Segoe UI", 9, "bold"))

            name_without_ext, _ = os.path.splitext(filename)
            default_base_name = f"{name_without_ext}_final"
            self.entry_name.delete(0, tk.END)
            self.entry_name.insert(0, default_base_name)

            self.lbl_status.config(text=f"Файл готов: {filename}. Нажмите «Transcribe».", fg=self.colors["accent"])
            self.log_system(f"Выбран файл: {chosen}")

    def log(self, text, tag="stdout"):
        self.txt_log.insert(tk.END, text, tag)
        self.txt_log.see(tk.END)

    def log_system(self, msg):
        self.log_queue.put((f"[СИСТЕМА] {msg}\n", "system"))

    def log_success(self, msg):
        self.log_queue.put((f"[ГОТОВО] {msg}\n", "success"))

    def log_warning(self, msg):
        self.log_queue.put((f"[ВНИМАНИЕ] {msg}\n", "warning"))

    def log_error(self, msg):
        self.log_queue.put((f"[ОШИБКА] {msg}\n", "error"))

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
            self.lbl_status.config(text="Текст скопирован в буфер обмена!", fg=self.colors["success"])

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
                text="⏳ Идет транскрибация...",
                state=tk.DISABLED,
                bg=self.colors["btn_sub"],
                fg=self.colors["text_muted"]
            )
            self.btn_stop.config(state=tk.NORMAL)
            self.btn_change_file.config(state=tk.DISABLED)
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
            self.progress_bar.stop()

    def on_stop_requested(self):
        """Мягкая отмена транскрибации."""
        if not self.is_processing:
            return
        self.cancel_requested = True
        self.log_warning("Запрошена остановка процесса пользователем...")
        self.lbl_status.config(text="Остановка процесса...", fg=self.colors["warning"])
        if self.ffmpeg_proc and self.ffmpeg_proc.poll() is None:
            try:
                self.ffmpeg_proc.terminate()
            except Exception:
                pass

    def on_start_transcribe(self):
        if self.is_processing:
            return

        if not DEPENDENCIES_AVAILABLE:
            messagebox.showerror("Ошибка", f"Не найдены зависимости torch / whisper:\n{IMPORT_ERROR_MSG}")
            return

        if not self.selected_file_path or not os.path.exists(self.selected_file_path):
            messagebox.showwarning("Выберите файл", "Сначала выберите файл через кнопку «Change file».")
            return

        raw_name = self.entry_name.get().strip()
        if not raw_name:
            filename = os.path.basename(self.selected_file_path)
            name_without_ext, _ = os.path.splitext(filename)
            raw_name = f"{name_without_ext}_final"

        # Строгая кросс-платформенная санитизация
        base_name = os.path.basename(raw_name)
        for char in '<>:"/\\|?*':
            base_name = base_name.replace(char, "_")
        base_name = base_name.strip(". ")
        if not base_name:
            base_name = "transcription_final"
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, base_name)

        selected_model_val = self.combo_model.get().strip()
        model_name = selected_model_val.split()[0] if selected_model_val else "turbo"

        lang = self.combo_lang.get().strip() or "ru"
        use_silence = self.var_silence.get()

        self.set_busy(True)
        self.btn_open_folder.config(state=tk.DISABLED)
        self.btn_open_txt.config(state=tk.DISABLED)

        threading.Thread(
            target=self.run_pipeline,
            args=(self.selected_file_path, self.output_directory, base_name, model_name, lang, use_silence),
            daemon=True
        ).start()

    def download_model_with_progress(self, model_name):
        """Скачивает модель из OpenAI с отображением реального прогресса в GUI."""
        if not hasattr(whisper, "_MODELS") or model_name not in whisper._MODELS:
            return True

        url = whisper._MODELS[model_name]
        info = MODEL_INFO.get(model_name, {})
        dest_filename = info.get("file", url.split("/")[-1])
        dest_path = os.path.join(self.whisper_cache_dir, dest_filename)

        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1024 * 1024:
            return True

        self.log_system(f"Модель '{model_name}' отсутствует в кэше. Начинаем загрузку...")
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
                        self.log_warning("Загрузка модели отменена.")
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
                        status_str = f"Загрузка {model_name}: {mb_done:.1f} из {mb_tot:.1f} МБ ({percent}%)"
                        self.root.after(0, lambda p=percent, s=status_str: [
                            self.progress_bar.config(value=p),
                            self.lbl_status.config(text=s, fg=self.colors["accent"])
                        ])

            os.replace(temp_path, dest_path)
            self.log_success(f"Модель '{model_name}' скачана и сохранена в кэш!")
            self.root.after(0, self.refresh_model_dropdown)
            return True
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            self.log_error(f"Ошибка загрузки модели: {e}")
            return False

    def run_pipeline(self, source_file, out_dir, base_name, model_name, lang, use_silence):
        old_stdout = sys.stdout
        old_stderr = sys.stderr

        redirector = TextRedirector(self.log_queue, tag="stdout")
        sys.stdout = redirector
        sys.stderr = redirector

        t0 = time.time()
        try:
            self.lbl_status.config(text="Подготовка аудиофайла...", fg=self.colors["accent"])
            self.log_system(f"Старт обработки: {os.path.basename(source_file)}")
            self.log_system(f"Результаты: {base_name}.txt и {base_name}.json")

            target_audio = source_file
            cleaned_audio = os.path.join(out_dir, f"{base_name}_cleaned.wav")

            # 1. FFmpeg
            if use_silence:
                if self.cancel_requested:
                    return

                if not os.path.exists(cleaned_audio):
                    self.lbl_status.config(text="FFmpeg: вырезка пауз и тишины...", fg=self.colors["accent"])
                    self.log_system("Вырезаем тишину и конвертируем в моно 16 кГц...")

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
                        self.log_error("FFmpeg не обнаружен в системе (PATH)! Нажмите кнопку «Справка / Команды ОС» для быстрой установки.")
                        raise RuntimeError("FFmpeg не найден. Пожалуйста, установите FFmpeg.")

                    if self.cancel_requested:
                        self.log_warning("Процесс отменен во время работы FFmpeg.")
                        if os.path.exists(cleaned_audio):
                            os.remove(cleaned_audio)
                        return

                    if self.ffmpeg_proc.returncode == 0:
                        self.log_success(f"Аудио очищено: {os.path.basename(cleaned_audio)}")
                        target_audio = cleaned_audio
                    else:
                        err_text = stderr_bytes.decode("utf-8", errors="ignore")
                        self.log_warning(f"FFmpeg вернул предупреждение: {err_text[:120]}")
                        target_audio = source_file
                else:
                    self.log_system(f"Используем готовый очищенный файл: {os.path.basename(cleaned_audio)}")
                    target_audio = cleaned_audio
            else:
                target_audio = source_file

            if self.cancel_requested:
                return

            # 2. Проверка и скачивание модели
            if not self.is_model_cached(model_name):
                download_ok = self.download_model_with_progress(model_name)
                if not download_ok or self.cancel_requested:
                    return

            self.root.after(0, lambda: [
                self.progress_bar.config(mode="indeterminate"),
                self.progress_bar.start(10)
            ])

            # 3. Загрузка в память и освобождение VRAM / Metal
            device = self.device_str

            if self.loaded_model is not None and self.loaded_model_name != model_name:
                self.log_system(f"Выгрузка из памяти предыдущей модели '{self.loaded_model_name}'...")
                del self.loaded_model
                self.loaded_model = None
                if device == "cuda":
                    torch.cuda.empty_cache()
                elif device == "mps" and hasattr(torch, "mps"):
                    torch.mps.empty_cache()

            if self.loaded_model is None:
                self.lbl_status.config(text=f"Загрузка модели '{model_name}' на {device.upper()}...", fg=self.colors["accent"])
                self.log_system(f"Загружаем модель '{model_name}' в память...")
                try:
                    self.loaded_model = whisper.load_model(model_name, device=device)
                    self.loaded_model_name = model_name
                    self.log_system(f"Модель '{model_name}' готова к работе на {device.upper()}!")
                except Exception as load_err:
                    if device != "cpu":
                        self.log_warning(f"Не удалось инициализировать {device.upper()}: {load_err}. Автоматический переход на CPU...")
                        device = "cpu"
                        self.device_str = "cpu"
                        self.loaded_model = whisper.load_model(model_name, device="cpu")
                        self.loaded_model_name = model_name
                        self.log_system(f"Модель '{model_name}' успешно загружена на CPU!")
                    else:
                        raise load_err
            else:
                self.log_system(f"Модель '{model_name}' уже готова в памяти.")

            if self.cancel_requested:
                return

            # 4. Транскрибация Whisper
            self.lbl_status.config(text="Транскрибация... Текст выводится в реальном времени.", fg=self.colors["accent"])
            self.log_system(f"Транскрибируем (язык: {lang}). Текст записи:")
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
                self.log_warning("Транскрибация прервана пользователем.")
                return

            self.log_system("-" * 60)
            elapsed_trans = round(time.time() - t_trans, 2)
            self.log_success(f"Распознавание завершено за: {elapsed_trans} сек.")

            # 5. Атомарное сохранение результатов
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

            self.log_success(f"Файлы сохранены:\n{txt_path}\n{json_path}")
            self.last_saved_txt = txt_path

            total_elapsed = round(time.time() - t0, 2)
            self.log_success(f"🎉 Готово! Всего времени: {total_elapsed} сек.")

            self.root.after(0, lambda: [
                self.lbl_status.config(text=f"✅ Готово за {total_elapsed} с!", fg=self.colors["success"]),
                self.btn_open_folder.config(state=tk.NORMAL),
                self.btn_open_txt.config(state=tk.NORMAL)
            ])

        except Exception as e:
            if not self.cancel_requested:
                err_str = str(e)
                self.log_error(f"Ошибка: {err_str}")
                self.root.after(0, lambda: [
                    self.lbl_status.config(text=f"❌ Ошибка: {err_str}", fg=self.colors["error"]),
                    messagebox.showerror("Ошибка", err_str)
                ])
            else:
                self.log_warning("Процесс был остановлен.")
                self.root.after(0, lambda: self.lbl_status.config(text="Процесс остановлен.", fg=self.colors["warning"]))
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
