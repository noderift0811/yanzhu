@echo off
chcp 65001 >nul
title YanZhu Share - cpolar tunnel
cd /d %~dp0

REM 复用 start.bat 的三级 Python 查找
set "PY="
if exist "%~dp0backend\.venv\Scripts\python.exe" set "PY=%~dp0backend\.venv\Scripts\python.exe"
if not defined PY if exist "C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe" set "PY=C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if not defined PY set "PY=python"

"%PY%" "%~dp0share.py"

echo.
echo 按任意键关闭此窗口。
pause
