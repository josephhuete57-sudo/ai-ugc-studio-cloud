@echo off
chcp 65001 >nul
title AI UGC STUDIO
cd /d "%~dp0"
echo ============================================
echo  AI UGC STUDIO - motor local (CPU)
echo ============================================
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] No se encontro .venv\Scripts\python.exe en %~dp0
  pause
  exit /b 1
)
if not exist ".env" (
  echo [AVISO] No hay archivo .env. La voz Fish Audio quedara sin configurar.
  echo         Copia .env.example a .env y completa las claves.
)
set APP_HOST=127.0.0.1
set APP_PORT=8001
echo Servidor en http://127.0.0.1:8001  (8000 reservado para otros servicios)
start "" /min powershell -NoProfile -Command "Start-Sleep -Seconds 9; Start-Process 'http://127.0.0.1:8001'"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8001
pause
