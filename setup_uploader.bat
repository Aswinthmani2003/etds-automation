@echo off
set PYTHON=C:\Users\aswinthmani_v\AppData\Local\Programs\Python\Python311\python.exe

echo.
echo  ETDS Uploader - One-time Setup
echo  ================================
echo.

if not exist "%PYTHON%" (
    echo  ERROR: Python 3.11 not found at:
    echo  %PYTHON%
    echo.
    pause
    exit /b 1
)

echo  Using: %PYTHON%
echo.
echo  Installing Playwright...
"%PYTHON%" -m pip install playwright
if errorlevel 1 (
    echo  ERROR: pip install failed.
    pause
    exit /b 1
)

echo.
echo  Downloading Chromium browser...
"%PYTHON%" -m playwright install chromium
if errorlevel 1 (
    echo  ERROR: Playwright browser install failed.
    pause
    exit /b 1
)

echo.
echo  ================================================
echo   Setup complete!  Run run_uploader.bat to start.
echo  ================================================
echo.
pause
