@echo off
setlocal EnableExtensions
title BUBBLES Launcher

set "ROOT=%~dp0"
set "FRONTEND=%ROOT%frontend"
set "BACKEND=%ROOT%backend"
set "FRONT_URL=http://localhost:3000"
set "BACK_URL=http://127.0.0.1:8000"

echo.
echo ==========================================
echo              BUBBLES LAUNCHER
echo ==========================================
echo.

:: ---------- prerequisites ----------
where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed or not in PATH. Install Node.js LTS first.
    pause
    exit /b 1
)
where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm was not found.
    pause
    exit /b 1
)
if not exist "%FRONTEND%\package.json" (
    echo [ERROR] Frontend not found at %FRONTEND%
    pause
    exit /b 1
)
if not exist "%BACKEND%\main.py" (
    echo [ERROR] Backend not found at %BACKEND%
    pause
    exit /b 1
)

:: ---------- environment files (names only, never printed) ----------
if not exist "%BACKEND%\.env" (
    echo [ERROR] backend\.env is missing. Copy backend\.env.example to backend\.env and fill it in.
    pause
    exit /b 1
)
if not exist "%FRONTEND%\.env.local" (
    echo [ERROR] frontend\.env.local is missing. It needs NEXT_PUBLIC_SUPABASE_URL,
    echo         NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY and NEXT_PUBLIC_API_URL.
    pause
    exit /b 1
)

:: ---------- backend python: venv if present, else a working system Python, else build a venv ----------
echo [1/5] Checking backend Python environment...
set "PY="
if exist "%BACKEND%\venv\Scripts\python.exe" set "PY=%BACKEND%\venv\Scripts\python.exe"
if not defined PY (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import fastapi, uvicorn, supabase" >nul 2>&1
        if not errorlevel 1 set "PY=python"
    )
)
if not defined PY (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python was not found in PATH. Install Python 3.11+ first.
        pause
        exit /b 1
    )
    echo       Creating a virtual environment and installing requirements. This happens once.
    python -m venv "%BACKEND%\venv"
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
    "%BACKEND%\venv\Scripts\python.exe" -m pip install -r "%BACKEND%\requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Backend dependency installation failed. Run the pip command above to see why.
        pause
        exit /b 1
    )
    set "PY=%BACKEND%\venv\Scripts\python.exe"
)
echo       Using: %PY%

:: ---------- frontend dependencies ----------
echo [2/5] Checking frontend dependencies...
if not exist "%FRONTEND%\node_modules" (
    echo       Installing frontend dependencies. This happens once.
    pushd "%FRONTEND%"
    call npm.cmd install
    if errorlevel 1 (
        popd
        echo [ERROR] Frontend dependency installation failed.
        pause
        exit /b 1
    )
    popd
)

:: ---------- backend (supervised: restarts itself if it stops) ----------
echo [3/5] Starting backend...
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       Port 8000 is already in use - assuming the backend is already running.
) else (
    start "BUBBLES Backend" /D "%BACKEND%" cmd /k call run_backend.bat "%PY%"
)

:: ---------- frontend ----------
echo [4/5] Starting frontend...
netstat -ano | findstr /R /C:":3000 .*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       Port 3000 is already in use - assuming the frontend is already running.
) else (
    start "BUBBLES Frontend" /D "%FRONTEND%" cmd /k "npm.cmd run dev"
)

:: ---------- wait until both answer, report database status, open the browser ----------
echo [5/5] Waiting for services to become ready...
powershell -NoProfile -Command "$u='%BACK_URL%/health'; for($i=0;$i -lt 90;$i++){ try { $r=Invoke-RestMethod $u -TimeoutSec 3; $d=$r.services.database; if($d -eq 'ok'){Write-Host '      Backend is ready. Database: ok'} elseif($d -eq 'permission_denied'){Write-Host '      Backend is ready. Database: COMPATIBILITY MODE (your data is saved safely).'; Write-Host '      For full storage, run supabase\migrations\20261006_coco_service_role_grants.sql in the Supabase SQL editor.'} else {Write-Host ('      Backend is ready. Database: ' + $d)}; exit 0 } catch { Start-Sleep 1 } }; exit 1"
if errorlevel 1 (
    echo [WARNING] Backend did not answer within 90 seconds. Read the BUBBLES Backend window for the error.
)
powershell -NoProfile -Command "$u='%FRONT_URL%'; for($i=0;$i -lt 120;$i++){ try { Invoke-WebRequest $u -UseBasicParsing -TimeoutSec 3 | Out-Null; exit 0 } catch { Start-Sleep 1 } }; exit 1"
if errorlevel 1 (
    echo [WARNING] Frontend did not answer within 2 minutes. Check the BUBBLES Frontend window for errors.
) else (
    echo       Frontend is ready.
    start "" "%FRONT_URL%"
)

echo.
echo ==========================================
echo            BUBBLES IS RUNNING
echo ==========================================
echo Frontend: %FRONT_URL%
echo Backend:  %BACK_URL%
echo API Docs: %BACK_URL%/docs
echo ==========================================
echo.
echo Keep the BUBBLES Backend and BUBBLES Frontend windows open.
echo The backend restarts itself if it stops. Close the windows to stop Bubbles.
echo.
pause
endlocal
