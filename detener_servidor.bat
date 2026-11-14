@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [Earth2Worlds] Deteniendo servidor en el puerto 8000...
for /f "tokens=5" %%A in ('netstat -aon ^| findstr /R "[:\.]8000[ ]" ^| findstr "LISTENING"') do (
    if not "%%A"=="0" (
        echo   - Terminando proceso PID %%A...
        taskkill /PID %%A /T /F >nul 2>&1
    )
)
echo [OK] Servidor detenido.
