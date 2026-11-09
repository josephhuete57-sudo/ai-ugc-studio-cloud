@echo off
chcp 65001 >nul
title AI UGC STUDIO - CLOUD (local dev)
cd /d "%~dp0"
echo ============================================
echo  AI UGC STUDIO - CLOUD (solo desarrollo local)
echo  Backend en http://127.0.0.1:8002
echo  Requiere CLOUD_API_TOKEN e INFERENCE_URL en .env
echo ============================================
if not exist "CLOUD_ENV" if not exist ".env" (
  echo [AVISO] Falta CLOUD_ENV o .env con CLOUD_API_TOKEN / INFERENCE_URL.
)
set CLOUD_PORT=8002
start "" /min powershell -NoProfile -Command "Start-Sleep -Seconds 8; Start-Process 'http://127.0.0.1:8001'"
".venv\Scripts\python.exe" -m uvicorn cloud.backend.app:app --host 127.0.0.1 --port 8002
pause
