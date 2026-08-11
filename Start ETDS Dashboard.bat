@echo off
title ETDS PDF Renamer — Amirtharaj Investment
cd /d "%~dp0"

echo.
echo  ================================================
echo   ETDS PDF Renamer — Amirtharaj Investment
echo  ================================================
echo.

:: ── Step 1: Find Python ──────────────────────────────────────────────────────
set PYTHON=

where python >nul 2>&1
if %errorlevel%==0 ( set PYTHON=python & goto :check_version )

where py >nul 2>&1
if %errorlevel%==0 ( set PYTHON=py & goto :check_version )

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    goto :check_version
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
    goto :check_version
)
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
    goto :check_version
)

:: ── Python not found — download and install silently ─────────────────────────
echo  [1/3] Python not found. Downloading Python 3.11 installer...
echo        (One-time setup ~ 25 MB, please wait...)
echo.

powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python_setup.exe' -UseBasicParsing"

if not exist "%TEMP%\python_setup.exe" (
    echo.
    echo  ERROR: Could not download Python. Check your internet connection.
    echo  Or download manually from https://www.python.org/downloads/
    echo.
    pause & exit /b 1
)

echo  Installing Python silently (no pop-ups)...
"%TEMP%\python_setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
timeout /t 8 /nobreak >nul
del "%TEMP%\python_setup.exe" >nul 2>&1

set PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
if not exist "%PYTHON%" (
    echo.
    echo  ERROR: Python installation failed.
    echo  Please download and install manually from https://www.python.org/downloads/
    echo  Then double-click this bat file again.
    echo.
    pause & exit /b 1
)
echo  Python installed successfully!
echo.

:check_version
echo  [1/3] Python ready.

:: ── Step 2: Install Python packages ──────────────────────────────────────────
echo  [2/3] Checking required packages (first run installs them automatically)...
echo.

%PYTHON% -m pip install --upgrade pip --quiet --no-warn-script-location
%PYTHON% -m pip install flask pymupdf "zxing-cpp" pillow openpyxl --quiet --no-warn-script-location

if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Package installation failed.
    echo  Try right-clicking this bat file and selecting "Run as administrator".
    echo.
    pause & exit /b 1
)

echo  [2/3] All packages ready.
echo.

:: ── Step 3: Launch dashboard ──────────────────────────────────────────────────
echo  [3/3] Starting dashboard...
echo.
echo  ┌─────────────────────────────────────────────┐
echo  │  Dashboard is running!                      │
echo  │  Opening browser at http://localhost:5000   │
echo  │                                             │
echo  │  Keep this window open while working.       │
echo  │  Close this window to stop the server.      │
echo  └─────────────────────────────────────────────┘
echo.

timeout /t 2 /nobreak >nul
start "" "http://localhost:5000"
%PYTHON% app.py

echo.
echo  Server stopped. Press any key to close.
pause >nul
