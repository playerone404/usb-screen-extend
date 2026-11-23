@echo off
setlocal
cd /d "%~dp0"
title Virtual Display Setup

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python "driver\setup_virtual_display.py"
    goto done
)

if exist "C:\Platform-tool\platform-tools\python.exe" (
    "C:\Platform-tool\platform-tools\python.exe" "driver\setup_virtual_display.py"
    goto done
)

echo [ERROR] Python was not found in PATH!
pause
exit /b 1

:done
pause
