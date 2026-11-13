@echo off
chcp 65001 >nul
title YanZhu Share - cpolar keep-alive
cd /d %~dp0

REM 守护版：掉线自动重建。日常分享用这个，share.bat 保留给一次性临时分享。
set "PY="
if exist "%~dp0backend\.venv\Scripts\python.exe" set "PY=%~dp0backend\.venv\Scripts\python.exe"
if not defined PY if exist "C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe" set "PY=C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if not defined PY set "PY=python"

"%PY%" "%~dp0share_keep.py"

echo.
echo 按任意键关闭此窗口。
pause
