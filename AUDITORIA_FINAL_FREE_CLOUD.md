# AUDITORÍA FINAL — FREE CLOUD (2026-11-09)

**Coste: 0 USD.** Sin tarjetas, sin suscripciones, sin `ALLOW_PAID`, sin HF PRO,
sin Replicate, sin Colab, sin GPU de pago.

## URLs

| Servicio | URL | Estado real |
|---|---|---|
| Dashboard | https://josjshid99-ai-ugc-studio-web.static.hf.space | ✅ 200 (HTML 13.090 B, JS 19.015 B, CSS 3.825 B) |
| Backend API | https://ai-ugc-studio-backend.onrender.com | ✅ 200 `/api/cloud/status` (`mode=kaggle`) |
| Repo código | https://github.com/josephhuete57-sudo/ai-ugc-studio-cloud | ✅ `main` @ `0123bee` |
| Pesos (HF) | https://huggingface.co/josjshid99/ai-ugc-studio-weights | ✅ 5 archivos |
| Estado (HF) | https://huggingface.co/josjshid99/ai-ugc-studio-state | ⚠️ creado, vacío, **no conectado a Render** |
| Worker GPU | Kaggle `josephfrancia25/ai-ugc-studio-gpu-worker` | ⛔ BLOQUEADO: falta verificación telefónica |

## Tabla de estado

| Componente | Resultado |
|---|---|
| Dashboard público | **LIVE** |
| Backend Render | **LIVE** |
| Kaggle GPU | **BLOCKED** (sin `nvidia-smi`, `torch 2.11.0+cpu`, `cuda False`) |
| Internet worker | **FAILED** (`gaierror(-3)`, DNS bloqueado por falta de verificación) |
| LivePortrait remoto | **NO EJECUTADO** (requiere GPU) |
| Wav2Lip remoto | **NO EJECUTADO** (requiere GPU) |
| TTS remoto | **NO EJECUTADO** (edge-tts requiere internet en Kaggle) |
| FFmpeg remoto | **NO EJECUTADO** (requiere sesión con internet) |
| Almacenamiento remoto | **PARCIAL**: entrega pública OK; espejo HF desactivado |
| MP4 real generado en GPU | **NO** |
| Descarga pública | **VERIFIED** (cadena de entrega real, archivo real) |
| Coste | **0 USD** |

## Verificado de verdad en esta ejecución

| Prueba | Resultado |
|---|---|
| `tests/test_prod_worker.py` contra Render (producción) | ✅ `PROD_CHAIN_OK` |
| Firma Ed25519 contra producción | ✅ sin firma 401 · firmada 200 · ventana ±900 s |
| Subida real de MP4 por el worker | ✅ 457.960 B → `exports/anuncio_1794251176.mp4` |
| Descarga pública inline | ✅ 200 `video/mp4` 457.960 B |
| Descarga pública attachment | ✅ 200 `attachment; filename="anuncio_1794251176.mp4"` |
| CORS dashboard → backend | ✅ `access-control-allow-origin: *` |
| Diagnóstico Kaggle v4 | ⛔ `NVIDIA_SMI_FAIL`, `TORCH 2.11.0+cpu cuda False`, `NET_FAIL gaierror`, `DIAG_DONE gpu=False net=False` |
| Persistencia HF en Render | ⚠️ `persistence=false` (faltan `HF_TOKEN`/`HF_REPO`) |

**URL pública del MP4 de prueba (cadena de entrega real):**
https://ai-ugc-studio-backend.onrender.com/api/cloud/files/anuncio_1794251176.mp4

Este MP4 es un archivo real de 457.960 B (H.264 720x1280 24 fps + AAC 48 kHz,
5,0 s) subido por el endpoint del worker y descargado por HTTP público. **No** es
una generación nueva en GPU: la GPU de Kaggle sigue bloqueada.

## Bugs reales corregidos en esta ejecución

1. **`/api/cloud/files/<nombre>` devolvía 404** para archivos en `exports/`
   (resolvía solo contra la raíz del repo). Ahora busca también en
   `assets/`, `projects/` y `exports/`, manteniendo el bloqueo de traversal.
   Era un fallo que habría impedido descargar cualquier MP4 del dashboard.
2. `Path("")` == `Path(".")` y `.exists()` es `True` → el flujo sin audio subido
   daba el audio por válido y FFmpeg habría fallado. Ahora `is_file()` + tamaño.
3. `on_gpu = _gpu() != "CPU"` era `True` para `"CPU(desconocida)"` → habría
   usado `--flag-use-half-precision` en CPU.
4. Si Kaggle entrega GPU pero `torch` es `+cpu`, LivePortrait habría corrido en
   CPU (~20 min/vídeo). Añadido `_ensure_torch_cuda()` (reinstala torch CUDA).
5. Validación de entradas descargadas (`_require_input`) con error claro.
6. `/api/cloud/status` expone `persistence` (booleano, sin secretos).

## Único bloqueo (autorización indispensable)

Kaggle exige **verificación telefónica** (SMS, gratis, sin tarjeta) para dar GPU
e internet. Comprobado hoy con el diagnóstico v4: `NVIDIA_SMI_FAIL` (no hay GPU
asignada) y `gaierror(-3)` (DNS bloqueado).

👉 https://www.kaggle.com/settings → *Phone Verification*.

## Acción opcional (no bloquea la generación)

Añadir en Render → Environment: `HF_TOKEN` (token HF Write del usuario) y
`HF_REPO=josjshid99/ai-ugc-studio-state`, `HF_REPO_TYPE=model`. Sin ellas el
backend funciona igual, pero un reinicio de Render borra proyectos y MP4
(disco efímero). Con ellas, `/api/cloud/status` mostrará `persistence: true`.

## Tras la verificación telefónica

1. `kaggle kernels push -p cloud/worker/kaggle_diag` → debe dar
   `NVIDIA_SMI_RC 0`, `GPU Tesla T4`, `cuda True`, `DNS_OK`, `HF_W2L_OK`.
2. `python cloud/pack_kernel.py https://ai-ugc-studio-backend.onrender.com`
3. `kaggle kernels push -p cloud/worker/kaggle/_build`
4. `/api/cloud/status` → `worker.online=true`, `worker.gpu="Tesla T4"`.
5. Generar un anuncio desde el dashboard y validar el MP4 con `ffprobe`.

## Lo que NO se ha hecho

- No se activó ningún servicio de pago ni `ALLOW_PAID`.
- No se publicó ningún secreto (`.env`, `kaggle.json`, clave privada Ed25519).
- No se procesó vídeo en el PC del usuario.
- No se tocó el puerto 8000 ni la app local del 8001.
- **No se afirma generación real en GPU**: sigue bloqueada por Kaggle.
