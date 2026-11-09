# AI UGC STUDIO — aplicación local + cloud de anuncios UGC (CPU / remoto)

App web que produce anuncios UGC completos desde una foto y un guion:

```
Foto → LivePortrait (animación) → Wav2Lip (labios) → voz (Fish/local) → subtítulos → MP4 9:16
```

## Arranque

- **Local (CPU)**: `run_studio.bat` → `http://127.0.0.1:8001` (el 8000 está ocupado por otro servicio).
- **Manual**: `.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001`
- **Cloud gratis**: ver `FREE_CLOUD_EDITION.md` y `CLOUD_PUBLICAR.md`.

## Cloud gratis (0 USD, sin cómputo en tu PC)

| Pieza | Servicio | URL |
|---|---|---|
| Dashboard | HF Static | https://josjshid99-ai-ugc-studio-web.static.hf.space |
| Backend / API | Render free | https://ai-ugc-studio-backend.onrender.com |
| Worker GPU | Kaggle T4 | kernel `josephfrancia25/ai-ugc-studio-gpu-worker` |
| Pesos | HF | https://huggingface.co/josjshid99/ai-ugc-studio-weights |

En modo `CLOUD_INFERENCE_MODE=kaggle` el backend solo encola y entrega archivos;
el worker de Kaggle hace LivePortrait + Wav2Lip + TTS + FFmpeg. La cola
(`ext_jobs`) tiene progreso, reintento de trabajos huérfanos y latido del worker
(el dashboard muestra `GPU ONLINE` / `GPU APAGADO`). El worker se autentica con
firma Ed25519 (sin compartir secretos). Ver `AUDITORIA_FINAL_FREE_CLOUD.md` para
el estado verificado y el único bloqueo pendiente (verificación telefónica de
Kaggle).

Sin CUDA: todo el stack local corre en CPU. LivePortrait de ~3 s (78 frames) tarda
~20 min en CPU con 2 hilos; recorta el vídeo de referencia para iterar rápido.
La UI no se bloquea: trabajos en segundo plano con log, progreso y cancelación.

## Voz (dos proveedores, uno gratuito)

- **Fish Audio** (`POST /v1/tts`): claves y saldo en `.env`. Conecta OK; sin saldo HTTP 402.
- **Local Windows SAPI (gratis)**: voces `Microsoft Helena (es-ES)` y `Jarvis (es-MX)`.
  Sin cuenta ni saldo. El flujo usa `auto`: prueba Fish y cae a SAPI si falla.

## Wav2Lip (pesos oficiales convertidos)

`wav2lip_gan.pth` oficial viene como TorchScript con CUDA; se convierte UNA vez:

```
Wav2Lip\.venv\Scripts\python.exe tests\convert_w2l.py
```

→ `Wav2Lip\checkpoints\wav2lip_gan_state.pth`. `s3fd.pth` va en
`Wav2Lip\face_detection\detection\sfd\s3fd.pth`.

## Perfil LOW_RAM_12GB

Máximo 2 hilos, batch mínimo, `source_max_dim=512`, `-threads 2` en FFmpeg,
pausa automática si RAM libre < 2.5 GB, limpieza de temporales y monitor
de RAM/CPU en el dashboard (`/api/system/memory`). Ver `RAM_OPTIMIZATION_REPORT.md`.

## Flujo «GENERAR MI ANUNCIO»

Audio (Fish o SAPI) → Animación LivePortrait CPU → Lip sync Wav2Lip (opcional, real) →
Subtítulos SRT + quemado → MP4 720×1280 o 1080×1920 (H.264 ultrafast CPU + AAC).
Reutiliza etapas completadas al reintentar.

## Configuración (`.env`)

| Variable | Uso |
|---|---|
| `FISH_AUDIO_API_KEY` / `FISH_AUDIO_REFERENCE_ID` | Voz Fish Audio (servidor; nunca va al frontend) |
| `FISH_AUDIO_FORMAT` | `mp3` por defecto |
| `VIDEO_WIDTH` / `VIDEO_HEIGHT` / `VIDEO_FPS` | Salida por defecto (720×1280, 24) |
| `APP_PORT` | Puerto (8001 por defecto) |
| `OPENAI_API_KEY` (opcional) | LLM real para guiones; sin ella, plantillas UGC editables |
| `MAX_UPLOAD_MB` | Límite de subidas (25 por defecto) |
| `PROFILE` / `CPU_THREADS` / `MIN_FREE_RAM_GB` | Perfil de memoria (ver arriba) |
| `HF_TOKEN` / `HF_REPO` / `HF_REPO_TYPE` | Opcional: persiste base y MP4 en HF (sobrevive a reinicios de Render) |

## Estructura

```
app/main.py                 FastAPI + estáticos (local)
cloud/                      backend + adaptador ZeroGPU + worker + docs
app/api/routes.py           REST local
app/core/{config,database,jobs,memory}.py   .env, SQLite, cola 1 worker, monitor RAM
app/services/{fish_audio,local_tts,animation,video_editor,subtitles,script_writer,maintenance,media}.py
app/frontend/               SPA oscura (vanilla JS; modo local o cloud con token)
assets/ projects/ exports/ logs/ tests/
run_studio.bat  run_cloud.bat
```

## Pruebas

`.venv\Scripts\python.exe -m unittest tests.test_studio -v` (backend local en 8001).
