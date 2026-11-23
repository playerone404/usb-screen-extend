@echo off
setlocal
cd /d "%~dp0"
title USB Second Screen Console

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python "core\server.py" %*
    goto end
)

if exist "C:\Platform-tool\platform-tools\python.exe" (
    "C:\Platform-tool\platform-tools\python.exe" "core\server.py" %*
    goto end
)

echo [ERROR] Python was not found in PATH!
pause
exit /b 1

:end
pause
