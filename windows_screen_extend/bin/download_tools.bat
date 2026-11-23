@echo off
setlocal
cd /d "%~dp0"
title Tool Downloader (FFmpeg & ADB)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python download_tools.py
    pause
    exit /b %ERRORLEVEL%
)

if exist "C:\Platform-tool\platform-tools\python.exe" (
    "C:\Platform-tool\platform-tools\python.exe" download_tools.py
    pause
    exit /b %ERRORLEVEL%
)

echo [ERROR] Python is required to run this script.
echo Please install Python from https://python.org/
pause
exit /b 1
