@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"

echo [Earth2Worlds] Inicializando base de datos (earth2worlds.db)...
"%PYTHON_EXE%" -m app.init_db
if errorlevel 1 (
    echo [Error] Fallo la inicializacion de la base de datos.
    pause
    exit /b 1
)

echo [Earth2Worlds] Preparando apertura automatica del navegador cuando el servidor este listo...
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for ($i=0; $i -lt 60; $i++) { Start-Sleep -Milliseconds 500; try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/login' -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop; if ($r.StatusCode -eq 200) { Start-Process 'http://127.0.0.1:8000'; break } } catch {} }"

echo [Earth2Worlds] Iniciando servidor en http://127.0.0.1:8000 ...
"%PYTHON_EXE%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
if errorlevel 1 (
    echo [Error] El servidor se detuvo o fallo al iniciar.
    pause
)
