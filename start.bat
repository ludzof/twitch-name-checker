@echo off
title Twitch Short Username Sniper
color 05
echo ========================================================
echo    Twitch Short Username Checker & Sniper Dashboard
echo ========================================================
echo.
echo Starting Web Dashboard on http://localhost:5050 ...
echo Press Ctrl+C in this terminal window to stop the server.
echo.

cd /d "%~dp0"
python server.py
pause
