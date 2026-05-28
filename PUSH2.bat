@echo off
title BoxBox - Push Fix
cd /d "D:\Claude co-work\BoxBox_AI_System"

echo [1] Removing .git... > D:\push_log.txt 2>&1
if exist ".git" rmdir /s /q ".git" >> D:\push_log.txt 2>&1

echo [2] Git init... >> D:\push_log.txt 2>&1
git init >> D:\push_log.txt 2>&1
git branch -M main >> D:\push_log.txt 2>&1
git config user.email "blackdevilz.demonz@gmail.com" >> D:\push_log.txt 2>&1
git config user.name "BoxBox AI" >> D:\push_log.txt 2>&1

echo [3] Staging files... >> D:\push_log.txt 2>&1
git add . >> D:\push_log.txt 2>&1

echo [4] Committing... >> D:\push_log.txt 2>&1
git commit -m "fix: complete main.py + config thresholds" >> D:\push_log.txt 2>&1

echo [5] Pushing to GitHub... >> D:\push_log.txt 2>&1
git remote add origin "https://ghp_R82lX01C0w1npsCjk0tzA5Gx9sIFMS06XbUE@github.com/blackdevilzdemonz-prog/boxbox-ai-system.git" >> D:\push_log.txt 2>&1
git push -u origin main --force >> D:\push_log.txt 2>&1

echo [DONE] >> D:\push_log.txt 2>&1
echo Push complete. Check D:\push_log.txt for details.
