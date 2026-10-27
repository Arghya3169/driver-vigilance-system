@echo off
title Driver Vigilance System
cd /d "%~dp0"

echo ========================================================
echo Starting Driver Vigilance ^& Multi-Modal Safety System...
echo ========================================================
echo.

:: 1. Check local virtual environments first
if exist "venv\Scripts\python.exe" (
    echo [INFO] Using virtual environment: venv
    venv\Scripts\python.exe main.py %*
    goto :DONE
)
if exist ".venv\Scripts\python.exe" (
    echo [INFO] Using virtual environment: .venv
    .venv\Scripts\python.exe main.py %*
    goto :DONE
)

:: 2. Try py launcher (standard on Windows)
py --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Using Python Launcher: py
    py main.py %*
    goto :DONE
)

:: 3. Try python in PATH
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Using system Python
    python main.py %*
    goto :DONE
)

:: 4. Look for Python in standard local installation directories
for /d %%D in ("%LOCALAPPDATA%\Python\pythoncore-*") do (
    if exist "%%D\python.exe" (
        echo [INFO] Found Python at: %%D\python.exe
        "%%D\python.exe" main.py %*
        goto :DONE
    )
)
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%D\python.exe" (
        echo [INFO] Found Python at: %%D\python.exe
        "%%D\python.exe" main.py %*
        goto :DONE
    )
)
for /d %%D in ("%ProgramFiles%\Python*") do (
    if exist "%%D\python.exe" (
        echo [INFO] Found Python at: %%D\python.exe
        "%%D\python.exe" main.py %*
        goto :DONE
    )
)

:: 5. Python not found
echo ========================================================
echo [ERROR] Python could not be located on this computer.
echo ========================================================
echo.
echo Please ensure Python is installed and added to PATH.
echo.
pause
exit /b 1

:DONE
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================================
    echo [ERROR] Application exited with error code %ERRORLEVEL%.
    echo ========================================================
    pause
)
