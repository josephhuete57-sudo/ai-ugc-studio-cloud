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
- **No se declara MP4 generado**: el trabajo sigue en cola por falta de cupo GPU.

---

# CIERRE REAL — 2026-11-10 15:35 (arquitectura sin LivePortrait)

LivePortrait queda **eliminado** de la cadena de ejecución (no se clona, no se
descargan sus pesos, no se instalan scikit-image/albumentations/onnx).
Cadena final, 100 % nube gratuita:

```
foto (influencer) -> edge-tts (voz) -> Wav2Lip --static -> FFmpeg (720x1280, H.264+AAC)
```

Worker: **GitHub Actions** (runner `ubuntu-latest`, CPU, sin CUDA, sin tarjeta).
Backend: Render Free. Frontend: HF Static. Autenticación Ed25519 intacta.

## MP4 entregados (reales, descargados y auditados)

| Proyecto | Archivo | Bytes | SHA-256 | Duración | Vídeo | Audio | HTTP |
|---|---|---|---|---|---|---|---|
| 3 | `anuncio_1794346272.mp4` | 744.884 | `a135390e5d92ca973bf6aee4dbdeadbd74a8b766936bf7d7949b6ee36bd8823d` | 8,667 s (208 frames) | H.264 720x1280 yuv420p 24 fps | AAC 48 kHz mono | 200 `video/mp4` |
| 2 | `anuncio_1794346293.mp4` | 747.256 | `15c3d7b6f5751e21d9629ba650d0e82f95db7976d7d38f82413aa2b73b3a2060` | 8,667 s (208 frames) | H.264 720x1280 yuv420p 24 fps | AAC 48 kHz mono | 200 `video/mp4` |

URLs públicas:

- https://ai-ugc-studio-backend.onrender.com/api/cloud/files/anuncio_1794346272.mp4
- https://ai-ugc-studio-backend.onrender.com/api/cloud/files/anuncio_1794346293.mp4

Verificación: dos descargas independientes con SHA-256 idéntico y tamaño igual
al almacenado; fotogramas distintos en t=0,5/2/4/6/8 s (vídeo con movimiento
real, no una foto fija). No se reutiliza ningún MP4 anterior.

## Prueba real en logs del runner

```
[worker 21:30:34] Job ext_edba546739 (flujo)
[worker 21:30:36] audio.py de Wav2Lip parcheado para librosa nuevo
[worker 21:31:16] Job ext_edba546739 completado -> .../anuncio_1794346272.mp4
[worker 21:31:16] Job ext_ea82468cc6 (flujo)
[worker 21:31:34] Job ext_ea82468cc6 completado -> .../anuncio_1794346293.mp4
```

## Dashboard

`https://josjshid99-ai-ugc-studio-web.static.hf.space` -> HTTP 200.
`GET /api/projects` devuelve proyecto 2 y 3 en `done` con su `final_path`; el
dashboard los muestra y permite descargar el MP4.

## Cómo lanzar un trabajo nuevo (0 USD)

```
gh workflow run worker-cpu.yml --ref worker-cpu
```

El worker arranca, reclama la cola firmada, procesa y sube el MP4 a `exports/`.

## Pendiente conocido (no bloquea la entrega)

`persistence:false` en Render: sin `HF_TOKEN`/`HF_REPO` la base es efímera y un
reinicio la borra. Los MP4 viven en el disco de Render (descargables ya) y se
pierden si Render se reinicia.
