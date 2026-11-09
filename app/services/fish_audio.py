"""Integración Fish Audio (TTS real vía API REST). La clave nunca sale del servidor."""
from __future__ import annotations

import time
from pathlib import Path

import requests

from app.core.config import settings
from app.services.media import redact, unique_path

API_BASE = "https://api.fish.audio/v1"
MODEL_URL = "https://api.fish.audio/model"  # endpoint real verificado (200); /v1/model da 404


class FishAudioError(RuntimeError):
    pass


def _headers() -> dict:
    if not settings.FISH_AUDIO_API_KEY:
        raise FishAudioError("Falta FISH_AUDIO_API_KEY en C:\\AI_UGC_STUDIO\\.env")
    return {
        "Authorization": f"Bearer {settings.FISH_AUDIO_API_KEY}",
        "Content-Type": "application/json",
    }


def test_connection() -> dict:
    """Comprueba credenciales sin generar audio (GET /model)."""
    if not settings.fish_configured():
        return {"ok": False, "configured": False, "message": "Fish Audio no configurado en .env."}
    try:
        r = requests.get(
            MODEL_URL,
            headers={"Authorization": f"Bearer {settings.FISH_AUDIO_API_KEY}"},
            timeout=30,
        )
        if r.ok:
            return {"ok": True, "configured": True, "status": r.status_code,
                    "message": "Conexión Fish Audio OK."}
        return {"ok": False, "configured": True, "status": r.status_code,
                "message": f"Fish respondió HTTP {r.status_code}. Revisa credenciales o plan."}
    except requests.RequestException as exc:
        return {"ok": False, "configured": True, "message": f"Error de red: {redact(str(exc))}"}


def list_voices(limit: int = 10) -> dict:
    """Lista modelos/voices disponibles (si el endpoint lo permite)."""
    if not settings.fish_configured():
        return {"ok": False, "configured": False, "voices": [], "message": "Fish Audio no configurado."}
    try:
        r = requests.get(
            MODEL_URL,
            params={"page_size": limit},
            headers={"Authorization": f"Bearer {settings.FISH_AUDIO_API_KEY}"},
            timeout=30,
        )
        if not r.ok:
            return {"ok": False, "configured": True, "voices": [],
                    "message": f"Fish respondió HTTP {r.status_code}."}
        try:
            data = r.json()
        except ValueError:
            data = {}
        models = data.get("items") or data.get("models") if isinstance(data, dict) else None
        voices = []
        if isinstance(models, list):
            for m in models[:limit]:
                if isinstance(m, dict):
                    voices.append({
                        "id": m.get("_id") or m.get("id") or "",
                        "title": m.get("title") or m.get("name") or "Voz",
                    })
        if not voices and settings.FISH_AUDIO_REFERENCE_ID:
            voices = [{"id": settings.FISH_AUDIO_REFERENCE_ID, "title": "Voz configurada en .env"}]
        return {"ok": True, "configured": True, "voices": voices,
                "message": "Voces obtenidas de Fish Audio."}
    except requests.RequestException as exc:
        return {"ok": False, "configured": True, "voices": [],
                "message": f"Error de red: {redact(str(exc))}"}


def generate_audio(
    text: str,
    reference_id: str | None = None,
    fmt: str | None = None,
    speed: float = 1.0,
    output_name: str | None = None,
) -> Path:
    """Genera TTS real con Fish Audio y guarda el archivo en assets/audio."""
    text = (text or "").strip()
    if not text:
        raise FishAudioError("El guion está vacío.")
    if len(text) > 2000:
        raise FishAudioError("El guion supera 2000 caracteres (límite de Fish Audio).")
    ref = (reference_id or settings.FISH_AUDIO_REFERENCE_ID or "").strip()
    if not ref:
        raise FishAudioError("Falta FISH_AUDIO_REFERENCE_ID en .env o debe indicarse una voz.")
    fmt = (fmt or settings.FISH_AUDIO_FORMAT or "mp3").lower()
    if fmt not in ("mp3", "wav", "pcm", "opus", "flac"):
        raise FishAudioError(f"Formato no soportado por Fish Audio: {fmt}")

    payload: dict = {"text": text, "reference_id": ref, "format": fmt}
    # La API acepta speed según modelo; se envía si es distinto de 1.0 (ignorado si no aplica).
    if abs(float(speed) - 1.0) > 0.001:
        payload["speed"] = float(speed)

    try:
        r = requests.post(
            f"{API_BASE}/tts", headers=_headers(), json=payload,
            timeout=settings.FISH_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise FishAudioError(f"Error de red con Fish Audio: {redact(str(exc))}") from exc

    if r.status_code == 401:
        raise FishAudioError("Fish Audio: API key inválida (HTTP 401).")
    if r.status_code == 402:
        raise FishAudioError("Fish Audio: saldo insuficiente (HTTP 402).")
    if r.status_code == 404:
        raise FishAudioError("Fish Audio: reference_id no encontrado (HTTP 404). Revisa la voz en Fish Audio.")
    if not r.ok:
        raise FishAudioError(f"Fish Audio respondió HTTP {r.status_code}: {redact(r.text[:500])}")

    settings.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time())
    filename = output_name or f"voz_{stamp}.{fmt}"
    path = unique_path(settings.AUDIO_DIR, Path(filename).name)
    path.write_bytes(r.content)
    if path.stat().st_size < 100:
        raise FishAudioError("Fish Audio devolvió una respuesta vacía o inválida.")
    return path
