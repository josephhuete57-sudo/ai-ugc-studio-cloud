# FREE CLOUD EDITION — estado y decisión (2026-11-09)

Objetivo: AI UGC STUDIO público, 100 % remoto, 0 US$, sin tarjetas ni suscripciones.

## Publicado y verificado

- **Dashboard**: https://josjshid99-ai-ugc-studio-web.static.hf.space (200, estático en HF,
  verificado con CSS y campos cloud). Es el frontend real (mismo de local).
- **Backend cloud**: `cloud/backend` (API con auth/cuotas/storage) probado en 8002.
- **Motor cloud**: adaptador Gradio (LivePortrait + Wav2Lip + edge-tts + FFmpeg) listo.
- **TTS remoto gratuito**: edge-tts real (MP3 5.5 s generado desde internet).

## Bloqueo verificado (no teórico)

1. **Hugging Face**: Space Gradio/Docker → HTTP 402 “requires a PRO subscription”.
   ZeroGPU también es PRO. Los Spaces públicos gratuitos de terceros están caídos
   (probados con y sin tu token: RUNTIME_ERROR / PAUSED / BUILD_ERROR / upstream exception).
2. **HF Inference API**: lista de proveedores vacía para LivePortrait y Wav2Lip.
3. **Render free**: 512 MB RAM < 1.5 GB que necesita LivePortrait (OOM seguro).
4. **Cloudflare Workers / Vercel**: sin GPU y límites de CPU/memoria; incapaces.
5. **Oracle free**: requiere tarjeta en el alta (prohibida por tu orden).

## La única ruta gratuita con GPU real que queda

**Worker GPU en Kaggle** (cuenta gratuita, sin tarjeta, GPU T4/P100 gratis):
un kernel que compra trabajos del backend, anima (LivePortrait), sincroniza
(Wav2Lip) y sube el MP4. Backend en Render free (512 MB, sin modelos). Todo
remoto, 0 US$. Límites: kernels ≤12 h, cola de 1 GPU, apagados si Kaggle cambia
reglas. Conflicta con tu regla anterior de “no Kaggle como producción”.

## Decisión que necesito

- **Approve Kaggle** (gratis, sin tarjeta, GPU real, frágil) → construyo el worker
  GPU en Kaggle + backend Render + enlaces, y te entrego la app completa.
- **Rechazo Kaggle y no pago** → solo puedo mantener el dashboard público; los
  modelos seguirían locales (lo que pediste evitar). No hay otra GPU gratuita.
- **PRO (9 €/mes)** → lo más sólido: deploy automático con el código ya listo.

Sin tu aprobación no activo facturación ni servicios de pago, y no uso Kaggle.
