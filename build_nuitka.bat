@echo off
setlocal EnableDelayedExpansion
title AI Shorts Generator - Build Tool

echo.
echo ============================================================
echo   AI Shorts Generator - Nuitka Build Tool
echo   Creates a fully standalone package (no install needed)
echo ============================================================
echo.

:: --- Config ---
set "ROOT=%~dp0"
set "NODE_VERSION=20.18.3"
set "NODE_DIR=%ROOT%node_portable"
set "NODE_EXE=%NODE_DIR%\node.exe"
set "PW_BROWSERS=%ROOT%playwright-browsers"
set "DIST_DIR=%ROOT%dist"
set "APP_EXE=AIShorts.exe"

:: --- Step 1: Check Python ---
echo [1/6] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ and add to PATH.
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo        %%v
echo.

:: --- Step 2: Install Nuitka + Python deps ---
echo [2/6] Installing Python dependencies + Nuitka...
pip install nuitka ordered-set zstandard --quiet
pip install -r "%ROOT%requirements.txt" --quiet
echo        OK
echo.

:: --- Step 3: Download Node.js portable ---
echo [3/6] Preparing Node.js portable v%NODE_VERSION%...
if not exist "%NODE_EXE%" (
    set "NODE_FOLDER=node-v%NODE_VERSION%-win-x64"
    set "NODE_ZIP=%TEMP%\node-portable.zip"
    set "NODE_URL=https://nodejs.org/dist/v%NODE_VERSION%/!NODE_FOLDER!.zip"

    echo        Downloading from nodejs.org ...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri '!NODE_URL!' -OutFile '!NODE_ZIP!' -UseBasicParsing"
    if errorlevel 1 (
        echo [ERROR] Download failed. Check internet connection.
        pause & exit /b 1
    )

    echo        Extracting...
    powershell -NoProfile -Command "Expand-Archive -Path '!NODE_ZIP!' -DestinationPath '%TEMP%\node_extract' -Force"
    if not exist "%NODE_DIR%" mkdir "%NODE_DIR%"
    xcopy /E /I /Y /Q "%TEMP%\node_extract\!NODE_FOLDER!\*" "%NODE_DIR%\" >nul
    del "!NODE_ZIP!" >nul 2>&1
    rmdir /S /Q "%TEMP%\node_extract" >nul 2>&1
    echo        Node.js portable ready at node_portable\
) else (
    echo        Already exists - skipping download.
)
echo.

:: --- Step 4: npm install ---
echo [4/6] Running npm install (Playwright packages)...
set "PATH=%NODE_DIR%;%PATH%"
cd /d "%ROOT%"

if exist "%NODE_DIR%\node_modules\npm\bin\npm-cli.js" (
    "%NODE_EXE%" "%NODE_DIR%\node_modules\npm\bin\npm-cli.js" install --prefer-offline
) else (
    call "%NODE_DIR%\npm.cmd" install
)
if errorlevel 1 (
    echo [ERROR] npm install failed.
    pause & exit /b 1
)
echo        OK
echo.

:: --- Step 5: Install Playwright Chromium locally ---
echo [5/6] Installing Playwright Chromium to playwright-browsers\ ...
if not exist "%PW_BROWSERS%" mkdir "%PW_BROWSERS%"

set "PW_INSTALLED=0"
for /d %%D in ("%PW_BROWSERS%\chromium*") do set "PW_INSTALLED=1"

if "!PW_INSTALLED!"=="0" (
    set "PLAYWRIGHT_BROWSERS_PATH=%PW_BROWSERS%"
    if exist "%NODE_DIR%\node_modules\npm\bin\npx-cli.js" (
        "%NODE_EXE%" "%NODE_DIR%\node_modules\npm\bin\npx-cli.js" playwright install chromium
    ) else (
        call "%NODE_DIR%\npx.cmd" playwright install chromium
    )
    if errorlevel 1 (
        echo [ERROR] Playwright install failed.
        pause & exit /b 1
    )
    echo        Chromium installed to playwright-browsers\
) else (
    echo        Already exists - skipping.
)
echo.

:: --- Step 6: Nuitka build ---
echo [6/6] Building EXE with Nuitka...
echo        (First run may take 10-20 minutes)
echo.

:: CRITICAL: cd to ROOT so we can use relative paths
:: This avoids CMD quoting issues when path contains spaces (e.g. "This PC")
cd /d "%ROOT%"

if not exist "dist" mkdir "dist"

:: Use the Python helper script to invoke Nuitka
:: This bypasses CMD path parsing issues completely
python build_helper.py

if errorlevel 1 (
    echo.
    echo [ERROR] Nuitka build failed! See output above for details.
    pause & exit /b 1
)


echo.
echo ============================================================
echo   BUILD SUCCESSFUL!
echo.
echo   Files ready to package in Inno Setup:
echo     dist\AIShorts.exe       - Main app
echo     node_portable\          - Node.js runtime
echo     playwright-browsers\    - Chromium browser
echo     node_modules\           - Playwright package
echo     ffmpeg\                 - FFmpeg binary
echo.
echo   Next step: Open AIShorts-Setup.iss in Inno Setup Compiler
echo ============================================================
echo.
pause
