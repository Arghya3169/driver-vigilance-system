@echo off
setlocal enabledelayedexpansion
title Driver Vigilance System
cd /d "%~dp0"

echo ========================================================
echo Starting Driver Vigilance ^& Multi-Modal Safety System...
echo ========================================================
echo.

:: 1. Check if virtual environment already exists
if exist "venv\Scripts\python.exe" (
    echo [INFO] Using virtual environment: venv
    set "PYTHON_CMD=venv\Scripts\python.exe"
    venv\Scripts\python.exe -c "import cv2, mediapipe" >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo [INFO] Installing missing dependencies into venv...
        venv\Scripts\pip.exe install -r requirements.txt
    )
    goto :RUN_APP
)
if exist ".venv\Scripts\python.exe" (
    echo [INFO] Using virtual environment: .venv
    set "PYTHON_CMD=.venv\Scripts\python.exe"
    .venv\Scripts\python.exe -c "import cv2, mediapipe" >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo [INFO] Installing missing dependencies into .venv...
        .venv\Scripts\pip.exe install -r requirements.txt
    )
    goto :RUN_APP
)

:: 2. Locate system Python
set "BASE_PYTHON="
py -3 --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "BASE_PYTHON=py -3"
) else (
    python --version >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set "BASE_PYTHON=python"
    )
)

if "%BASE_PYTHON%"=="" (
    echo ========================================================
    echo [ERROR] Python is not installed or not in your system PATH!
    echo ========================================================
    echo.
    echo How to resolve:
    echo   1. Download Python 3.10, 3.11, or 3.12 from:
    echo      https://www.python.org/downloads/
    echo   2. When running the installer, make sure to check:
    echo      [x] "Add python.exe to PATH"
    echo   3. Complete the installation, then run run.bat again.
    echo.
    pause
    exit /b 1
)

:: 3. Test if required packages are available
%BASE_PYTHON% -c "import cv2, mediapipe" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [INFO] Required packages not detected. Setting up virtual environment (venv)...
    %BASE_PYTHON% -m venv venv
    if exist "venv\Scripts\python.exe" (
        echo [INFO] Installing dependencies from requirements.txt...
        venv\Scripts\python.exe -m pip install --upgrade pip
        venv\Scripts\pip.exe install -r requirements.txt
        set "PYTHON_CMD=venv\Scripts\python.exe"
    ) else (
        echo [INFO] Installing dependencies directly...
        %BASE_PYTHON% -m pip install -r requirements.txt
        set "PYTHON_CMD=%BASE_PYTHON%"
    )
) else (
    set "PYTHON_CMD=%BASE_PYTHON%"
)

:RUN_APP
echo.
echo Launching application...
echo ========================================================
%PYTHON_CMD% main.py
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [ERROR] An error occurred while running the application.
    pause
)
