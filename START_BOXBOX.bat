@echo off
title BoxBox AI System - Startup
color 0A
echo.
echo =========================================
echo   BoxBox AI Sales System - Starting...
echo =========================================
echo.

:: Go to script directory
cd /d "%~dp0"

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Install dependencies
echo [1/3] Installing dependencies...
pip install -r requirements.txt -q --break-system-packages 2>nul || pip install -r requirements.txt -q
echo     Done!

:: Create .env if not exists
if not exist .env (
    echo [2/3] Creating .env from template...
    copy .env.example .env
    echo     .env created! Please fill in your API keys later.
) else (
    echo [2/3] .env found!
)

:: Start FastAPI server
echo [3/3] Starting BoxBox AI Server on port 8000...
echo.
echo =========================================
echo   Server running at: http://localhost:8000
echo   API Docs at:       http://localhost:8000/docs
echo =========================================
echo.
echo Keep this window open. Open START_NGROK.bat in a new window.
echo.
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
