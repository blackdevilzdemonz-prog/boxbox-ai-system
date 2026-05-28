@echo off
title BoxBox AI - Deploy to Railway
color 0D
echo.
echo =========================================
echo   BoxBox AI - Deploy to Railway
echo =========================================
echo.

cd /d "%~dp0"

:: ── Step 1: Check Git ─────────────────────────────────────────────────────
echo [1/5] Checking Git...
where git >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git not found!
    echo Please install Git from: https://git-scm.com/download/win
    pause
    exit /b 1
)
echo     Git found!

:: ── Step 2: Check Railway CLI ────────────────────────────────────────────
echo [2/5] Checking Railway CLI...
where railway >nul 2>&1
if errorlevel 1 (
    echo     Railway CLI not found. Installing...
    powershell -Command "iwr https://install.railway.app -useb | iex"
    echo     Done! Please restart this script.
    pause
    exit /b 1
)
echo     Railway CLI found!

:: ── Step 3: Git init ─────────────────────────────────────────────────────
echo [3/5] Setting up Git repository...
if not exist ".git" (
    git init
    git add .
    git commit -m "BoxBox AI System - Initial Deploy"
    echo     Git repo initialized!
) else (
    git add .
    git commit -m "BoxBox AI System - Update"
    echo     Git updated!
)

:: ── Step 4: Railway Login ────────────────────────────────────────────────
echo [4/5] Railway Login...
echo     A browser will open for login...
railway login
echo     Logged in!

:: ── Step 5: Deploy ───────────────────────────────────────────────────────
echo [5/5] Deploying to Railway...
railway up --detach

echo.
echo =========================================
echo   Getting your public URL...
echo =========================================
railway domain
echo.
echo =========================================
echo   IMPORTANT: ใส่ URL ด้านบน + /webhook/line
echo   ลงใน LINE Developers Console
echo   เช่น: https://boxbox-ai.railway.app/webhook/line
echo =========================================
echo.
echo กด Enter เพื่อเปิด Railway Dashboard...
pause
railway open
