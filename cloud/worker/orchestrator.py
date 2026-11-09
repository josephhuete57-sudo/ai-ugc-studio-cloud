"""Orquestador del pipeline cloud (worker).

Llamadas al adaptador Gradio vía gradio_client (o import directo en "local").
Nunca ejecuta modelos en el proceso local si INFERENCE_URL apunta a un Space.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from cloud.common.config import settings
from cloud.common.storage import storage


def _client():
    from gradio_client import Client  # type: ignore

    if not settings.INFERENCE_URL:
        raise RuntimeError("INFERENCE_URL no configurado (URL del Space ZeroGPU).")
    return Client(settings.INFERENCE_URL)


def _call(fn_name: str, *args) -> str:
    """Llama al adaptador. En "local" (sin INFERENCE_URL) se usa import directo."""
    if settings.INFERENCE_URL:
        client = _client()
        fn = getattr(client, fn_name, None) or getattr(client, f"predict_{fn_name}", None)
        if fn is None:
            # API pública: /predict con nombre de función
            res = client.predict(*args, api_name=f"/{fn_name}")
        else:
            res = fn(*args)
        return _path_of(res)
    raise RuntimeError("INFERENCE_URL no configurado: el modo cloud no usa motores locales.")


def _path_of(res) -> str:
    if isinstance(res, str):
        return res
    if isinstance(res, dict) and "path" in res:
        return res["path"]
    if isinstance(res, (list, tuple)) and res:
        first = res[0]
        return first.get("path") if isinstance(first, dict) else str(first)
    return str(res)


def run_pipeline(job_id: str, photo_key: str, script: str, voice: str,
                 driving_key: str | None, use_lipsync: bool) -> str:
    """Cadena: voz (remoto) → LivePortrait (remoto) → Wav2Lip (remoto) → FFmpeg (remoto)."""
    work = Path(tempfile.mkdtemp(prefix=f"cloud_{job_id}_"))
    try:
        photo = storage.download_to(photo_key, work / "foto.jpg")
        audio = _call("tts", script, voice or "es-ES-ElviraNeural")
        result = audio
        if driving_key:
            driving = storage.download_to(driving_key, work / "driving.mp4")
            result = _call("animate", str(photo), str(driving))
        if use_lipsync:
            result = _call("lipsync", str(result), str(audio))
        final = _call("edit", str(result), str(audio))
        return storage.save_file("anuncio_final.mp4", final)
    finally:
        shutil.rmtree(work, ignore_errors=True)
