$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$Root\frontend'; npm run dev"
)

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$Root\backend'; if (Test-Path '.\venv\Scripts\Activate.ps1') { . .\venv\Scripts\Activate.ps1 }; python -m uvicorn main:app --host 127.0.0.1 --port 8000"
)

Write-Host "BUBBLES services starting..."
Write-Host "Frontend: http://localhost:3000"
Write-Host "Backend:  http://127.0.0.1:8000"
