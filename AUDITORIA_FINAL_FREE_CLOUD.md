# AUDITORÍA FINAL — FREE CLOUD (actualizada 2026-11-10)

**Coste: 0 USD.** Sin tarjetas, sin `ALLOW_PAID`, sin HF PRO, sin Replicate, sin Colab.

## URLs

| Servicio | URL | Estado real |
|---|---|---|
| Dashboard | https://josjshid99-ai-ugc-studio-web.static.hf.space | ✅ 200 |
| Backend API | https://ai-ugc-studio-backend.onrender.com | ✅ 200 `mode=kaggle` |
| Repo código | https://github.com/josephhuete57-sudo/ai-ugc-studio-cloud | ✅ `main` @ `afbf637` |
| Pesos (HF) | https://huggingface.co/josjshid99/ai-ugc-studio-weights | ✅ 5 archivos (HTTP 200) |
| Pesos oficiales LP | https://huggingface.co/KwaiVGI/LivePortrait | ✅ 5 `.pth` (HTTP 200) |
| Worker GPU | Kaggle `josephfrancia25/ai-ugc-studio-gpu-worker` | ⏳ **QUEUED** (sin cupo de GPU libre) |

## Tabla de estado

| Componente | Resultado |
|---|---|
| Dashboard | **LIVE** |
| Render | **LIVE** |
| Kaggle verificado (GPU asignada) | **YES** — el worker reportó `Tesla T4` |
| GPU NVIDIA | **ONLINE** (sesión real ejecutada hoy) |
| Internet | **OK** — HTTPS a HF funcionó (respuesta real 404 de la API) |
| Worker | **QUEUED** (nueva versión esperando cupo de GPU) |
| LivePortrait GPU | **FAILED** → causa encontrada y corregida (rutas de pesos) |
| Wav2Lip | **NO EJECUTADO** (no llegó a esa etapa) |
| edge-tts | **NO EJECUTADO** |
| FFmpeg | **NO EJECUTADO** |
| Almacenamiento | **PARCIAL** — entrega pública OK; espejo HF desactivado (`persistence:false`) |
| MP4 NUEVO generado | **NO** |
| Descarga pública | **VERIFIED** (archivo real subido por el worker, no generación nueva) |
| Coste | **0 USD** |

## Prueba E2E lanzada (pendiente de GPU)

- Proyecto **1**, job local **1**, trabajo externo **`ext_6fcae63da9`**, estado `pending`.
- Foto + vídeo de referencia + guion subidos por la API pública de Render.
- El worker lo procesará al arrancar la sesión de Kaggle (sin intervención manual).

## Bug real encontrado en la primera ejecución GPU (corregido)

La sesión GPU **sí arrancó** (Tesla T4, internet OK) y falló con:

```
404 Entry Not Found:
https://huggingface.co/KlingTeam/LivePortrait/resolve/main/pretrained_weights/liveportrait/base_models/appearance_feature_extractor.pth
```

Causa: el repo oficial de LivePortrait publica los pesos en
`liveportrait/base_models/...` (sin el prefijo `pretrained_weights/`). El worker
pedía la ruta con prefijo y recibía 404 en **todos** los jobs.

Corregido en `cloud/worker/kaggle/kernel.py` (`_lp_weights`): descarga desde
`liveportrait/...` y copia a `pretrained_weights/liveportrait/...`, que es donde
LivePortrait los busca. Verificado con `HEAD` real: **10/10 URLs devuelven 200**
(3.387.959 / 112.545.506 / 221.813.590 / 182.180.086 / 2.393.098 B oficiales y
los 5 del espejo propio).

## Bloqueo actual (externo, no de código)

La cuenta ya tiene GPU e internet, pero Kaggle limita a **2 sesiones GPU
simultáneas** y ahora mismo no hay cupo libre: el kernel queda en `QUEUED`.
Durante la espera:

- el trabajo permanece `pending` en la cola del backend (no se pierde);
- al liberarse una GPU, el worker arranca, reclama `ext_6fcae63da9` y ejecuta
  LivePortrait → Wav2Lip → edge-tts → FFmpeg → subida del MP4.

## Nota de persistencia

`/api/cloud/status` → `persistence:false`: faltan `HF_TOKEN` y `HF_REPO` en
Render. Consecuencia real observada: Render se reinició y la base volvió a 0
proyectos. Añadir en Render → Environment (lo pega el usuario, nunca en el chat):

```
HF_TOKEN=<token HF Write>
HF_REPO=josjshid99/ai-ugc-studio-state
HF_REPO_TYPE=model
```

## Lo que NO se ha hecho

- No se activó ningún servicio de pago.
- No se publicó ningún secreto.
- No se procesó vídeo en el PC del usuario.
- No se tocó el puerto 8000 ni la app local del 8001.
- **No se declara MP4 nuevo generado**: el trabajo sigue en cola por falta de cupo GPU.
