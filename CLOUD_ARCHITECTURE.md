# CLOUD_ARCHITECTURE — AI UGC STUDIO en la nube (gratis)

```
Navegador (dashboard) ──HTTPS──▶ BACKEND (FastAPI, gratis: Fly.io/Render/VPS)
                                       │ token Bearer, cola de trabajos, cuotas
                                       │ llamadas remotas (gradio_client)
                                       ▼
                                  SPACE ZeroGPU (HF, gratis) ── adaptador Gradio
                                       │ LivePortrait · Wav2Lip · edge-tts · FFmpeg
                                       │ GPU efímera gratuita (ZeroGPU)
                                       ▼
                                  STORAGE (local del contenedor o S3 gratis)
                                       │ enlaces temporales firmados
                                       ▼
                                  Dashboard: vídeo final para descargar
```

## Componentes (`cloud/`)

| Carpeta | Rol | Despliegue gratis sugerido |
|---|---|---|
| `cloud/backend/` | API: auth, usuarios, trabajos, cuotas, modos, almacenamiento | Fly.io / Render free (Docker) |
| `cloud/inference/app.py` | Adaptador Gradio: LivePortrait + Wav2Lip + edge-tts + FFmpeg | HF Space gratis (ZeroGPU) |
| `cloud/worker/` | Orquestador (cadena voz→animación→lip→montaje) | dentro del backend o proceso aparte |
| `cloud/common/` | Config por env + storage local/S3 | — |

## Costes (anti-facturación)

- `CLOUD_MODE=FREE_CLOUD` por defecto; `CLOUD_GPU` exige `ALLOW_PAID=1` explícito.
  Sin eso, el backend arranca en FREE y rechaza el modo de pago.
- Cuotas: `CLOUD_MAX_DAILY_JOBS=10`, `CLOUD_MAX_JOB_SECONDS=1800`, `CLOUD_MAX_VIDEO_MB=200`.
- Sin servicios de pago activados automáticamente. Sin Google Colab/Kaggle.

## Seguridad

- Token Bearer (`CLOUD_API_TOKEN`) en cabecera y `?token=` para archivos.
- Claves solo por variables de entorno. Validación de extensiones y tamaños.
- Storage privado (claves con hash, sin acceso directo sin token/URL firmada).

## Estado de las pruebas (2026-11-09, verificado)

- Backend cloud local (puerto 8002): auth 401/OK, upload, job 202, estados, descarga. OK.
- TTS remoto gratuito real (edge-tts): 5.5 s MP3 generado desde el PC. OK.
- Space público ZeroGPU (KlingTeam/LivePortrait, innoai): API conectada,
  generación falla en el propio Space (cola/errores sin detalle). Patrón viable;
  con tu propio Space (HF) queda bajo control.
- Adaptador propio (`cloud/inference/app.py`): listo para desplegar; requiere
  cuenta HF gratuita + repos LivePortrait/Wav2Lip en el Space.
