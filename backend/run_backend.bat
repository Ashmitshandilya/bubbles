@echo off
rem Runs the Bubbles backend and restarts it if it ever stops, so the app never stays "offline".
rem Usage: run_backend.bat [path-to-python.exe]   (defaults to "python")
title BUBBLES Backend
cd /d "%~dp0"
set "PY=%~1"
if "%PY%"=="" set "PY=python"

:loop
rem If another Bubbles backend already serves port 8000, stand by instead of fighting for the port.
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [%date% %time%] Port 8000 is already served by a running backend. Standing by; I will take over if it stops.
    ping -n 6 127.0.0.1 >nul
    goto loop
)
echo [%date% %time%] Starting the Bubbles backend on http://127.0.0.1:8000
"%PY%" -m uvicorn main:app --host 127.0.0.1 --port 8000
echo.
echo [%date% %time%] The backend stopped (exit code %errorlevel%). Restarting in 3 seconds.
echo        Close this window to stop Bubbles. If this repeats, read the error above it.
ping -n 4 127.0.0.1 >nul
goto loop
