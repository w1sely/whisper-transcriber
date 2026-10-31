@echo off
chcp 65001 > nul
cd /d "%~dp0.."
echo ====================================================
echo  Building Whisper Transcriber for Windows (.exe)
echo ====================================================

pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed --name "Transcriber" --collect-all whisper src\app.py

if exist "dist\Transcriber\Transcriber.exe" (
    echo.
    echo [SUCCESS] Executable successfully built: dist\Transcriber\Transcriber.exe
) else (
    echo.
    echo [ERROR] Build failed.
)
pause
