@echo off
chcp 65001 >nul
title YanZhu Launcher
cd /d %~dp0

REM 端口集中在这里改：8000/4173 常被本机其它项目（人智评分系统）占用，
REM 故言筑固定用 后端 8100 + 预览 4180。
REM 改端口时需同步改三处：这里、frontend/vite.config.js、share.py。
set "BACKEND_PORT=8100"
set "FRONTEND_PORT=4180"

echo ==================================================
echo   YanZhu 言筑 - One-Click Start
echo   Backend  http://127.0.0.1:%BACKEND_PORT%
echo   Frontend http://127.0.0.1:%FRONTEND_PORT%
echo ==================================================
echo.

set "FRONTEND_URL=http://127.0.0.1:%FRONTEND_PORT%/"
set "BACKEND_URL=http://127.0.0.1:%BACKEND_PORT%/api/health"

where curl >nul 2>&1
if errorlevel 1 (
    echo [ERROR] curl.exe not found. Windows 10 1803+ ships it; please check PATH.
    echo.
    pause
    exit /b 1
)

REM ---------- locate a Python that has the backend deps ----------
set "BACKEND_PY="
if exist "%~dp0backend\.venv\Scripts\python.exe" set "BACKEND_PY=%~dp0backend\.venv\Scripts\python.exe"
if not defined BACKEND_PY if exist "C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe" set "BACKEND_PY=C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe"

REM ================= 1. backend on %BACKEND_PORT% =================
REM 探活用真实 HTTP 请求，而不是只看端口：端口被别的进程占着也照样显示 LISTENING
curl -s --noproxy "*" --max-time 2 -o nul "%BACKEND_URL%" >nul 2>&1
if not errorlevel 1 (
    echo [1/3] Backend %BACKEND_PORT% already healthy - skip
    goto frontend
)

netstat -ano | findstr :%BACKEND_PORT% | findstr LISTENING >nul
if not errorlevel 1 (
    echo [1/3] WARNING: port %BACKEND_PORT% is occupied but not answering %BACKEND_URL%
    echo       Close that window / kill that process, or change BACKEND_PORT at the top.
    echo.
    pause
    exit /b 1
)

if not defined BACKEND_PY (
    echo [1/3] First run: creating backend venv and installing deps ...
    python -m venv "%~dp0backend\.venv"
    "%~dp0backend\.venv\Scripts\python.exe" -m pip install -r "%~dp0backend\requirements.txt"
    set "BACKEND_PY=%~dp0backend\.venv\Scripts\python.exe"
)

echo [1/3] Starting backend %BACKEND_PORT% ...
start "YanZhu-Backend" cmd /k ""%BACKEND_PY%" -m uvicorn --app-dir "%~dp0backend" app.main:app --host 127.0.0.1 --port %BACKEND_PORT%"

REM ================= 2. frontend preview on %FRONTEND_PORT% =================
:frontend
curl -s --noproxy "*" --max-time 2 -o nul "%FRONTEND_URL%" >nul 2>&1
if not errorlevel 1 (
    echo [2/3] Frontend %FRONTEND_PORT% already healthy - skip
    goto openbrowser
)

REM 端口被占但不响应 127.0.0.1：典型是旧 preview 只绑了 IPv6(::1)。
REM 注意：取值与判断必须分处顶层语句，不能塞进同一个 () 块——
REM 块内 %VAR% 在解析期就展开，会拿到空值（batch 延迟展开坑）。
set "STALE_PID="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :%FRONTEND_PORT% ^| findstr LISTENING') do set "STALE_PID=%%p"
if not defined STALE_PID goto frontend_start

tasklist /fi "PID eq %STALE_PID%" /fo csv 2>nul | findstr /i "node.exe" >nul
if errorlevel 1 (
    echo [2/3] WARNING: port %FRONTEND_PORT% is occupied by a non-node process ^(PID %STALE_PID%^).
    echo       Close it and run this script again.
    echo.
    pause
    exit /b 1
)

echo [2/3] Port %FRONTEND_PORT% held by a stale preview ^(PID %STALE_PID%^) - restarting it ...
taskkill /f /pid %STALE_PID% >nul 2>&1
timeout /t 1 /nobreak >nul

:frontend_start
if not exist "%~dp0frontend\node_modules" (
    echo [2/3] First run: installing frontend deps ...
    pushd "%~dp0frontend"
    call npm install
    popd
)

echo [2/3] Building and starting frontend %FRONTEND_PORT% ...
start "YanZhu-Frontend" cmd /k "cd /d %~dp0frontend && npm run build && npm run preview"

REM ================= 3. wait until really serving, then open =================
:openbrowser
echo [3/3] Waiting for frontend to serve ...
set /a WAITED=0
:waitloop
curl -s --noproxy "*" --max-time 2 -o nul "%FRONTEND_URL%" >nul 2>&1
if not errorlevel 1 goto ready
set /a WAITED+=1
if %WAITED% GEQ 90 (
    echo       Timed out after 90s. Check the YanZhu-Frontend window for build errors.
    echo.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto waitloop

:ready
echo       Frontend ready after %WAITED%s.
start "" "%FRONTEND_URL%"
echo.
echo Done - browser opened at %FRONTEND_URL%
echo Close the two black windows (YanZhu-Backend / YanZhu-Frontend) to stop the services.
echo.
pause
