@echo off
set PYTHON=C:\Users\aswinthmani_v\AppData\Local\Programs\Python\Python311\python.exe

echo.
echo  ETDS PDF Uploader - Amirtharaj Investment
echo  ==========================================
echo.

if not exist "%PYTHON%" (
    echo  ERROR: Python 3.11 not found. Run setup_uploader.bat first.
    pause
    exit /b 1
)

:: Find Chrome
set CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" set CHROME=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" (
    echo  ERROR: Google Chrome not found. Please install Chrome.
    pause
    exit /b 1
)

echo  Closing any open Chrome windows (may take a moment)...
taskkill /F /T /IM chrome.exe >nul 2>&1
taskkill /F /T /IM chrome.exe >nul 2>&1
timeout /t 4 /nobreak >nul

echo  Opening Chrome (your existing profile + automation enabled)...
start "" "%CHROME%" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data" --profile-directory="Default" --no-first-run
timeout /t 5 /nobreak >nul

echo.
echo  Chrome is now open. If you are NOT logged in to Steel City,
echo  please log in now before pressing ENTER below.
echo.
pause

echo.
set /p PDF_FOLDER="Drag your renamed PDFs folder here (or type path): "
set PDF_FOLDER=%PDF_FOLDER:"=%

if not exist "%PDF_FOLDER%" (
    echo.
    echo  ERROR: Folder not found.
    pause
    exit /b 1
)

echo.
"%PYTHON%" "%~dp0upload_etds.py" "%PDF_FOLDER%"
echo.
pause
