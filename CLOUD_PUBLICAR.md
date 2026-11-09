# PUBLICAR / OPERAR AI UGC STUDIO (gratis, sin tarjeta)

El backend y el dashboard **ya están publicados**. Este documento es el manual
para redesplegar, arrancar el worker y verificar.

## URLs actuales

- Dashboard: https://josjshid99-ai-ugc-studio-web.static.hf.space
- Backend: https://ai-ugc-studio-backend.onrender.com
- Estado de la cola: https://ai-ugc-studio-backend.onrender.com/api/cloud/status

## 1. Desplegar el backend (Render free)

El servicio `ai-ugc-studio-backend` está conectado al repo
`josephhuete57-sudo/ai-ugc-studio-cloud` y **redespliega solo** con cada push a
`main` (build: `pip install -r app/requirements.txt`).

Variables (Render → Environment):

| Variable | Valor |
|---|---|
| `CLOUD_INFERENCE_MODE` | `kaggle` |
| `CLOUD_WORKER_KEY` | generada por Render (opcional; la firma Ed25519 no la necesita) |
| `MAX_UPLOAD_MB` | `100` |
| `HF_TOKEN` | *opcional*: tu token HF (Write) para persistencia |
| `HF_REPO` | *opcional*: `josjshid99/ai-ugc-studio-state` |
| `HF_REPO_TYPE` | `model` |

Con `HF_TOKEN` + `HF_REPO`, Render guarda `state/studio.db` y `media/*` en HF:
los proyectos y los MP4 sobreviven a los reinicios (disco efímero de Render).
Sin esas variables la app funciona igual, pero un reinicio borra el historial.

Comprobar:

```powershell
Invoke-WebRequest https://ai-ugc-studio-backend.onrender.com/api/cloud/status
```

Debe responder `mode: kaggle` y `worker_configured: true`.

## 2. Desplegar el dashboard (HF Static)

```powershell
.venv\Scripts\python.exe cloud\deploy_frontend.py
```

Sube `cloud/frontend_static/` al Space `<usuario>/ai-ugc-studio-web` (SDK
`static`, gratis) e imprime la URL.

## 3. Arrancar el worker GPU (Kaggle)

Requisito: cuenta de Kaggle con **verificación telefónica** (SMS, sin tarjeta).
Sin ella el kernel no recibe GPU ni internet.

```powershell
# Empaqueta el worker con el backend y la clave privada de firma (no se publica)
.venv\Scripts\python.exe cloud\pack_kernel.py https://ai-ugc-studio-backend.onrender.com

# Comprueba la inyección (sin imprimir la clave)
.venv\Scripts\python.exe cloud\_check_build.py

# Publica y ejecuta el kernel privado
.venv\Scripts\python.exe -m kaggle kernels push -p cloud\worker\kaggle\_build
```

- `_build/` está en `.gitignore`: la clave privada Ed25519 nunca llega a GitHub.
- El kernel sondea la cola cada 30 s y se detiene a los 170 min.
- Si Kaggle cierra la sesión, relanza el kernel: los trabajos pendientes siguen
  en la cola del backend.

Estado del worker:

```powershell
.venv\Scripts\python.exe -m kaggle kernels status josephfrancia25/ai-ugc-studio-gpu-worker
```

Logs:

```powershell
.venv\Scripts\python.exe -m kaggle kernels output josephfrancia25/ai-ugc-studio-gpu-worker -p cloud\data\kaggle_out
```

## 4. Verificar de punta a punta

En local (simula Render, puerto 8003, sin GPU):

```powershell
$env:CLOUD_INFERENCE_MODE="kaggle"; $env:CLOUD_WORKER_KEY=""; $env:HF_TOKEN=""; $env:HF_REPO=""
Start-Process .\.venv\Scripts\python.exe -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8003" -WindowStyle Hidden
.venv\Scripts\python.exe tests\test_signed_auth.py
.venv\Scripts\python.exe tests\test_cloud_flow.py
```

Persistencia HF (requiere `hf auth login`):

```powershell
.venv\Scripts\python.exe tests\test_hf_store.py
```

Producción: genera un anuncio en el dashboard público y descarga el MP4. Luego:

```powershell
ffprobe -v error -show_entries stream=codec_name,width,height -show_entries format=duration archivo.mp4
```

## 5. Pesos de los modelos

Ya subidos a https://huggingface.co/josjshid99/ai-ugc-studio-weights
(`wav2lip_gan_state.pth`, `s3fd.pth`, `liveportrait/landmark.onnx`,
`insightface/models/buffalo_l/{det_10g,2d106det}.onnx`). Si hay que recrearlos:

```powershell
.venv\Scripts\python.exe cloud\upload_weights_hf.py
.venv\Scripts\python.exe cloud\upload_lp_weights_hf.py
```

## 6. Limpiar el estado de pruebas

```powershell
.venv\Scripts\python.exe cloud\clear_state.py
```

Borra `state/` y `media/` del repo HF (deja el repo listo para producción).

## Qué NO necesitas

Python, FFmpeg, LivePortrait ni Wav2Lip en tu PC para el modo cloud. El modo
local (`run_studio.bat`, puerto 8001) sigue intacto como respaldo.
