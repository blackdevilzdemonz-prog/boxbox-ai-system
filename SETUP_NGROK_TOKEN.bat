@echo off
title Setup ngrok Auth Token
color 0E
echo.
echo =========================================
echo   Setup ngrok Auth Token
echo =========================================
echo.
echo 1. ไปที่: https://dashboard.ngrok.com/signup
echo    (สมัครฟรี ใช้ email ก็ได้)
echo.
echo 2. หลัง login ไปที่:
echo    https://dashboard.ngrok.com/get-started/your-authtoken
echo.
echo 3. Copy Auth Token แล้ววางด้านล่าง:
echo.
set /p TOKEN="Paste Auth Token here: "

if "%TOKEN%"=="" (
    echo [ERROR] Token cannot be empty!
    pause
    exit /b 1
)

echo.
echo Setting up token...
ngrok config add-authtoken %TOKEN%

echo.
echo =========================================
echo   Done! Now run START_NGROK.bat
echo =========================================
pause
