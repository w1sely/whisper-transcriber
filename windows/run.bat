@echo off
chcp 65001 > nul
cd /d "%~dp0.."
echo Starting Whisper Transcriber...

if exist "dist\Transcriber\Transcriber.exe" (
    start "" "dist\Transcriber\Transcriber.exe"
) else (
    start "" pythonw app.py
    if errorlevel 1 (
        python app.py
        pause
    )
)
