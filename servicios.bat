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
echo   [1] Iniciar todos los servicios (Rotaterra + Backend + Frontend)
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
echo [Earth2Worlds] Iniciando servicios locales...

if not defined ROTATERRA_API_KEY set "ROTATERRA_API_KEY=clave-local-dev"
set "ROTATERRA_API_KEYS=%ROTATERRA_API_KEY%"

if exist ".venv\Scripts\uvicorn.exe" (
    if exist "rotaterra\api.py" (
        echo   - Iniciando motor satelital Rotaterra en http://127.0.0.1:8000 ...
        start "Earth2Worlds - Rotaterra (8000)" cmd /k "cd /d "%~dp0" && set ROTATERRA_API_KEYS=%ROTATERRA_API_KEYS% && .\.venv\Scripts\uvicorn.exe rotaterra.api:app --host 127.0.0.1 --port 8000"
        if not defined ROTATERRA_API_URL set "ROTATERRA_API_URL=http://127.0.0.1:8000/consulta"
    ) else (
        echo   - [Aviso] No se encontro rotaterra\api.py en esta rama; el backend usara ROTATERRA_API_URL por defecto.
    )
) else (
    echo   - [Aviso] No se encontro .venv\Scripts\uvicorn.exe; el backend usara ROTATERRA_API_URL por defecto.
)

echo   - Iniciando Backend Fastify en http://127.0.0.1:3000 ...
if defined ROTATERRA_API_URL (
    start "Earth2Worlds - Backend (3000)" cmd /k "cd /d "%~dp0backend" && set ROTATERRA_API_KEY=%ROTATERRA_API_KEY% && set ROTATERRA_API_URL=%ROTATERRA_API_URL% && npm run dev"
) else (
    start "Earth2Worlds - Backend (3000)" cmd /k "cd /d "%~dp0backend" && set ROTATERRA_API_KEY=%ROTATERRA_API_KEY% && npm run dev"
)

echo   - Iniciando Frontend Vite en http://localhost:5173 ...
start "Earth2Worlds - Frontend (5173)" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo [OK] Servicios lanzados:
echo   - Frontend Web:      http://localhost:5173
echo   - Backend API:       http://127.0.0.1:3000/api/v1/catalog
echo   - Rotaterra API:     http://127.0.0.1:8000/salud
echo.
if "%~1"=="" pause & goto :MENU
exit /b 0

:STOP_ALL
echo.
echo [Earth2Worlds] Deteniendo servicios en puertos 8000, 3000 y 5173...

taskkill /FI "WINDOWTITLE eq Earth2Worlds - Rotaterra (8000)*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Earth2Worlds - Backend (3000)*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Earth2Worlds - Frontend (5173)*" /T /F >nul 2>&1

for %%P in (8000 3000 5173) do (
    for /f "tokens=5" %%A in ('netstat -aon ^| findstr /R "[:\.]%%P[ ]" ^| findstr "LISTENING"') do (
        if not "%%A"=="0" (
            echo   - Terminando proceso en puerto %%P (PID %%A)...
            taskkill /PID %%A /T /F >nul 2>&1
        )
    )
)

echo [OK] Servicios detenidos.
echo.
if "%~1"=="" pause & goto :MENU
exit /b 0

:STATUS_ALL
echo.
echo [Earth2Worlds] Estado actual de los puertos:
echo ------------------------------------------------------------
for %%P in (8000 3000 5173) do (
    set "FOUND="
    for /f "tokens=5" %%A in ('netstat -aon ^| findstr /R "[:\.]%%P[ ]" ^| findstr "LISTENING"') do (
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
