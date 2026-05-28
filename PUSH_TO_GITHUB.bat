@echo off
title BoxBox AI - Push to GitHub
color 0A
echo.
echo =========================================
echo   BoxBox AI - Pushing to GitHub...
echo =========================================
echo.
cd /d "%~dp0"

echo [1/4] Setting up Git...
git config --global user.email "blackdevilz.demonz@gmail.com"
git config --global user.name "BoxBox AI"

echo [2/4] Initializing repository...
if exist ".git" rmdir /s /q ".git"
git init
git branch -M main

echo [3/4] Adding files...
git add .
git commit -m "BoxBox AI System - Deploy"

echo [4/4] Pushing to GitHub...
git remote add origin "https://ghp_R82lX01C0w1npsCjk0tzA5Gx9sIFMS06XbUE@github.com/blackdevilzdemonz-prog/boxbox-ai-system.git"
git push -u origin main --force

echo.
echo =========================================
if %errorlevel%==0 (
    echo   SUCCESS! Code is now on GitHub!
    echo   กลับไปบอก Claude ได้เลย
) else (
    echo   ERROR! Please check the output above.
)
echo =========================================
pause
