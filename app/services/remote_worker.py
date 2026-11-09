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
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )
            conn.commit()
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN ext_ref TEXT")
            conn.commit()
        except Exception:
            pass
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
