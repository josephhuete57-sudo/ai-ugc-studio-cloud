"""Backend cloud de AI UGC STUDIO (FastAPI).

Autenticación por token, trabajos asíncronos con estados, cuotas gratuitas,
modos de coste con anti-facturación y almacenamiento privado.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from cloud.common.config import settings
from cloud.common.storage import storage
from cloud.worker.orchestrator import run_pipeline

settings.check_mode()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
LOCK = threading.Lock()


def _now() -> float:
    return time.time()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(settings.DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init_db() -> None:
    c = _conn()
    try:
        with LOCK:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS cloud_jobs (
                    id TEXT PRIMARY KEY,
                    photo_key TEXT NOT NULL,
                    script TEXT NOT NULL,
                    voice TEXT NOT NULL DEFAULT 'auto',
                    driving_key TEXT DEFAULT '',
                    use_lipsync INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'pending',
                    progress REAL DEFAULT 0,
                    step TEXT DEFAULT '',
                    error TEXT DEFAULT '',
                    result_key TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS quota (
                    day TEXT PRIMARY KEY,
                    jobs INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            c.commit()
    finally:
        c.close()


def _auth(request: Request, token: Optional[str] = None) -> str:
    expected = settings.API_TOKEN
    if not expected:
        return "local-sin-token"
    given = None
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        given = auth[7:].strip()
    if given is None and token:
        given = token.strip()
    if given != expected:
        raise HTTPException(401, "Token inválido.")
    return given  # type: ignore[return-value]


class JobIn(BaseModel):
    photo_key: str
    script: str = Field(min_length=1, max_length=2000)
    voice: str = "auto"
    driving_key: Optional[str] = None
    use_lipsync: bool = True


def _new_id() -> str:
    return "job_" + str(int(_now() * 1000))


def _check_quota() -> None:
    day = time.strftime("%Y-%m-%d")
    c = _conn()
    try:
        with LOCK:
            row = c.execute("SELECT jobs FROM quota WHERE day=?", (day,)).fetchone()
            n = row["jobs"] if row else 0
            if n >= settings.MAX_DAILY_JOBS:
                raise HTTPException(429, f"Cuota gratuita diaria alcanzada ({settings.MAX_DAILY_JOBS} trabajos).")
            c.execute("INSERT INTO quota(day,jobs) VALUES(?,1) ON CONFLICT(day) DO UPDATE SET jobs=jobs+1", (day,))
            c.commit()
    finally:
        c.close()


def _update(job_id: str, **kw) -> None:
    allowed = {"status", "progress", "step", "error", "result_key"}
    fields = {k: v for k, v in kw.items() if k in allowed}
    if not fields:
        return
    c = _conn()
    try:
        with LOCK:
            sets = ", ".join(f"{k}=?" for k in fields)
            c.execute(f"UPDATE cloud_jobs SET {sets}, updated_at=? WHERE id=?",
                      list(fields.values()) + [_now(), job_id])
            c.commit()
    finally:
        c.close()


app = FastAPI(title="AI UGC STUDIO · CLOUD backend", version="1.0.0")


@app.on_event("startup")
def boot():
    init_db()
    if settings.MODE == "CLOUD_GPU" and not settings.ALLOW_PAID:
        raise ValueError("CLOUD_GPU sin ALLOW_PAID=1")


@app.get("/api/cloud/health")
def health():
    return {"status": "ok", "mode": settings.effective_mode(), "time": _now()}


@app.post("/api/cloud/upload")
def upload(file: UploadFile = File(...), _=Depends(_auth)):
    data = file.file.read()
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"Supera {settings.MAX_UPLOAD_MB} MB.")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".mp3", ".wav", ".m4a"}:
        raise HTTPException(400, f"Extensión no permitida: {ext}")
    return {"key": storage.save_bytes(file.filename or "archivo", data)}


@app.post("/api/cloud/jobs", status_code=202)
def create_job(payload: JobIn, _=Depends(_auth)):
    if not storage.exists(payload.photo_key):
        raise HTTPException(404, "Foto no encontrada en almacenamiento.")
    _check_quota()
    job_id = _new_id()
    c = _conn()
    try:
        with LOCK:
            c.execute(
                "INSERT INTO cloud_jobs(id,photo_key,script,voice,driving_key,use_lipsync,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (job_id, payload.photo_key, payload.script, payload.voice,
                 payload.driving_key or "", 1 if payload.use_lipsync else 0, _now(), _now()),
            )
            c.commit()
    finally:
        c.close()

    def worker():
        _update(job_id, status="processing", step="Generando voz…")
        try:
            result_key = run_pipeline(job_id, payload.photo_key, payload.script,
                                      payload.voice, payload.driving_key, payload.use_lipsync)
            _update(job_id, status="completed", progress=100.0, step="Completado", result_key=result_key)
        except Exception as exc:
            _update(job_id, status="failed", step="Error", error=str(exc)[:1000])

    threading.Thread(target=worker, daemon=True, name=f"cloud-{job_id}").start()
    return {"id": job_id, "status": "pending"}


@app.get("/api/cloud/jobs/{job_id}")
def get_job(job_id: str, _=Depends(_auth)):
    c = _conn()
    try:
        row = c.execute("SELECT * FROM cloud_jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Trabajo no encontrado.")
        d = dict(row)
        if d.get("result_key"):
            d["result_url"] = storage.url(d["result_key"])
        return d
    finally:
        c.close()


@app.get("/api/cloud/jobs")
def list_jobs(_=Depends(_auth)):
    c = _conn()
    try:
        return [dict(r) for r in c.execute("SELECT * FROM cloud_jobs ORDER BY created_at DESC LIMIT 50").fetchall()]
    finally:
        c.close()


@app.get("/api/cloud/mode")
def mode(_=Depends(_auth)):
    day = time.strftime("%Y-%m-%d")
    c = _conn()
    try:
        row = c.execute("SELECT jobs FROM quota WHERE day=?", (day,)).fetchone()
        used = row["jobs"] if row else 0
    finally:
        c.close()
    return {
        "mode": settings.effective_mode(),
        "allow_paid": settings.ALLOW_PAID,
        "quota_daily": settings.MAX_DAILY_JOBS,
        "quota_used": used,
        "max_job_seconds": settings.MAX_JOB_SECONDS,
        "max_video_mb": settings.MAX_VIDEO_MB,
    }


@app.get("/api/cloud/files/{key}")
def download_file(key: str, token: Optional[str] = None, _=Depends(_auth)):
    if ".." in key or "/" in key or "\\" in key:
        raise HTTPException(403, "Clave inválida.")
    if not storage.exists(key):
        raise HTTPException(404, "Archivo no encontrado.")
    tmp = settings.DATA_DIR / "dl" / key
    storage.download_to(key, tmp)
    return FileResponse(str(tmp), filename=key)
