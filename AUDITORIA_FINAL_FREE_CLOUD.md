# AUDITORÍA FINAL — FREE CLOUD (2026-11-09)

**Coste: 0 USD.** Sin tarjetas, sin suscripciones, sin activar `ALLOW_PAID`, sin
pruebas que puedan cobrar. Solo planes gratuitos: HF Static, Render free y Kaggle.

## URLs

| Servicio | URL | Estado real |
|---|---|---|
| Dashboard | https://josjshid99-ai-ugc-studio-web.static.hf.space | ✅ 200 (HF Static) |
| Backend API | https://ai-ugc-studio-backend.onrender.com | ✅ 200 (`/api/cloud/status`) |
| Repo código | https://github.com/josephhuete57-sudo/ai-ugc-studio-cloud | ✅ rama `main` |
| Pesos (HF) | https://huggingface.co/josjshid99/ai-ugc-studio-weights | ✅ 5 archivos |
| Estado (HF) | https://huggingface.co/josjshid99/ai-ugc-studio-state | ✅ creado (vacío) |
| Worker GPU | Kaggle `josephfrancia25/ai-ugc-studio-gpu-worker` | ⛔ bloqueado: falta verificación telefónica |

## Arquitectura (la que está desplegada)

```
Navegador
  └─ Dashboard HF Static (HTML/CSS/JS, gratis)
       └─ Backend Render free (FastAPI, 512 MB, sin modelos)
            ├─ SQLite: proyectos, jobs y cola externa ext_jobs
            ├─ /api/cloud/files/...  ← sirve foto/audio/MP4 al dashboard
            └─ Cola de trabajos  ←── worker GPU Kaggle (T4 gratis)
                                     LivePortrait + Wav2Lip + edge-tts + FFmpeg
```

- **Sin cómputo local**: en `CLOUD_INFERENCE_MODE=kaggle` el backend solo encola
  y sirve archivos; tu PC únicamente abre el navegador.
- **Cola robusta**: `pending → processing → completed/failed`, progreso y paso
  visible; los trabajos abandonados por una sesión de Kaggle que muere se
  reintentan (`requeue_stale`, hasta 2 intentos) o se marcan `failed` con aviso.
- **Latido del worker**: el dashboard muestra `GPU ONLINE` / `GPU APAGADO` y un
  aviso para arrancar el kernel si está apagado.
- **Autenticación del worker**: firma **Ed25519** (`X-Worker-Timestamp` +
  `X-Worker-Signature`, ventana ±900 s). La clave privada nunca se publica; la
  pública está en `cloud/worker_public_key.txt`.
- **Persistencia opcional en HF** (`HF_TOKEN` + `HF_REPO` en Render): copia
  `studio.db` a `state/` cada minuto si cambió y espeja fotos/audios/MP4 a
  `media/`. Si Render se reinicia (disco efímero), restaura la base al arrancar
  y sirve los MP4 por redirección a HF.
- **Pesos**: alojados en HF (`wav2lip_gan_state.pth`, `s3fd.pth`,
  `landmark.onnx`, `insightface/...`); LivePortrait base/retargeting desde el
  repo oficial `KwaiVGI/LivePortrait`. Sin Google Drive.

## Verificado de verdad (hoy)

| Prueba | Resultado |
|---|---|
| Backend Render `/api/cloud/status` | ✅ 200, `mode=kaggle`, `worker_configured=true` |
| Firma Ed25519 (`tests/test_signed_auth.py`, puerto 8003) | ✅ 401 sin firma · 200 firmado · 401 caducada · 401 falsa |
| Flujo cloud completo (`tests/test_cloud_flow.py`) | ✅ subida foto+audio → proyecto → cola → claim → descarga input → subida MP4 → `completed` → `final_path` → descarga pública `video/mp4` y `attachment` |
| Persistencia HF (`tests/test_hf_store.py`) | ✅ respaldo de base (77 KB, 12 proyectos), MP4 espejado (457.960 B) y servido por redirección tras borrar el archivo local |
| Pesos en HF | ✅ 145.355.946 / 89.843.225 / 114.666.491 / 16.923.827 / 5.030.888 B |
| Kernel GPU (build) | ✅ backend + clave privada inyectados, `MAX_RUNTIME_MIN=170`, compila |
| Diagnóstico Kaggle (v2, ejecutado) | ⛔ `TORCH 2.11.0+cpu cuda False`, `NET_FAIL gaierror` → sin GPU y sin internet |

## Único bloqueo

Kaggle exige **verificación telefónica** (SMS, sin tarjeta) para dar GPU e
internet. Sin ella el kernel corre en CPU y sin red: no puede instalar
dependencias ni hablar con el backend.

👉 **Acción tuya (2 min):** https://www.kaggle.com/settings → *Phone
Verification* → verifica el número → avísame.

## Después de la verificación (lo hago yo)

1. Re-ejecutar el diagnóstico: debe dar `gpu=True net=True`.
2. `kaggle kernels push -p cloud/worker/kaggle/_build` (worker con firma).
3. Crear un trabajo real desde el dashboard público y esperar el MP4.
4. Descargar el MP4 del dashboard y comprobar con ffprobe (H.264 + AAC, > 0 s).
5. Actualizar esta auditoría con el resultado real.

## Límites gratuitos (reales)

- **Render free**: 750 h/mes, 512 MB RAM, duerme a los ~15 min sin uso
  (~30 s en despertar), disco efímero (mitigado con la persistencia HF).
- **Kaggle**: GPU T4 gratis con cuota semanal tras verificar el teléfono;
  sesión máxima 12 h (el worker se detiene solo a los 170 min para no ser
  cortado a mitad de un trabajo).
- **HF Static**: sin límite práctico para este dashboard.
- **TTS**: edge-tts (gratis, sin clave). Fish Audio es opcional y de pago; si no
  hay saldo se usa edge-tts.

## Lo que NO se ha hecho

- No se activó ningún servicio de pago ni `ALLOW_PAID`.
- No se publicó ningún secreto (`.env`, `kaggle.json`, claves) en GitHub.
- **No se afirma que la generación real de MP4 en GPU esté verificada**: falta
  la verificación telefónica de Kaggle. Todo lo demás sí está verificado.
