"""Utilidades de medios: validación de subidas, duración, dimensiones, rutas seguras."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.core.config import settings


def safe_join(base: Path, *parts: str) -> Path:
    """Une rutas evitando directory traversal."""
    target = (base.joinpath(*parts)).resolve()
    base_resolved = base.resolve()
    if base_resolved not in target.parents and target != base_resolved:
        raise ValueError("Ruta fuera del directorio permitido.")
    return target


def validate_upload(filename: str, allowed: set[str]) -> Path:
    name = Path(filename).name
    ext = Path(name).suffix.lower()
    if ext not in allowed:
        raise ValueError(f"Extensión no permitida: '{ext}'. Permitidas: {sorted(allowed)}")
    if not name or name in (".", ".."):
        raise ValueError("Nombre de archivo inválido.")
    return Path(name)


def unique_path(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stem, suffix = Path(filename).stem, Path(filename).suffix
    candidate = directory / filename
    i = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{i}{suffix}"
        i += 1
    return candidate


def probe_duration(path: str | Path) -> float | None:
    """Duración en segundos con ffprobe (None si no se puede leer)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        data = json.loads(out.stdout or "{}")
        return float(data.get("format", {}).get("duration") or 0) or None
    except Exception:
        return None


def image_size(path: str | Path) -> tuple[int, int] | None:
    try:
        from PIL import Image
        with Image.open(str(path)) as im:
            return im.size
    except Exception:
        return None


def ffmpeg_available() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=10, check=True)
        return True
    except Exception:
        return False


def redact(text: str) -> str:
    """Evita filtrar claves en logs/errores."""
    if not text:
        return text
    for secret in (settings.FISH_AUDIO_API_KEY, settings.OPENAI_API_KEY):
        if secret:
            text = text.replace(secret, "***")
    return text
