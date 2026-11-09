# CLOUD_API_DOCUMENTATION — backend de AI UGC STUDIO

Base: `https://<BACKEND>/api/cloud/` · Auth: cabecera `Authorization: Bearer <CLOUD_API_TOKEN>`
(los archivos también aceptan `?token=`). Errores: `401` token · `400` validación ·
`404` no encontrado · `413` tamaño · `429` cuota. Todo POST es JSON salvo upload.

## GET /health
`{status, mode, time}` — sin auth.

## GET /mode
Modo efectivo, `allow_paid`, cuota diaria/usada, límites de duración/tamaño.

## POST /upload (multipart `file`)
Devuelve `{key}` (clave privada de almacenamiento). Extensiones: jpg/png/webp/mp4/mov/mp3/wav/m4a.

## POST /jobs
`{photo_key, script, voice?, driving_key?, use_lipsync?}` → `202 {id, status: "pending"}`.
El worker remoto ejecuta: voz → LivePortrait → Wav2Lip → FFmpeg.

## GET /jobs/{id}
`{id, status, progress, step, error, result_key, result_url}`.
Estados: `pending → processing → completed | failed`.

## GET /jobs
Últimos 50 trabajos.

## GET /files/{key}
Descarga (token en cabecera o `?token=`). Con S3 devuelve URL firmada de 1 h.
