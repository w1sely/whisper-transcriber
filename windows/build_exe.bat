@echo off
chcp 65001 > nul
cd /d "%~dp0.."
echo ====================================================
echo  Сборка Whisper Transcriber для Windows (.exe)
echo ====================================================

pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed --name "Transcriber" --collect-all whisper src\app.py

if exist "dist\Transcriber\Transcriber.exe" (
    echo.
    echo [УСПЕХ] Исполняемый файл успешно собран в: dist\Transcriber\Transcriber.exe
) else (
    echo.
    echo [ОШИБКА] Не удалось собрать исполняемый файл.
)
pause
