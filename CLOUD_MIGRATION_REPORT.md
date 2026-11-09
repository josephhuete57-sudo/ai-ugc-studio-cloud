# CLOUD_MIGRATION_REPORT — migración AI UGC STUDIO a la nube (2026-11-09)

## Qué se hizo

- Respaldo previo: `backup_precloud_20261109_123547` (código app + DB + frontend).
  La versión local (puerto 8001) sigue intacta y operativa.
- Nuevo árbol `cloud/`: backend FastAPI (auth, jobs, cuotas, modos, storage),
  adaptador Gradio/ZeroGPU (LivePortrait + Wav2Lip + edge-tts + FFmpeg),
  orquestador worker (estados pending/processing/completed/failed),
  config por env y almacenamiento local/S3.
- Frontend adaptado: `window.STUDIO_API_BASE` + token en localStorage +
  selector en la cabecera. Sin API base = modo local (sin romper nada).
- Instalación mínima en el .venv local: `gradio_client`, `edge-tts`.
  Nada más se reinstaló ni se tocó de los motores locales.

## Pruebas reales ejecutadas

| Prueba | Resultado |
|---|---|
| Health/modo backend (8002) | ✅ FREE_CLOUD |
| Auth: sin token y token malo → 401 | ✅ |
| Upload foto + rechazo .exe | ✅ |
| Job: 202 → estado (failed limpio sin INFERENCE_URL, sin fingir) | ✅ |
| Descarga de archivo con token | ✅ |
| TTS remoto gratuito (edge-tts) | ✅ MP3 real 5.5 s |
| Space público ZeroGPU (KlingTeam/innoai) | ⚠️ API conectada; generación falla dentro del Space (errores sin detalle) |
| Space motor propio (`deploy_hf.py`) | ❌ HTTP 402: Spaces Gradio/Docker exigen PRO (cuenta gratis no puede crearlos) |
| Dashboard frontend | ✅ Publicado (estático, gratis): https://josjshid99-ai-ugc-studio-web.static.hf.space |
| Spaces públicos LivePortrait/Wav2Lip (10 candidatos) | ❌ Todos en RUNTIME_ERROR / PAUSED / BUILD_ERROR (también con tu token) |
| HF Inference API (providers LivePortrait/Wav2Lip) | ❌ Ningún provider publicado |

## Límites honestos

- **Sin cuenta HF**: el despliegue del motor ZeroGPU requiere crear una cuenta
  gratuita (sin tarjeta) y subir el adaptador. Hasta entonces, los trabajos
  cloud devuelven `failed` con mensaje claro (no se simula éxito).
- Los Spaces públicos gratuitos de terceros actualmente devuelven errores
  internos al generar (verificado con 2 Spaces). Por eso el adaptador propio
  es la vía recomendada.
- Fish Audio sigue siendo opcional y requiere saldo; el TTS cloud por defecto
  es edge-tts (gratis, Microsoft).
- El modo local (8001) no se ha modificado: sigue siendo el respaldo probado.

## Para GPU de pago (futuro)

`CLOUD_MODE=CLOUD_GPU` + `ALLOW_PAID=1` en el backend y hardware de pago en el
Space. Sin ambos, el sistema se queda en FREE_CLOUD.
