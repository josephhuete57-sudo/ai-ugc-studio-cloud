"""Rutas REST de AI UGC STUDIO (validación, límites y rutas seguras)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.core import database, jobs, memory
from app.core.config import settings
from app.services import (animation, cloud_store, fish_audio, local_tts, maintenance,
                          media, remote_worker, script_writer, subtitles, video_editor)


def _mirror_async(path: Path | str) -> None:
    """Espeja un artefacto en HF sin bloquear la petición (si está activo)."""
    if not cloud_store.enabled():
        return
    import threading

    threading.Thread(target=cloud_store.mirror, args=(path,), daemon=True).start()


def _worker_pubkey() -> bytes:
    """Clave pública Ed25519 del worker (publicada en el repo, no es secreta)."""
    try:
        raw = (settings.BASE_DIR / "cloud" / "worker_public_key.txt").read_text(encoding="utf-8").strip()
        return bytes.fromhex(raw) if raw else b""
    except Exception:
        return b""


def _worker_key_ok(request: Request) -> bool:
    expected = settings.CLOUD_WORKER_KEY
    if expected and request.headers.get("x-worker-key", "") == expected:
        return True
    # Firma Ed25519: no requiere ningún secreto configurado en el backend.
    pub = _worker_pubkey()
    if not pub:
        return False
    ts = request.headers.get("x-worker-timestamp", "")
    sig = request.headers.get("x-worker-signature", "")
    if not ts or not sig:
        return False
    try:
        if abs(time.time() - int(ts)) > 900:
            return False
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        key = Ed25519PublicKey.from_public_bytes(pub)
        key.verify(bytes.fromhex(sig), f"{ts}:{request.url.path}".encode())
        return True
    except Exception:
        return False

router = APIRouter(prefix="/api", tags=["studio"])


# ---------- esquemas ----------

class ProjectIn(BaseModel):
    name: str = "Sin título"
    influencer_id: Optional[int] = None
    product: str = ""
    campaign: str = ""
    script: str = ""
    voice_id: str = ""
    status: str = "draft"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    influencer_id: Optional[int] = None
    product: Optional[str] = None
    campaign: Optional[str] = None
    script: Optional[str] = None
    voice_id: Optional[str] = None
    audio_path: Optional[str] = None
    animated_path: Optional[str] = None
    lipsync_path: Optional[str] = None
    final_path: Optional[str] = None
    status: Optional[str] = None


class ScriptIn(BaseModel):
    product: str
    campaign: str = ""
    tone: str = "conversacional"


class InfluencerIn(BaseModel):
    name: str
    photo_path: str


class EditorPreviewIn(BaseModel):
    image_path: str
    project_id: Optional[int] = None


class SubtitlesIn(BaseModel):
    text: str
    audio_path: str


class VoiceIn(BaseModel):
    text: str
    reference_id: Optional[str] = None
    format: Optional[str] = None
    speed: float = 1.0
    filename: Optional[str] = None
    project_id: Optional[int] = None
    provider: str = "auto"  # auto | fish | local (SAPI Windows)
    voice_name: Optional[str] = None


class AnimateIn(BaseModel):
    source_path: str = ""
    driving_path: str = ""
    influencer_id: Optional[int] = None
    project_id: Optional[int] = None


class LipSyncIn(BaseModel):
    face_path: str = ""
    audio_path: str = ""
    project_id: Optional[int] = None


class EditorIn(BaseModel):
    visual_path: str
    audio_path: Optional[str] = None
    music_path: Optional[str] = None
    subtitles_path: Optional[str] = None
    title: str = ""
    voice_volume: float = 1.0
    music_volume: float = 0.25
    zoom: bool = True
    resolution: str = "720x1280"  # 720x1280 | 1080x1920
    trim_start: float = 0.0
    trim_end: Optional[float] = None
    project_id: Optional[int] = None


class FlowIn(BaseModel):
    project_id: int
    influencer_photo: str = ""
    driving_video: str = ""
    use_lipsync: bool = False
    music_path: Optional[str] = None
    title: str = ""
    audio_provider: str = "auto"  # auto | fish | local (fallback automático si Fish no tiene saldo)
    resolution: str = "720x1280"
    # Cloud: audio ya subido por el usuario y/o guion explícito (sin Fish)
    audio_path: Optional[str] = None
    script: str = ""
    voice_id: Optional[str] = None


# ----------helpers ----------

def _check_size(upload: UploadFile) -> None:
    if upload.size is not None and upload.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"El archivo supera {settings.MAX_UPLOAD_MB} MB.")


def _save_upload(upload: UploadFile, directory: Path, allowed: set[str]) -> Path:
    try:
        target = media.validate_upload(upload.filename or "", allowed)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    directory.mkdir(parents=True, exist_ok=True)
    path = media.unique_path(directory, target.name)
    try:
        path.write_bytes(upload.file.read())
    except Exception as exc:
        raise HTTPException(500, f"No se pudo guardar el archivo: {media.redact(str(exc))}") from exc
    if path.stat().st_size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        path.unlink(missing_ok=True)
        raise HTTPException(413, f"El archivo supera {settings.MAX_UPLOAD_MB} MB.")
    return path


def _generate_audio_auto(text: str, reference_id: str | None, provider: str, voice_name: str | None) -> Path:
    """Fish primero (si aplica) con fallback local SAPI; nunca simula audio."""
    want = (provider or "auto").lower()
    if want in ("fish", "auto") and reference_id is not None:
        try:
            path = fish_audio.generate_audio(text, reference_id)
            return path
        except fish_audio.FishAudioError:
            if want == "fish":
                raise
            # Fallback local gratuito (p. ej. saldo insuficiente 402 en Fish).
            try:
                return local_tts.synthesize(text, voice_name)
            except local_tts.LocalTTSError as exc:
                raise fish_audio.FishAudioError(f"Fish Audio no disponible y TTS local falló: {exc}") from exc
    if want == "local":
        return local_tts.synthesize(text, voice_name)
    return local_tts.synthesize(text, voice_name)


def _resolve_asset(path_str: str) -> Path:
    """Resuelve un path solo dentro de assets/projects/exports."""
    if not path_str:
        raise HTTPException(400, "Falta la ruta del archivo.")
    candidate = Path(path_str)
    if not candidate.is_absolute():
        candidate = settings.BASE_DIR / path_str
    candidate = candidate.resolve()
    allowed_roots = [settings.ASSETS_DIR.resolve(), settings.PROJECTS_DIR.resolve(),
                     settings.EXPORTS_DIR.resolve(), settings.BASE_DIR.resolve()]
    for root in allowed_roots:
        try:
            candidate.relative_to(root)
            break
        except ValueError:
            continue
    else:
        raise HTTPException(403, "Ruta no permitida.")
    if not candidate.exists():
        raise HTTPException(404, f"Archivo no encontrado: {candidate.name}")
    return candidate


# ---------- salud / motores ----------

@router.get("/health")
def health():
    return {"status": "ok", "app": "AI UGC STUDIO", "time": time.time()}


@router.get("/config")
def public_config():
    return {
        "video_width": settings.VIDEO_WIDTH,
        "video_height": settings.VIDEO_HEIGHT,
        "video_fps": settings.VIDEO_FPS,
        "fish_configured": settings.fish_configured(),
        "llm_configured": settings.llm_configured(),
        "max_upload_mb": settings.MAX_UPLOAD_MB,
        "profile": settings.PROFILE,
        "cpu_threads": settings.CPU_THREADS,
        "ffmpeg_threads": settings.FFMPEG_THREADS,
        "min_free_ram_gb": settings.MIN_FREE_RAM_GB,
    }


@router.post("/system/cleanup")
def system_cleanup():
    return maintenance.cleanup_temp_safe()


@router.get("/system/memory")
def system_memory():
    snap = memory.memory_snapshot()
    running = [j for j in database.list_jobs(20) if j["status"] in ("running", "queued")]
    current = running[0] if running else None
    # ETA estimado solo cuando hay histórico suficiente del mismo tipo de trabajo.
    eta = None
    if current:
        done = [j for j in database.list_jobs(80)
                if j["kind"] == current["kind"] and j["status"] == "done"]
        if done:
            elapsed = []
            for j in done:
                try:
                    elapsed.append(max(1.0, j["updated_at"] - j["created_at"]))
                except Exception:
                    continue
            if elapsed:
                avg = sum(elapsed) / len(elapsed)
                prog = current.get("progress") or 0
                if prog and prog > 5:
                    eta = round(avg * (100 - prog) / max(prog, 1), 1)
                else:
                    eta = round(avg, 1)
    return {
        **snap,
        "stage": (f"{current['kind']} · {current['step']}" if current else "En espera"),
        "eta_seconds": eta,
    }


@router.get("/engines")
def engines():
    last_done = {j["kind"]: j["updated_at"] for j in database.list_jobs(80) if j["status"] == "done"}
    return {
        "liveportrait": animation.liveportrait_check(),
        "wav2lip": animation.wav2lip_check(),
        "fish_audio": fish_audio.test_connection(),
        "local_tts": {"available": True, "provider": "SAPI Windows (gratuito)",
                      "message": "Voces locales es-ES/es-MX disponibles sin saldo."},
        "ffmpeg": {"available": media.ffmpeg_available()},
        "ffprobe": {"available": True},
        "last_successful_jobs": last_done,
    }


# ---------- influencers ----------

@router.post("/influencers/upload")
async def upload_influencer(photo: UploadFile = File(...)):
    _check_size(photo)
    path = _save_upload(photo, settings.INFLUENCERS_DIR, settings.ALLOWED_IMAGES)
    _mirror_async(path)
    return {"path": str(path), "url": f"/api/assets?path={path.as_posix()}"}


@router.post("/influencers")
def create_influencer(payload: InfluencerIn):
    _resolve_asset(payload.photo_path)
    return database.create_influencer(name=payload.name, photo_path=payload.photo_path)


@router.get("/influencers")
def list_influencers():
    return database.list_influencers()


@router.delete("/influencers/{influencer_id}")
def delete_influencer(influencer_id: int):
    if not database.delete_influencer(influencer_id):
        raise HTTPException(404, "Influencer no encontrado.")
    return {"ok": True}


# ---------- proyectos ----------

@router.post("/projects")
def create_project(payload: ProjectIn):
    return database.create_project(payload.model_dump())


@router.get("/projects")
def list_projects():
    return database.list_projects()


@router.get("/projects/{project_id}")
def get_project(project_id: int):
    project = database.get_project(project_id)
    if not project:
        raise HTTPException(404, "Proyecto no encontrado.")
    return project


@router.patch("/projects/{project_id}")
def update_project(project_id: int, payload: ProjectUpdate):
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    updated = database.update_project(project_id, data)
    if not updated:
        raise HTTPException(404, "Proyecto no encontrado.")
    return updated


@router.delete("/projects/{project_id}")
def delete_project(project_id: int):
    if not database.delete_project(project_id):
        raise HTTPException(404, "Proyecto no encontrado.")
    return {"ok": True}


@router.get("/projects/{project_id}/history")
def project_history(project_id: int):
    if not database.get_project(project_id):
        raise HTTPException(404, "Proyecto no encontrado.")
    return database.list_generations(project_id)


# ---------- guiones ----------

@router.post("/scripts/generate")
def generate_scripts(payload: ScriptIn):
    try:
        return script_writer.generate_scripts(payload.product, payload.campaign, payload.tone)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# ---------- voz Fish Audio ----------

@router.get("/voice/test")
def voice_test():
    return fish_audio.test_connection()


@router.get("/voice/list")
def voice_list():
    return fish_audio.list_voices()


@router.post("/voice/generate")
def voice_generate(payload: VoiceIn):
    try:
        path = _generate_audio_auto(payload.text, payload.reference_id, payload.provider, payload.voice_name)
    except (fish_audio.FishAudioError, local_tts.LocalTTSError) as exc:
        raise HTTPException(400, str(exc)) from exc
    if payload.project_id:
        database.update_project(payload.project_id, {"audio_path": str(path), "status": "audio"})
        database.log_generation(payload.project_id, "audio", path)
    return {"path": str(path), "url": f"/api/assets?path={path.as_posix()}", "size": path.stat().st_size}


@router.get("/voice/local/list")
def voice_local_list():
    try:
        voices = local_tts.list_voices()
        return {"ok": True, "voices": voices}
    except local_tts.LocalTTSError as exc:
        return {"ok": False, "voices": [], "message": str(exc)}


# ---------- subidas de referencia ----------

@router.post("/upload/video")
async def upload_video(video: UploadFile = File(...)):
    _check_size(video)
    path = _save_upload(video, settings.PROJECTS_DIR / "uploads", settings.ALLOWED_VIDEOS)
    return {"path": str(path), "url": f"/api/assets?path={path.as_posix()}"}


@router.post("/upload/audio")
async def upload_audio(audio: UploadFile = File(...)):
    _check_size(audio)
    path = _save_upload(audio, settings.AUDIO_DIR, settings.ALLOWED_AUDIOS)
    _mirror_async(path)
    return {"path": str(path), "url": f"/api/assets?path={path.as_posix()}"}


@router.post("/upload/music")
async def upload_music(music: UploadFile = File(...)):
    _check_size(music)
    path = _save_upload(music, settings.MUSIC_DIR, settings.ALLOWED_AUDIOS | {".mp4"})
    _mirror_async(path)
    return {"path": str(path), "url": f"/api/assets?path={path.as_posix()}"}


# ---------- animación LivePortrait (job) ----------

def _enqueue_remote(kind: str, ext_kind: str, payload: dict, project_id: int | None) -> dict:
    """Encola en la cola externa y devuelve el job local enlazado (UI sin cambios)."""
    from app.core import database as _db

    ext_id = remote_worker.enqueue_ext(ext_kind, payload, project_id)
    local_id = _db.create_job("remoto_" + ext_kind, project_id)
    _db.update_job(local_id, step=f"Remoto ({ext_id}) en cola…")
    conn = _db.get_conn()
    try:
        with _db._lock:
            conn.execute("UPDATE jobs SET ext_ref=? WHERE id=?", (ext_id, local_id))
            conn.commit()
    finally:
        conn.close()
    return {"job_id": local_id, "status": "queued", "ext_id": ext_id}


@router.post("/animation/run")
def animation_run(payload: AnimateIn):
    source = payload.source_path
    if payload.influencer_id and not source:
        inf = database.get_influencer(payload.influencer_id)
        if not inf:
            raise HTTPException(404, "Influencer no encontrado.")
        source = inf["photo_path"]
    source_path = _resolve_asset(source)
    driving_path = _resolve_asset(payload.driving_path)
    if settings.CLOUD_INFERENCE_MODE == "kaggle":
        return _enqueue_remote("animacion", "animacion",
                               {"source_path": str(source_path), "driving_path": str(driving_path)},
                               payload.project_id)

    def runner(job_id: int, report):
        result = animation.liveportrait_animate(job_id, source_path, driving_path, report)
        if payload.project_id:
            database.update_project(payload.project_id, {"animated_path": str(result), "status": "animated"})
            database.log_generation(payload.project_id, "animacion", result)
        return result

    job_id = jobs.submit_job("animacion", payload.project_id, runner)
    return {"job_id": job_id, "status": "queued"}


# ---------- lip sync (job real) ----------

@router.post("/lipsync/run")
def lipsync_run(payload: LipSyncIn):
    check = animation.wav2lip_check()
    if not check["available"]:
        raise HTTPException(409, check["message"])
    face = _resolve_asset(payload.face_path)
    audio = _resolve_asset(payload.audio_path)
    if settings.CLOUD_INFERENCE_MODE == "kaggle":
        return _enqueue_remote("lipsync", "lipsync",
                               {"face_path": str(face), "audio_path": str(audio)},
                               payload.project_id)

    def runner(job_id: int, report):
        result = animation.wav2lip_sync(job_id, face, audio, report)
        if payload.project_id:
            database.update_project(payload.project_id, {"lipsync_path": str(result), "status": "lipsync"})
            database.log_generation(payload.project_id, "lipsync", result)
        return result

    job_id = jobs.submit_job("lipsync", payload.project_id, runner)
    return {"job_id": job_id, "status": "queued"}


# ---------- editor (job) ----------

@router.post("/editor/render")
def editor_render(payload: EditorIn):
    visual = _resolve_asset(payload.visual_path)
    audio = _resolve_asset(payload.audio_path) if payload.audio_path else None
    music = _resolve_asset(payload.music_path) if payload.music_path else None
    subs = _resolve_asset(payload.subtitles_path) if payload.subtitles_path else None
    if settings.CLOUD_INFERENCE_MODE == "kaggle":
        return _enqueue_remote("editor", "editor", {
            "visual_path": str(visual),
            "audio_path": str(audio) if audio else "",
            "title": payload.title or "",
        }, payload.project_id)

    def runner(job_id: int, report):
        result = video_editor.render_announcement(
            job_id, visual, audio, music, subs, payload.title,
            payload.voice_volume, payload.music_volume, payload.zoom,
            payload.resolution, payload.trim_start, payload.trim_end, report,
        )
        if payload.project_id:
            database.update_project(payload.project_id, {"final_path": str(result), "status": "done"})
            database.log_generation(payload.project_id, "video_final", result)
        return result

    job_id = jobs.submit_job("editor", payload.project_id, runner)
    return {"job_id": job_id, "status": "queued"}


@router.post("/editor/preview")
def editor_preview(payload: EditorPreviewIn):
    image = _resolve_asset(payload.image_path)

    def runner(job_id: int, report):
        return video_editor.render_preview_from_image(job_id, image, 6.0, report)

    job_id = jobs.submit_job("preview", payload.project_id, runner)
    return {"job_id": job_id, "status": "queued"}


@router.post("/subtitles/build")
def subtitles_build(payload: SubtitlesIn):
    _resolve_asset(payload.audio_path)
    path = subtitles.build_subtitles(payload.text, payload.audio_path, settings.PROJECTS_DIR / "subs")
    return {"path": str(path), "url": f"/api/assets?path={path.as_posix()}"}


# ---------- flujo principal GENERAR MI ANUNCIO ----------

@router.post("/flow/generate")
def flow_generate(payload: FlowIn):
    project = database.get_project(payload.project_id)
    if not project:
        raise HTTPException(404, "Proyecto no encontrado.")
    photo_str = payload.influencer_photo or ""
    if project.get("influencer_id") and not photo_str:
        inf = database.get_influencer(project["influencer_id"])
        photo_str = inf["photo_path"] if inf else ""
    if not photo_str:
        raise HTTPException(400, "Selecciona un influencer (o indica su foto).")
    script_text = (payload.script or project.get("script") or "").strip()
    audio_override = payload.audio_path or ""
    if not script_text and not audio_override:
        raise HTTPException(400, "El proyecto no tiene guion ni audio.")
    if not (payload.driving_video):
        raise HTTPException(400, "Sube el vídeo de referencia de movimiento para LivePortrait.")

    pid = payload.project_id
    photo_path = _resolve_asset(photo_str)
    driving_path = _resolve_asset(payload.driving_video)
    music_path = _resolve_asset(payload.music_path) if payload.music_path else None
    audio_path = _resolve_asset(audio_override) if audio_override else None
    # Persistir audio/guion subidos para que el runner local (modo CPU) los reutilice.
    if audio_path is not None:
        database.update_project(pid, {"audio_path": str(audio_path)})
    if script_text:
        database.update_project(pid, {"script": script_text})

    if settings.CLOUD_INFERENCE_MODE == "kaggle":
        current = database.get_project(pid) or {}
        return _enqueue_remote("flujo", "flujo", {
            "photo_path": str(photo_path),
            "driving_path": str(driving_path),
            "audio_path": str(audio_path) if audio_path else (current.get("audio_path") or ""),
            "script": script_text,
            "music_path": str(music_path) if music_path else "",
            "title": payload.title or (current.get("name") or ""),
            "use_lipsync": bool(payload.use_lipsync),
            "resolution": payload.resolution or "720x1280",
        }, payload.project_id)

    def runner(job_id: int, report):
        # Etapas reutilizables: si audio_path ya existe, se reutiliza (reintento sin repetir).
        current = database.get_project(pid) or {}
        project_id = pid

        # 1. Audio Fish o local SAPI (fallback automático; reutiliza si ya existe)
        audio_path: Path
        if current.get("audio_path") and Path(current["audio_path"]).exists():
            report("Audio reutilizado (ya generado).", 15.0)
            audio_path = Path(current["audio_path"])
        else:
            report("Generando audio (Fish con fallback local)…", 5.0)
            audio_path = _generate_audio_auto(
                current.get("script", ""), current.get("voice_id", ""),
                payload.audio_provider, None,
            )
            database.update_project(project_id, {"audio_path": str(audio_path), "status": "audio"})
            database.log_generation(project_id, "audio", audio_path)
            report("Audio listo ✔", 25.0)

        # 2. Animación LivePortrait (reutiliza si ya existe)
        animated_path: Path
        if current.get("animated_path") and Path(current["animated_path"]).exists():
            report("Animación reutilizada (ya generada).", 55.0)
            animated_path = Path(current["animated_path"])
        else:
            report("Animando con LivePortrait (CPU)…", 30.0)
            animated_path = animation.liveportrait_animate(
                job_id, photo_path, driving_path,
                lambda s, p=None: report(s, (30.0 + (p or 0.0) / 100 * 25.0) if p is not None else None),
            )
            database.update_project(project_id, {"animated_path": str(animated_path), "status": "animated"})
            database.log_generation(project_id, "animacion", animated_path)
            report("Animación lista ✔", 60.0)
            # Perfil LOW_RAM_12GB: liberar memoria y temporales antes de Wav2Lip.
            import gc as _gc
            _gc.collect()
            maintenance.cleanup_temp_safe()
            snap = memory.memory_snapshot()
            report(f"Memoria liberada tras animación: {snap['free_gb']} GB libres.", 61.0)

        # 3. Lip sync opcional (solo si el usuario lo pide Y hay pesos; nunca simulado)
        visual = animated_path
        if payload.use_lipsync:
            check = animation.wav2lip_check()
            if check["available"]:
                report("Sincronizando labios con Wav2Lip…", 62.0)
                visual = animation.wav2lip_sync(job_id, animated_path, audio_path, report)
                database.update_project(project_id, {"lipsync_path": str(visual)})
                database.log_generation(project_id, "lipsync", visual)
                report("Lip sync listo ✔", 70.0)
            else:
                report("Lip sync omitido: faltan pesos de Wav2Lip (flujo continúa).", 70.0)

        import gc as _gc
        _gc.collect()
        maintenance.cleanup_temp_safe()
        snap = memory.memory_snapshot()
        report(f"Memoria liberada tras lip sync: {snap['free_gb']} GB libres.", 72.0)

        # 4. Subtítulos
        report("Generando subtítulos…", 75.0)
        subs_path = subtitles.build_subtitles(
            current.get("script", ""), audio_path, settings.PROJECTS_DIR / "subs"
        )
        # 5. Montaje final
        report("Montando anuncio final…", 80.0)
        final = video_editor.render_announcement(
            job_id, visual, audio_path, music_path, subs_path,
            payload.title or current.get("name", ""),
            resolution=payload.resolution,
            report=report,
        )
        database.update_project(project_id, {"final_path": str(final), "status": "done"})
        database.log_generation(project_id, "video_final", final)
        return final

    job_id = jobs.submit_job("flujo_completo", payload.project_id, runner)
    return {"job_id": job_id, "status": "queued"}


# ---------- trabajos ----------

@router.get("/jobs")
def list_jobs(limit: int = 50):
    return database.list_jobs(limit)


@router.get("/jobs/{job_id}")
def get_job(job_id: int):
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(404, "Trabajo no encontrado.")
    ext_ref = job.get("ext_ref")
    if ext_ref:
        ext = remote_worker.get_ext(ext_ref)
        if ext:
            return {
                "id": job["id"], "kind": job["kind"], "project_id": job.get("project_id"),
                "status": ext["status"], "step": ext.get("step", ""), "progress": ext.get("progress"),
                "log": job.get("log", ""), "error": ext.get("error", ""),
                "result_path": ext.get("result_path", ""), "ext_id": ext_ref,
            }
    return job


# ---------- worker remoto (Kaggle GPU) ----------

@router.get("/cloud/worker/next")
def worker_next(request: Request, gpu: str = "", v: str = ""):
    if not _worker_key_ok(request):
        raise HTTPException(401, "Worker key inválida.")
    remote_worker.touch_worker(gpu=gpu, version=v)
    # Recupera trabajos de una sesión de Kaggle que murió a mitad.
    remote_worker.requeue_stale()
    ext = remote_worker.claim_next("kaggle-gpu")
    if not ext:
        return {"status": "idle"}
    payload = ext["payload"]
    base = str(request.base_url).rstrip("/")
    return {
        "id": ext["id"], "kind": ext["kind"], "payload": {**payload, "_download_base": base},
    }


@router.post("/cloud/worker/upload")
async def worker_upload(request: Request):
    if not _worker_key_ok(request):
        raise HTTPException(401, "Worker key inválida.")
    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "filename"):
        raise HTTPException(400, "Falta el archivo.")
    if len(file.file.read()) > settings.MAX_UPLOAD_MB * 1024 * 1024 * 2:
        raise HTTPException(413, "Archivo demasiado grande.")
    filename = Path(file.filename or "result.mp4").name
    target = media.unique_path(settings.EXPORTS_DIR, filename)
    file.file.seek(0)
    target.write_bytes(file.file.read())
    # Espejo inmediato: el MP4 debe sobrevivir a un reinicio de Render.
    remote = cloud_store.mirror(target)
    return {"path": str(target), "remote": remote}


@router.post("/cloud/worker/result")
def worker_result(payload: dict, request: Request):
    if not _worker_key_ok(request):
        raise HTTPException(401, "Worker key inválida.")
    ext_id = payload.get("id", "")
    status = payload.get("status", "completed")
    remote_worker.finish_ext(ext_id, status, payload.get("step", "Completado"),
                             payload.get("result_path", ""), payload.get("error", ""))
    # Propaga al proyecto para el historial
    ext = remote_worker.get_ext(ext_id)
    if ext and ext.get("project_id") and status == "completed" and ext.get("result_path"):
        kind = ext["kind"]
        field = {"animacion": "animated_path", "lipsync": "lipsync_path",
                 "editor": "final_path", "flujo": "final_path"}.get(kind)
        if field:
            database.update_project(ext["project_id"], {field: ext["result_path"], "status": "done"})
            database.log_generation(ext["project_id"], kind, ext["result_path"])
    return {"ok": True}


@router.post("/cloud/worker/progress")
def worker_progress(payload: dict, request: Request):
    if not _worker_key_ok(request):
        raise HTTPException(401, "Worker key inválida.")
    remote_worker.progress_ext(payload.get("id", ""), payload.get("step", ""), payload.get("progress"))
    return {"ok": True}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: int):
    ok = jobs.request_cancel(job_id)
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(404, "Trabajo no encontrado.")
    if not ok:
        raise HTTPException(409, "El trabajo ya terminó o no está en ejecución.")
    database.update_job(job_id, status="cancelled", step="Cancelado por el usuario")
    return {"ok": True}


# ---------- assets ----------

@router.get("/assets")
def get_asset(path: str):
    file_path = _resolve_asset(path)
    return FileResponse(str(file_path))


@router.get("/cloud/files/{file_path:path}")
def cloud_file(file_path: str, download: bool = False):
    """Sirve un artefacto (foto/audio/MP4) al dashboard público.

    Solo dentro de assets/projects/exports (ver _resolve_asset). Si Render se
    reinició y el archivo ya no está en disco, redirige a la copia en HF.
    """
    file_path = file_path.replace("\\", "/") if ":" not in file_path else file_path
    try:
        file = _resolve_asset(file_path)
    except HTTPException as exc:
        if exc.status_code == 404:
            remote = cloud_store.remote_url(file_path, download=download)
            if remote:
                return RedirectResponse(remote, status_code=307)
        raise
    if download:
        return FileResponse(str(file), filename=file.name, content_disposition_type="attachment")
    return FileResponse(str(file))


@router.get("/cloud/status")
def cloud_status():
    """Estado de la cola remota para el dashboard (sin exponer secretos)."""
    from app.core import database as _db

    conn = _db.get_conn()
    try:
        rows = conn.execute("SELECT status, COUNT(*) c FROM ext_jobs GROUP BY status").fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    counts = {r["status"]: r["c"] for r in rows}
    return {
        "mode": settings.CLOUD_INFERENCE_MODE,
        "worker_configured": bool(settings.CLOUD_WORKER_KEY) or bool(_worker_pubkey()),
        "worker": remote_worker.worker_last_seen(),
        "queue": counts,
    }


@router.get("/cloud/worker/files")
def worker_file(path: str, request: Request):
    if not _worker_key_ok(request):
        raise HTTPException(401, "Worker key inválida.")
    file_path = _resolve_asset(path)
    return FileResponse(str(file_path))
