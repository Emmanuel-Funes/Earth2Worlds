$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonExe = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
$uvicornExe = if (Test-Path ".\.venv\Scripts\uvicorn.exe") { ".\.venv\Scripts\uvicorn.exe" } else { "uvicorn" }

Write-Host "[Earth2Worlds] Inicializando base de datos SQLite (earth2worlds.db)..." -ForegroundColor Cyan
& $pythonExe -m app.init_db

Write-Host "[Earth2Worlds] Levantando servidor FastAPI en http://127.0.0.1:8000 ..." -ForegroundColor Green
& $uvicornExe app.main:app --host 127.0.0.1 --port 8000 --reload
