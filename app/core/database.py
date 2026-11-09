"""Persistencia SQLite (stdlib sqlite3, sin ORM)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings

_lock = threading.Lock()


def _now() -> float:
    return time.time()


def get_conn() -> sqlite3.Connection:
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(settings.DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        with _lock:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS influencers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    photo_path TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    influencer_id INTEGER REFERENCES influencers(id),
                    product TEXT DEFAULT '',
                    campaign TEXT DEFAULT '',
                    script TEXT DEFAULT '',
                    voice_id TEXT DEFAULT '',
                    audio_path TEXT DEFAULT '',
                    animated_path TEXT DEFAULT '',
                    lipsync_path TEXT DEFAULT '',
                    final_path TEXT DEFAULT '',
                    status TEXT DEFAULT 'draft',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    project_id INTEGER REFERENCES projects(id),
                    status TEXT NOT NULL DEFAULT 'queued',
                    step TEXT DEFAULT '',
                    progress REAL DEFAULT NULL,
                    log TEXT DEFAULT '',
                    error TEXT DEFAULT '',
                    result_path TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER REFERENCES projects(id),
                    type TEXT NOT NULL,
                    path TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                """
            )
            conn.commit()
    finally:
        conn.close()


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict[str, Any]]:
    return dict(row) if row is not None else None


# ---------------- influencers ----------------

def create_influencer(name: str, photo_path: str) -> dict:
    conn = get_conn()
    try:
        with _lock:
            cur = conn.execute(
                "INSERT INTO influencers (name, photo_path, created_at) VALUES (?, ?, ?)",
                (name, photo_path, _now()),
            )
            conn.commit()
            return get_influencer(cur.lastrowid)  # type: ignore[return-value]
    finally:
        conn.close()


def list_influencers() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM influencers ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_influencer(influencer_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        return _row_to_dict(
            conn.execute("SELECT * FROM influencers WHERE id=?", (influencer_id,)).fetchone()
        )
    finally:
        conn.close()


def delete_influencer(influencer_id: int) -> bool:
    conn = get_conn()
    try:
        with _lock:
            cur = conn.execute("DELETE FROM influencers WHERE id=?", (influencer_id,))
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


# ---------------- projects ----------------

def create_project(data: dict) -> dict:
    conn = get_conn()
    try:
        with _lock:
            cur = conn.execute(
                """INSERT INTO projects
                   (name, influencer_id, product, campaign, script, voice_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data.get("name", "Sin título"),
                    data.get("influencer_id"),
                    data.get("product", ""),
                    data.get("campaign", ""),
                    data.get("script", ""),
                    data.get("voice_id", ""),
                    data.get("status", "draft"),
                    _now(),
                    _now(),
                ),
            )
            conn.commit()
            return get_project(cur.lastrowid)  # type: ignore[return-value]
    finally:
        conn.close()


def list_projects() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_project(project_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        return _row_to_dict(
            conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        )
    finally:
        conn.close()


def update_project(project_id: int, data: dict) -> Optional[dict]:
    allowed = {
        "name", "influencer_id", "product", "campaign", "script", "voice_id",
        "audio_path", "animated_path", "lipsync_path", "final_path", "status",
    }
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return get_project(project_id)
    conn = get_conn()
    try:
        with _lock:
            assignments = ", ".join(f"{k}=?" for k in fields)
            values = list(fields.values()) + [_now(), project_id]
            conn.execute(f"UPDATE projects SET {assignments}, updated_at=? WHERE id=?", values)
            conn.commit()
            return get_project(project_id)
    finally:
        conn.close()


def delete_project(project_id: int) -> bool:
    conn = get_conn()
    try:
        with _lock:
            cur = conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


# ---------------- jobs ----------------

def create_job(kind: str, project_id: Optional[int] = None) -> int:
    conn = get_conn()
    try:
        with _lock:
            cur = conn.execute(
                "INSERT INTO jobs (kind, project_id, status, step, created_at, updated_at) VALUES (?, ?, 'queued', 'En cola', ?, ?)",
                (kind, project_id, _now(), _now()),
            )
            conn.commit()
            return cur.lastrowid  # type: ignore[return-value]
    finally:
        conn.close()


def get_job(job_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        return _row_to_dict(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
    finally:
        conn.close()


def list_jobs(limit: int = 50) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_job(job_id: int, **kwargs: Any) -> None:
    allowed = {"status", "step", "progress", "log", "error", "result_path"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    conn = get_conn()
    try:
        with _lock:
            assignments = ", ".join(f"{k}=?" for k in fields)
            conn.execute(
                f"UPDATE jobs SET {assignments}, updated_at=? WHERE id=?",
                list(fields.values()) + [_now(), job_id],
            )
            conn.commit()
    finally:
        conn.close()


def append_job_log(job_id: int, message: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    stamp = time.strftime("%H:%M:%S")
    new_log = (job.get("log") or "") + f"[{stamp}] {message}\n"
    # Mantener solo las últimas 60 líneas para no crecer sin límite.
    new_log = "\n".join(new_log.splitlines()[-60:]) + "\n"
    update_job(job_id, log=new_log)


def log_generation(project_id: Optional[int], gen_type: str, path: str | Path) -> None:
    conn = get_conn()
    try:
        with _lock:
            conn.execute(
                "INSERT INTO generations (project_id, type, path, created_at) VALUES (?, ?, ?, ?)",
                (project_id, gen_type, str(path), _now()),
            )
            conn.commit()
    finally:
        conn.close()


def list_generations(project_id: Optional[int] = None, limit: int = 100) -> list[dict]:
    conn = get_conn()
    try:
        if project_id is not None:
            rows = conn.execute(
                "SELECT * FROM generations WHERE project_id=? ORDER BY id DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM generations ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
