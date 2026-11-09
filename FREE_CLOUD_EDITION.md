# FREE CLOUD EDITION — AI UGC STUDIO (0 USD)

App pública que genera anuncios UGC reales (MP4) sin usar tu PC para procesar
vídeo. Todo el cómputo ocurre en servicios gratuitos.

## Qué hay desplegado

| Pieza | Dónde | Coste |
|---|---|---|
| Dashboard | HF Static — https://josjshid99-ai-ugc-studio-web.static.hf.space | 0 |
| Backend / API | Render free — https://ai-ugc-studio-backend.onrender.com | 0 |
| Worker GPU | Kaggle T4 — kernel `josephfrancia25/ai-ugc-studio-gpu-worker` | 0 |
| Pesos de modelos | HF público — `josjshid99/ai-ugc-studio-weights` | 0 |
| Estado y MP4 (opcional) | HF público — `josjshid99/ai-ugc-studio-state` | 0 |

Sin tarjetas, sin suscripciones, sin `ALLOW_PAID`.

## Cómo se usa

1. Abre el dashboard. En «API cloud» ya viene
   `https://ai-ugc-studio-backend.onrender.com`; pulsa **Conectar**.
2. Comprueba la píldora de estado: **GPU ONLINE** = el worker está escuchando.
   Si dice **GPU APAGADO**, abre el kernel de Kaggle y pulsa *Run All*.
3. Sube una foto y un audio (o escribe el guion), pulsa **Generar mi anuncio**.
4. El trabajo entra en la cola del backend; el worker lo reclama, anima
   (LivePortrait), sincroniza labios (Wav2Lip), monta voz/subtítulos (edge-tts +
   FFmpeg) y sube el MP4.
5. El vídeo aparece en el proyecto y se descarga desde el dashboard.

## Qué se procesa dónde

- **Tu PC**: solo el navegador. Cero modelos, cero FFmpeg, cero GPU.
- **Render**: API, base de datos, cola y entrega de archivos (512 MB, sin modelos).
- **Kaggle**: LivePortrait + Wav2Lip + TTS + FFmpeg en GPU T4.

## Límites gratuitos

- **Render free**: se duerme tras ~15 min sin uso (~30 s en despertar). El worker
  lo mantiene despierto mientras sondea cada 30 s. Disco efímero: si se reinicia,
  la persistencia HF (si está configurada) recupera la base y los MP4.
- **Kaggle**: GPU gratis con cuota semanal (requiere verificación telefónica,
  SMS, sin tarjeta). El worker se apaga solo a los 170 min para terminar el
  trabajo en curso con margen.
- **Cola de 1 GPU**: los trabajos se procesan de uno en uno.
- **TTS**: edge-tts gratuito; Fish Audio es opcional y de pago (nunca obligatorio).

## Si el worker no está

El dashboard lo avisa. Los trabajos quedan en cola y se procesan cuando arrancas
el kernel. Si una sesión muere a mitad, el backend reintenta el trabajo hasta 2
veces y luego muestra un error claro (nunca un spinner infinito).

## Estado actual

Ver `AUDITORIA_FINAL_FREE_CLOUD.md` para la tabla de pruebas reales y el único
bloqueo pendiente (verificación telefónica de Kaggle).
