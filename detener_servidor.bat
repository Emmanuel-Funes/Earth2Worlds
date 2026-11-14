@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [Earth2Worlds] Deteniendo servidor en el puerto 8000...

taskkill /FI "WINDOWTITLE eq Earth2Worlds*" /T /F >nul 2>&1

for /f "tokens=5" %%A in ('netstat -aon ^| findstr /r /c:"[:\.]8000 " ^| findstr "LISTENING"') do (
    if not "%%A"=="0" (
        tasklist /FI "PID eq %%A" 2>nul | findstr /i /r "python uvicorn node cmd" >nul
        if not errorlevel 1 (
            echo   - Terminando servidor (PID %%A)...
            taskkill /PID %%A /T /F >nul 2>&1
        )
    )
)

echo [OK] Servidor detenido de forma segura.

