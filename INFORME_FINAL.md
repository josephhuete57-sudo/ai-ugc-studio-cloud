# INFORME_FINAL — AI UGC STUDIO

Fecha: 2026-11-09 · CPU-only · Servidor en `http://127.0.0.1:8001` (8000 ocupado por OpenJarvis).

## Flujo completo verificado (job #9, proyecto #1)

| Etapa | Motor | Artefacto |
|---|---|---|
| Audio | SAPI local (Helena es-ES, gratis) | `assets/audio/voz_local_1794247183.wav` (5.0 s, 16 kHz) |
| Animación | LivePortrait CPU (63 frames, ~14 min) | `exports/anim_1794247240.mp4` |
| Lip sync | Wav2Lip CPU (~3 min / 5 s audio) | `exports/lipsync_1794248095.mp4` |
| Montaje | FFmpeg (+título, subtítulos quemados) | `exports/anuncio_1794248282.mp4` |

MP4 final verificado con ffprobe + OpenCV: **H.264 720×1280 24 fps + AAC 48 kHz,
5.0 s, 120 frames, 601 KB, frame legible**. Estado del proyecto: `done`.

Extra verificado: render **1080×1920 + trim 1→3 s** → `anuncio_1794248345.mp4`
(H.264+AAC, 2.0 s). Lip-sync test manual sin usar la API: `lipsync_test.mp4`.

## Pruebas automatizadas: 10/10 OK

`unittest tests.test_studio`: health, engines, config sin secretos, upload+influencer,
guiones, persistencia, preview FFmpeg, voz local, lip-sync encola, rechazo de .exe.

## Rendimiento real en CPU (sin promesas imposibles)

- LivePortrait: ~20 s/frame ⇒ 78 frames ≈ 25 min. Recorta el driving (~2–3 s).
- Wav2Lip: ~1.1 s/frame; 5 s de audio ≈ 3 min (lote 8).
- Editor FFmpeg (720×1280, ultrafast): segundos.
- TTS local SAPI: segundos. Fish: segundos si hay saldo.

## Motores

- **LivePortrait**: pesos oficiales completos; funciona en CPU (verificado end-to-end).
- **Wav2Lip**: pesos oficiales convertidos a CPU (`wav2lip_gan_state.pth` vía
  `tests/convert_w2l.py`; `s3fd.pth` descargado de la fuente oficial del README).
  Funciona en CPU (verificado manual + API, jobs #12 y dentro del flujo #9).
- **Voces**: Fish Audio conecta (200) pero **402 sin saldo**; fallback **SAPI local
  gratuito** en español verificado (Helena/Jarvis). Fallback automático en `auto`.
- **Editor**: 720×1280 y 1080×1920, H.264/AAC, subtítulos quemados (drawtext; libass
  falla en Windows por fontconfig), título, música, volumen, trim, progreso real.

## Errores reales corregidos en esta fase

1. Servidor moría al cerrar el shell (árbol de procesos). Lanzador desacoplado
   `tests/launch_detached.py` (`CREATE_NEW_PROCESS_GROUP` + `CREATE_NO_WINDOW` hugefile).
2. LivePortrait crasheaba al final: emoji 🚀 de rich en cp1252. Fix: `PYTHONUTF8=1`.
3. Servidor 500 en /flow: `_generate_audio_auto` consumió la cabecera de `_resolve_asset`. Restaurado.
4. Wav2Lip no cargaba: peso oficial TorchScript-CUDA. Convertido a legacy dict (claves 352/352 = Wav2Lip).
5. Wav2Lip venv sin scipy/librosa/tqdm: instalados (librosa 0.9.2) en ese venv solo.
6. Upload .exe devolvía 500: ahora 400 legible.

## Limitaciones honestas

- Fish Audio requiere recargar saldo para TTS en la nube (HTTP 402 con 2 voces probadas).
- LivePortrait en CPU es lento por frame; usa driving ≤3 s para iterar.
- Sin GPU ni onnxruntime-CPU en el venv LivePortrait (se dejó el `-gpu` intacto, se fuerza CPU).
- Server arranca en 8001 porque 8000 está ocupado por OpenJarvis (no se tocó).
- Editor: sin transiciones avanzadas (zoom suave + corte disponibles).
- Sin música en `assets/music/` hasta subir una (API lista: `/api/upload/music`).

## Arranque

`run_studio.bat` → `http://127.0.0.1:8001`. Respaldos de `.env`, DB y servicios
en `*.bak_20261109` / `studio.db.bak_*`.
