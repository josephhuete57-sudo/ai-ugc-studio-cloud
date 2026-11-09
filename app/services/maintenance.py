"""Limpieza segura de archivos temporales (nunca toca proyectos ni exports finales)."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from app.core.config import settings


def _older_than(path: Path, max_age_days: float) -> bool:
    try:
        return (time.time() - path.stat().st_mtime) > max_age_days * 86400
    except OSError:
        return False


def cleanup_temp_safe() -> dict:
    """Elimina solo temporales viejos: result.avi de Wav2Lip, render_* antiguos,
    .pkl de caché de motion templates antiguos. Devuelve contadores (nunca lanza)."""
    removed = {"archivos": 0, "carpetas": 0, "bytes": 0}

    def _remove_file(p: Path) -> None:
        try:
            removed["bytes"] += p.stat().st_size
            p.unlink(missing_ok=True)
            removed["archivos"] += 1
        except OSError:
            pass

    # Temp de Wav2Lip (result.avi y similares, >1 día)
    temp_dir = settings.WAV2LIP_DIR / "temp"
    if temp_dir.exists():
        for p in temp_dir.iterdir():
            if p.is_file() and p.name != "README.md" and _older_than(p, 1.0):
                _remove_file(p)

    # Carpetas render_* de subtítulos que ya no corresponden a un anuncio activo (>1 día)
    subs_dir = settings.PROJECTS_DIR / "subs"
    if subs_dir.exists():
        for d in subs_dir.iterdir():
            if d.is_dir() and d.name.startswith("render_") and _older_than(d, 1.0):
                try:
                    removed["bytes"] += sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                    shutil.rmtree(d, ignore_errors=True)
                    removed["carpetas"] += 1
                except OSError:
                    pass

    # Caché de motion templates de LivePortrait (>7 días, solo la carpeta de ejemplos)
    pkl_dir = settings.LIVEPORTRAIT_DIR / "assets" / "examples" / "driving"
    if pkl_dir.exists():
        for p in pkl_dir.glob("*.pkl"):
            if _older_than(p, 7.0):
                _remove_file(p)

    return removed
