"""Persistencia opcional de estado y artefactos en Hugging Face.

Render (plan free) usa disco efímero: cada reinicio borra la base de datos y
los archivos generados. Si el servicio define HF_TOKEN y HF_REPO (un repo
público de tipo model o dataset de tu cuenta), este módulo:

- restaura ``studio.db`` desde HF al arrancar si la copia local está vacía;
- sube un snapshot de la base cuando cambia (máximo uno cada 60 s);
- espeja los artefactos (MP4, fotos, audios) a ``media/`` y permite servirlos
  por redirección cuando ya no están en el disco local.

Sin esas variables no hace nada: el modo local y los tests no cambian.
Nunca imprime el token.
"""
from __future__ import annotations

import hashlib
import logging
import shutil
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("ai-ugc-studio.store")

DB_REMOTE = "state/studio.db"
MEDIA_PREFIX = "media"
_INTERVAL = 60.0
_thread_started = False
_last_hash = ""


def _cfg() -> tuple[str, str] | None:
    token = (getattr(settings, "HF_TOKEN", "") or "").strip()
    repo = (getattr(settings, "HF_REPO", "") or "").strip()
    if not token or not repo:
        return None
    return token, repo


def enabled() -> bool:
    return _cfg() is not None


def _api():
    from huggingface_hub import HfApi

    cfg = _cfg()
    if not cfg:
        return None
    return HfApi(token=cfg[0])


def _repo() -> str:
    cfg = _cfg()
    return cfg[1] if cfg else ""


def _repo_type() -> str:
    return (getattr(settings, "HF_REPO_TYPE", "model") or "model").strip()


# ---------- base de datos ----------

def _db_has_data() -> bool:
    if not settings.DB_PATH.exists():
        return False
    try:
        conn = sqlite3.connect(str(settings.DB_PATH))
        try:
            n = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            return int(n) > 0
        finally:
            conn.close()
    except Exception:
        return False


def restore_db() -> bool:
    """Restaura la base desde HF si la local no tiene proyectos."""
    if not enabled() or _db_has_data():
        return False
    try:
        from huggingface_hub import hf_hub_download

        got = hf_hub_download(repo_id=_repo(), repo_type=_repo_type(),
                              filename=DB_REMOTE, token=_cfg()[0])
        settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        for suffix in ("-wal", "-shm"):
            side = Path(str(settings.DB_PATH) + suffix)
            if side.exists():
                side.unlink()
        shutil.copy2(got, str(settings.DB_PATH))
        logger.info("Base de datos restaurada desde HF (%s)", DB_REMOTE)
        return True
    except Exception as exc:  # repo vacío o sin red: se sigue con base nueva
        logger.info("Sin copia previa en HF (%s)", type(exc).__name__)
        return False


def _snapshot() -> bytes:
    """Copia consistente de SQLite (incluye datos del WAL)."""
    tmp = Path(tempfile.gettempdir()) / f"snap_{time.time_ns()}.db"
    src = sqlite3.connect(str(settings.DB_PATH))
    dst = sqlite3.connect(str(tmp))
    try:
        src.backup(dst)
        dst.commit()
    finally:
        dst.close()
        src.close()
    data = tmp.read_bytes()
    tmp.unlink(missing_ok=True)
    return data


def backup_once(force: bool = False) -> bool:
    global _last_hash
    api = _api()
    if not api or not settings.DB_PATH.exists():
        return False
    try:
        data = _snapshot()
        digest = hashlib.sha256(data).hexdigest()
        if not force and digest == _last_hash:
            return False
        api.upload_file(path_or_fileobj=data, path_in_repo=DB_REMOTE,
                        repo_id=_repo(), repo_type=_repo_type())
        _last_hash = digest
        return True
    except Exception as exc:
        logger.warning("No se pudo respaldar la base en HF: %s", exc)
        return False


def start_backup_loop() -> None:
    global _thread_started
    if not enabled() or _thread_started:
        return

    def _loop() -> None:
        while True:
            time.sleep(_INTERVAL)
            backup_once()

    threading.Thread(target=_loop, name="hf-db-backup", daemon=True).start()
    _thread_started = True
    logger.info("Respaldo automático de la base en HF activo (cada %ss)", int(_INTERVAL))


# ---------- artefactos ----------

def mirror(path: str | Path) -> str:
    """Sube un artefacto a HF y devuelve su ruta remota ('' si no aplica)."""
    api = _api()
    if not api:
        return ""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return ""
    remote = f"{MEDIA_PREFIX}/{p.name}"
    try:
        api.upload_file(path_or_fileobj=str(p), path_in_repo=remote,
                        repo_id=_repo(), repo_type=_repo_type())
        return remote
    except Exception as exc:
        logger.warning("No se pudo espejar %s en HF: %s", p.name, exc)
        return ""


def remote_url(path: str | Path, download: bool = False) -> str:
    """URL pública en HF para un artefacto ya espejado."""
    if not enabled():
        return ""
    name = Path(str(path)).name
    prefix = "datasets/" if _repo_type() == "dataset" else ""
    url = f"https://huggingface.co/{prefix}{_repo()}/resolve/main/{MEDIA_PREFIX}/{name}"
    return url + "?download=true" if download else url
