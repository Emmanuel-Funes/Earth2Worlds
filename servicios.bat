@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

cd /d "%~dp0"

if /I "%~1"=="start" goto :START_ALL
if /I "%~1"=="iniciar" goto :START_ALL
if /I "%~1"=="stop" goto :STOP_ALL
if /I "%~1"=="detener" goto :STOP_ALL
if /I "%~1"=="status" goto :STATUS_ALL
if /I "%~1"=="estado" goto :STATUS_ALL

:MENU
cls
echo ============================================================
echo   Earth2Worlds - Gestor de Servicios Locales
echo ============================================================
echo.
echo   [1] Iniciar Plataforma Unificada Earth2Worlds (Puerto 8000 + Abrir Web)
echo   [2] Detener todos los servicios
echo   [3] Ver estado de los puertos (8000, 3000, 5173)
echo   [4] Salir
echo.
set /p OPCION="Selecciona una opcion [1-4]: "

if "%OPCION%"=="1" goto :START_ALL
if "%OPCION%"=="2" goto :STOP_ALL
if "%OPCION%"=="3" goto :STATUS_ALL
if "%OPCION%"=="4" exit /b 0
goto :MENU

:START_ALL
echo.
echo [Earth2Worlds] Preparando e iniciando plataforma unificada...

set "PYTHON_EXE=python"
set "UVICORN_EXE=uvicorn"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if exist ".venv\Scripts\uvicorn.exe" set "UVICORN_EXE=.venv\Scripts\uvicorn.exe"

echo   - Inicializando base de datos (earth2worlds.db)...
"%PYTHON_EXE%" -m app.init_db
if errorlevel 1 (
    echo   [Error] Fallo la inicializacion de la base de datos.
    if "%~1"=="" pause & goto :MENU
    exit /b 1
)

echo   - Iniciando servidor Earth2Worlds + Rotaterra en http://127.0.0.1:8000 ...
start "Earth2Worlds - Plataforma Unificada (8000)" cmd /k "cd /d "%~dp0" && "%UVICORN_EXE%" app.main:app --host 127.0.0.1 --port 8000 --reload"

echo   - Esperando a que el servidor termine de cargar para abrir el navegador...
powershell -NoProfile -Command "for ($i=0; $i -lt 60; $i++) { Start-Sleep -Milliseconds 500; try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/login' -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop; if ($r.StatusCode -eq 200) { Start-Process 'http://127.0.0.1:8000'; break } } catch {} }"

echo.
echo [OK] Plataforma Earth2Worlds activa y abierta en el navegador:
echo   - Panel Principal:     http://127.0.0.1:8000
echo   - Mapa de Secciones:   http://127.0.0.1:8000/mapa
echo   - Diagrama de BD:      http://127.0.0.1:8000/diagrama
echo.
if "%~1"=="" pause & goto :MENU
exit /b 0

:STOP_ALL
echo.
echo [Earth2Worlds] Deteniendo servicios en puertos 8000, 3000 y 5173...

taskkill /FI "WINDOWTITLE eq Earth2Worlds - Plataforma Unificada (8000)" /F >nul 2>&1

for %%P in (8000 3000 5173) do (
    for /f "tokens=5" %%A in ('netstat -aon ^| findstr /r /c:"[:\.]%%P " ^| findstr "LISTENING"') do (
        if not "%%A"=="0" (
            tasklist /FI "PID eq %%A" 2>nul | findstr /i /r "python uvicorn node" >nul
            if not errorlevel 1 (
                echo   - Terminando proceso en puerto %%P (PID %%A)...
                taskkill /PID %%A /F >nul 2>&1
            )
        )
    )
)

echo [OK] Servicios detenidos de forma segura.
echo.
if "%~1"=="" pause & goto :MENU
exit /b 0

:STATUS_ALL
echo.
echo [Earth2Worlds] Estado actual de los puertos:
echo ------------------------------------------------------------
for %%P in (8000 3000 5173) do (
    set "FOUND="
    for /f "tokens=5" %%A in ('netstat -aon ^| findstr /r /c:"[:\.]%%P " ^| findstr "LISTENING"') do (
        set "FOUND=%%A"
    )
    if defined FOUND (
        echo   Puerto %%P : ACTIVO ^(PID !FOUND!^)
    ) else (
        echo   Puerto %%P : INACTIVO
    )
)
echo ------------------------------------------------------------
echo.
if "%~1"=="" pause & goto :MENU
exit /b 0
