@echo off
title BoxBox AI - Set Railway Environment Variables
color 0C
echo.
echo =========================================
echo   Set Environment Variables on Railway
echo =========================================
echo.
cd /d "%~dp0"

echo กรุณาใส่ค่าต่อไปนี้ (กด Enter ข้ามถ้ายังไม่มี):
echo.

set /p META_SECRET="META_APP_SECRET: "
set /p META_TOKEN="META_PAGE_ACCESS_TOKEN: "
set /p IG_ID="IG_PAGE_ID: "
set /p ANTHROPIC="ANTHROPIC_API_KEY: "
set /p LINE_SECRET="LINE_CHANNEL_SECRET: "
set /p LINE_TOKEN="LINE_CHANNEL_ACCESS_TOKEN: "
set /p LINE_USER="LINE_OWNER_USER_ID: "

echo.
echo [Setting variables on Railway...]

if not "%META_SECRET%"==""  railway variables set META_APP_SECRET=%META_SECRET%
if not "%META_TOKEN%"==""   railway variables set META_PAGE_ACCESS_TOKEN=%META_TOKEN%
if not "%IG_ID%"==""        railway variables set IG_PAGE_ID=%IG_ID%
if not "%ANTHROPIC%"==""    railway variables set ANTHROPIC_API_KEY=%ANTHROPIC%
if not "%LINE_SECRET%"==""  railway variables set LINE_CHANNEL_SECRET=%LINE_SECRET%
if not "%LINE_TOKEN%"==""   railway variables set LINE_CHANNEL_ACCESS_TOKEN=%LINE_TOKEN%
if not "%LINE_USER%"==""    railway variables set LINE_OWNER_USER_ID=%LINE_USER%

railway variables set META_VERIFY_TOKEN=boxbox_verify_2026
railway variables set DATABASE_URL=sqlite:///./boxbox_crm.db
railway variables set HOT_LEAD_NOTIFY_THRESHOLD=0.85
railway variables set SALE_NOTIFY_MIN_AMOUNT=500
railway variables set DAILY_DIGEST_HOUR=20

echo.
echo =========================================
echo   Done! Variables set on Railway.
echo   Railway will auto-redeploy now.
echo =========================================
pause
