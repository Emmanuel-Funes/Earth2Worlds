$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonExe = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
$uvicornExe = if (Test-Path ".\.venv\Scripts\uvicorn.exe") { ".\.venv\Scripts\uvicorn.exe" } else { "uvicorn" }

Write-Host "[Earth2Worlds] Inicializando base de datos SQLite (earth2worlds.db)..." -ForegroundColor Cyan
& $pythonExe -m app.init_db

Write-Host "[Earth2Worlds] El navegador se abrira automaticamente en http://127.0.0.1:8000 cuando cargue el servidor..." -ForegroundColor Yellow
Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoProfile", "-Command", "for (`$i=0; `$i -lt 60; `$i++) { Start-Sleep -Milliseconds 500; try { `$r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/login' -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop; if (`$r.StatusCode -eq 200) { Start-Process 'http://127.0.0.1:8000'; break } } catch {} }"

Write-Host "[Earth2Worlds] Levantando servidor FastAPI en http://127.0.0.1:8000 ..." -ForegroundColor Green
& $uvicornExe app.main:app --host 127.0.0.1 --port 8000 --reload
