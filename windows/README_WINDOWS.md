# 🪟 Whisper Transcriber — Windows Guide

## Быстрый запуск
* **Готовый .exe:** Запустите `dist\Transcriber\Transcriber.exe` или ярлык `Transcriber.lnk`.
* **Из командной строки:** Запустите `windows\run.bat` или `python app.py`.

## Требования
* Windows 10 / 11 (64-bit).
* Видеокарта NVIDIA (GeForce RTX 20/30/40/50 серии) для аппаратного ускорения CUDA (либо процессор).
* FFmpeg: установить командой `winget install Gyan.FFmpeg`.

## Сборка .exe файла
Для повторной компиляции исполняемого файла запустите:
```cmd
windows\build_exe.bat
```
Файл будет собран в папку `dist\Transcriber\`.
