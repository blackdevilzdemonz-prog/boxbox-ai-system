@echo off
title BoxBox AI - ngrok Tunnel
color 0B
echo.
echo =========================================
echo   BoxBox AI - Starting ngrok Tunnel
echo =========================================
echo.

:: Check if ngrok is installed
where ngrok >nul 2>&1
if errorlevel 1 (
    echo [INFO] ngrok not found. Downloading...
    echo.
    
    :: Download ngrok using PowerShell
    powershell -Command "& {
        Write-Host 'Downloading ngrok...'
        $url = 'https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip'
        $out = '%TEMP%\ngrok.zip'
        Invoke-WebRequest -Uri $url -OutFile $out
        Write-Host 'Extracting...'
        Expand-Archive -Path $out -DestinationPath 'C:\ngrok' -Force
        Write-Host 'Done!'
    }"
    
    set PATH=%PATH%;C:\ngrok
    
    echo.
    echo =========================================
    echo   IMPORTANT: You need a free ngrok account
    echo   1. Go to: https://dashboard.ngrok.com/signup
    echo   2. Copy your Auth Token
    echo   3. Run this command:
    echo      C:\ngrok\ngrok.exe config add-authtoken YOUR_TOKEN
    echo   4. Then run this file again
    echo =========================================
    echo.
    pause
    exit /b 1
)

echo [OK] ngrok found!
echo.
echo Starting tunnel on port 8000...
echo.
echo =========================================
echo   When you see "Forwarding https://xxx.ngrok-free.app"
echo   Copy that URL and add /webhook/line at the end
echo   Example: https://abc123.ngrok-free.app/webhook/line
echo =========================================
echo.
ngrok http 8000
pause
