"""Cola de trabajos externos (worker GPU remoto, p. ej. Kaggle).

El backend (p. ej. en Render) solo encola y sirve artefactos; el worker
remoto reclama trabajos, procesa con GPU y sube el resultado. Sin cómputo
local de vídeo en modo kaggle.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid

from app.core.config import settings

_lock = __import__("threading").Lock()


def _now() -> float:
    return time.time()


def _conn() -> sqlite3.Connection:
    from app.core.database import get_conn

    return get_conn()


def init_ext() -> None:
    conn = _conn()
    try:
        with _lock:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS ext_jobs (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'pending',
                    step TEXT DEFAULT '',
                    progress REAL DEFAULT NULL,
                    error TEXT DEFAULT '',
                    result_path TEXT DEFAULT '',
                    project_id INTEGER,
                    retries INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )
            conn.commit()
        try:
            conn.execute("ALTER TABLE ext_jobs ADD COLUMN retries INTEGER NOT NULL DEFAULT 0")
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN ext_ref TEXT")
            conn.commit()
        except Exception:
            pass
    finally:
        conn.close()


def requeue_stale(max_age_sec: float = 2700, max_retries: int = 2) -> int:
    """Devuelve a la cola trabajos 'processing' abandonados (worker caído).

    Kaggle es por sesiones: si la sesión muere a mitad de un trabajo, el
    trabajo quedaría colgado para siempre. Tras `max_age_sec` sin progreso
    se reintenta (hasta `max_retries`); después se marca 'failed' para que
    el usuario vea un error claro en vez de un spinner infinito.
    """
    init_ext()
    conn = _conn()
    try:
        with _lock:
            cutoff = _now() - max_age_sec
            rows = conn.execute(
                "SELECT id, retries FROM ext_jobs WHERE status='processing' AND updated_at<?",
                (cutoff,),
            ).fetchall()
            requeued = 0
            for row in rows:
                if (row["retries"] or 0) < max_retries:
                    conn.execute(
                        "UPDATE ext_jobs SET status='pending', retries=retries+1, "
                        "step='Reintentando (worker interrumpido)…', updated_at=? WHERE id=?",
                        (_now(), row["id"]),
                    )
                    requeued += 1
                else:
                    conn.execute(
                        "UPDATE ext_jobs SET status='failed', "
                        "error='El worker GPU se interrumpió varias veces. Vuelve a generar.', "
                        "updated_at=? WHERE id=?",
                        (_now(), row["id"]),
                    )
            conn.commit()
            return requeued
    finally:
        conn.close()



def enqueue_ext(kind: str, payload: dict, project_id: int | None = None) -> str:
    init_ext()
    ext_id = "ext_" + uuid.uuid4().hex[:10]
    conn = _conn()
    try:
        with _lock:
            conn.execute(
                "INSERT INTO ext_jobs(id,kind,payload,status,project_id,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (ext_id, kind, json.dumps(payload, ensure_ascii=False), "pending", project_id, _now(), _now()),
            )
            conn.commit()
    finally:
        conn.close()
    return ext_id


def get_ext(ext_id: str) -> dict | None:
    init_ext()
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM ext_jobs WHERE id=?", (ext_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["payload"] = json.loads(d.get("payload") or "{}")
        except Exception:
            d["payload"] = {}
        return d
    finally:
        conn.close()


def claim_next(worker_id: str) -> dict | None:
    init_ext()
    conn = _conn()
    try:
        with _lock:
            row = conn.execute(
                "SELECT * FROM ext_jobs WHERE status='pending' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE ext_jobs SET status='processing', step=?, updated_at=? WHERE id=?",
                (f"Worker {worker_id} procesando…", _now(), row["id"]),
            )
            conn.commit()
        d = dict(row)
        try:
            d["payload"] = json.loads(d.get("payload") or "{}")
        except Exception:
            d["payload"] = {}
        d["worker_id"] = worker_id
        return d
    finally:
        conn.close()


def finish_ext(ext_id: str, status: str, step: str = "", result_path: str = "", error: str = "") -> None:
    init_ext()
    conn = _conn()
    try:
        with _lock:
            conn.execute(
                "UPDATE ext_jobs SET status=?, step=?, result_path=?, error=?, updated_at=? WHERE id=?",
                (status, step, result_path, error[:2000], _now(), ext_id),
            )
            conn.commit()
    finally:
        conn.close()


def progress_ext(ext_id: str, step: str, progress: float | None = None) -> None:
    init_ext()
    conn = _conn()
    try:
        with _lock:
            conn.execute(
                "UPDATE ext_jobs SET step=?, progress=?, updated_at=? WHERE id=?",
                (step, progress, _now(), ext_id),
            )
            conn.commit()
    finally:
        conn.close()


# ---------- latido del worker (para mostrar estado en el dashboard) ----------

_last_poll = {"ts": 0.0, "gpu": "", "version": ""}


def touch_worker(gpu: str = "", version: str = "") -> None:
    """Registra que el worker está vivo (llamado en cada sondeo)."""
    _last_poll["ts"] = _now()
    if gpu:
        _last_poll["gpu"] = gpu[:120]
    if version:
        _last_poll["version"] = version[:40]


def worker_last_seen() -> dict:
    ts = _last_poll["ts"]
    return {
        "seconds_ago": None if not ts else round(_now() - ts, 1),
        "gpu": _last_poll["gpu"],
        "version": _last_poll["version"],
        "online": bool(ts) and (_now() - ts) < 90,
    }

