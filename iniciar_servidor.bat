@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PYTHON_EXE=python"
set "UVICORN_EXE=uvicorn"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if exist ".venv\Scripts\uvicorn.exe" set "UVICORN_EXE=.venv\Scripts\uvicorn.exe"

echo [Earth2Worlds] Inicializando base de datos (earth2worlds.db)...
"%PYTHON_EXE%" -m app.init_db
if errorlevel 1 (
    echo [Error] Fallo la inicializacion de la base de datos.
    pause
    exit /b 1
)

echo [Earth2Worlds] Iniciando servidor en http://127.0.0.1:8000 ...
"%UVICORN_EXE%" app.main:app --host 127.0.0.1 --port 8000 --reload
