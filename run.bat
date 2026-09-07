@echo off
title Driver Vigilance System
cd /d "%~dp0"
echo ========================================================
echo Starting Driver Vigilance & Multi-Modal Safety System...
echo ========================================================
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred while starting the application.
    pause
)
