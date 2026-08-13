@echo off
title ETDS PDF Renamer — Amirtharaj Investment
cd /d "%~dp0"

echo.
echo  ================================================
echo   ETDS PDF Renamer — Amirtharaj Investment
echo  ================================================
echo.

:: Try to find Python and run setup script
set PYTHON=

:: Try py launcher first
py -3 --version >nul 2>&1
if %errorlevel%==0 ( set PYTHON=py -3 & goto :run_setup )

:: Try AppData Python installations
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    goto :run_setup
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
    goto :run_setup
)
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
    goto :run_setup
)

:: Download Python if not found
echo  Python not found. Downloading Python 3.11...
powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python_setup.exe' -UseBasicParsing" 2>nul

if not exist "%TEMP%\python_setup.exe" (
    echo  ERROR: Could not download Python.
    echo  Download manually: https://www.python.org/downloads/
    pause & exit /b 1
)

echo  Installing Python 3.11...
"%TEMP%\python_setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
timeout /t 8 /nobreak >nul
del "%TEMP%\python_setup.exe" >nul 2>&1

py -3.11 --version >nul 2>&1
if %errorlevel%==0 ( set PYTHON=py -3.11 & goto :run_setup )

echo  ERROR: Python installation failed.
pause & exit /b 1

:run_setup
echo  Running setup...
echo.
%PYTHON% setup.py
pause
