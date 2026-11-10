# AUDITORÍA FINAL — FREE CLOUD (2026-11-10, 11:20 local / 17:20 UTC)

**Coste: 0 USD.** Sin tarjetas, sin `ALLOW_PAID`, sin HF PRO, sin Replicate, sin Colab.

## URLs

| Servicio | URL | Estado real |
|---|---|---|
| Dashboard | https://josjshid99-ai-ugc-studio-web.static.hf.space | ✅ 200 |
| Backend API | https://ai-ugc-studio-backend.onrender.com | ✅ 200 `mode=kaggle` |
| Repo código | https://github.com/josephhuete57-sudo/ai-ugc-studio-cloud | ✅ `main` @ `7565586` |
| Pesos (HF, espejo) | https://huggingface.co/josjshid99/ai-ugc-studio-weights | ✅ 5 archivos 200 |
| Pesos (HF, oficial) | https://huggingface.co/KwaiVGI/LivePortrait | ✅ 5 `.pth` 200 |
| Worker GPU | Kaggle `josephfrancia25/ai-ugc-studio-gpu-worker` | ⏳ **QUEUED** (sin cupo T4) |

## Trabajo E2E en curso

| Campo | Valor |
|---|---|
| Proyecto | 1 |
| Job local | 1 |
| Trabajo externo | `ext_6fcae63da9` |
| Estado | `pending` (en cola del backend) |
| Foto / vídeo / guion | subidos por la API pública de Render |
| Vigilante | `tests/watch_e2e.py` en segundo plano (4 h): descarga el MP4 solo cuando exista y escribe `logs/watch_e2e.log` |

## Diagnóstico del bloqueo (con prueba)

| Prueba | Resultado |
|---|---|
| Kernel GPU del worker | `QUEUED` **45+ min** sin arrancar |
| Kernel CPU de prueba (mismo usuario, `enable_gpu:false`) | **`COMPLETE` en < 45 s** |
| Conclusión | La cuenta y las sesiones funcionan; el bloqueo es **capacidad/cuota de GPU T4**, no código ni configuración |
| API Kaggle `kernels/status` | `{"status":"queued","failureMessage":"","hasFailureMessage":false}` (sin error) |

Acciones de recuperación aplicadas (todas gratis):
1. Liberadas las 2 sesiones GPU antiguas (se borraron los kernels; el latido del worker pasó de 11 s a `null`, confirmando que murieron).
2. Re-publicado el worker con las rutas de pesos corregidas (versión 2).
3. Verificado que no hay kernels duplicados (solo el worker).

## Bug real corregido (bloqueaba TODOS los jobs)

La primera sesión GPU (Tesla T4, internet OK) falló con:

```
404 Entry Not Found:
huggingface.co/KlingTeam/LivePortrait/resolve/main/pretrained_weights/liveportrait/base_models/appearance_feature_extractor.pth
```

El repo oficial publica los pesos en `liveportrait/base_models/...` (sin
`pretrained_weights/`). Corregido en `_lp_weights`: se descarga desde
`liveportrait/...` y se copia a `pretrained_weights/liveportrait/...`, donde
LivePortrait los busca. Verificado con `HEAD`: **10/10 URLs → 200**.

## Estado de la cadena

| Etapa | Estado |
|---|---|
| LivePortrait | corregido, **pendiente de GPU** |
| Wav2Lip | no ejecutado (espera a LivePortrait) |
| edge-tts | no ejecutado |
| FFmpeg | no ejecutado |
| Subida MP4 | no ejecutada |
| MP4 nuevo | **NO generado** |

## Persistencia

`persistence:false` — faltan `HF_TOKEN`, `HF_REPO`, `HF_REPO_TYPE` en Render.
Observado: un reinicio de Render borró la base (los ids volvieron a 1).

**Importante:** no se hace `git push` mientras hay un trabajo pendiente, porque
Render redespliega en cada push y el disco efímero borraría la cola. El vigilante
mantiene Render despierto con sondeos cada 60 s.

## Lo que NO se ha hecho

- No se activó ningún servicio de pago.
- No se publicó ningún secreto.
- No se procesó vídeo en el PC del usuario.
- No se usó CPU como sustituto de la GPU.
- **No se declara MP4 generado**: el trabajo sigue en cola por falta de cupo GPU.
