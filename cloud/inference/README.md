---
title: AI UGC Studio Motor
emoji: 🎬
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: "5.0.0"
app_file: app.py
pinned: false
license: mit
---

# AI UGC STUDIO - Motor de IA (ZeroGPU)

LivePortrait + Wav2Lip + TTS + FFmpeg para AI UGC STUDIO.

## Funciones
- `tts(text, voice)` - voz remota gratuita (edge-tts)
- `animate(source, driving)` - LivePortrait
- `lipsync(face, audio)` - Wav2Lip
- `edit(visual, audio)` - montaje FFmpeg 720x1280

## Configuración en el Space
Variables (Settings → Variables and secrets):
- `LIVEPORTRAIT_DIR`: ruta del repo LivePortrait clonado en el Space
- `WAV2LIP_DIR`: ruta del repo Wav2Lip clonado en el Space
- Pesos LivePortrait: se descargan de `KwaiVGI/LivePortrait` (HF).
- Pesos Wav2Lip: coloca `wav2lip_gan.pth` oficial en `cloud/data/weights/`
  (la conversión a `wav2lip_gan_state.pth` la hace el adaptador).
- `s3fd.pth`: descargar `s3fd-619a316812.pth` (fuente oficial del README de
  Wav2Lip) en `Wav2Lip/face_detection/detection/sfd/s3fd.pth`.
