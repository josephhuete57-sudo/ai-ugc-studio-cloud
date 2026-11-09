"""Motores de animación / lip sync: LivePortrait (real) y Wav2Lip (pendiente honesto)."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from app.core import jobs
from app.core.config import settings
from app.services.media import redact, unique_path

_REQUIRED_WEIGHTS = {
    "F": settings.LIVEPORTRAIT_WEIGHTS / "base_models" / "appearance_feature_extractor.pth",
    "M": settings.LIVEPORTRAIT_WEIGHTS / "base_models" / "motion_extractor.pth",
    "G": settings.LIVEPORTRAIT_WEIGHTS / "base_models" / "spade_generator.pth",
    "W": settings.LIVEPORTRAIT_WEIGHTS / "base_models" / "warping_module.pth",
    "S": settings.LIVEPORTRAIT_WEIGHTS / "retargeting_models" / "stitching_retargeting_module.pth",
    "landmark": settings.LIVEPORTRAIT_WEIGHTS / "landmark.onnx",
}


class LivePortraitError(RuntimeError):
    pass


def liveportrait_check() -> dict:
    ready = (
        settings.LIVEPORTRAIT_PYTHON.exists()
        and settings.LIVEPORTRAIT_INFERENCE.exists()
        and all(p.exists() and p.stat().st_size > 1000 for p in _REQUIRED_WEIGHTS.values())
    )
    missing = [k for k, p in _REQUIRED_WEIGHTS.items() if not (p.exists() and p.stat().st_size > 1000)]
    return {
        "name": "LivePortrait",
        "available": ready,
        "device": "CPU",
        "missing": missing,
        "message": "Motor listo (pesos oficiales cargados en CPU)." if ready
                   else f"Faltan pesos: {', '.join(missing) or 'entorno LivePortrait'}.",
    }


def liveportrait_animate(
    job_id: int,
    source: str | Path,
    driving: str | Path,
    report,
) -> Path:
    """Anima con LivePortrait en CPU invocando SU propio venv (torch ya probado ahí).

    No se importa LivePortrait en el proceso de la API: el .venv principal (3.12)
    no tiene torch; su .venv (3.10) sí. Se orquesta como subproceso sin shell.
    """
    source_p, driving_p = Path(source), Path(driving)
    if not source_p.exists():
        raise LivePortraitError(f"No existe la fotografía: {source_p.name}")
    if not driving_p.exists():
        raise LivePortraitError(f"No existe el vídeo de referencia: {driving_p.name}")
    if not settings.LIVEPORTRAIT_PYTHON.exists():
        raise LivePortraitError("No se encontró el intérprete de LivePortrait (.venv).")

    stamp = int(time.time())
    out_dir = unique_path(settings.EXPORTS_DIR / "liveportrait", f"anim_{stamp}")
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(settings.LIVEPORTRAIT_PYTHON),
        str(settings.LIVEPORTRAIT_INFERENCE),
        "-s", str(source_p),
        "-d", str(driving_p),
        "-o", str(out_dir),
        "--flag-force-cpu",
        "--no-flag-use-half-precision",
        "--source-max-dim", str(settings.LIVEPORTRAIT_SOURCE_MAX_DIM),
    ]
    report("Cargando LivePortrait en CPU…", None)
    # Salida completa a archivo para diagnóstico (tyro/tqdm escriben a stderr).
    log_path = out_dir / "liveportrait.log"
    log_fh = log_path.open("w", encoding="utf-8", errors="replace")
    # El emoji de progreso de rich (🚀) rompe con cp1252 en Windows: forzar UTF-8.
    # Perfil LOW_RAM_12GB: hilos limitados, batch mínimo, sin fp16 (CPU).
    env = dict(
        os.environ,
        PYTHONIOENCODING="utf-8",
        PYTHONUTF8="1",
        OMP_NUM_THREADS=str(settings.CPU_THREADS),
        MKL_NUM_THREADS=str(settings.CPU_THREADS),
        ORT_LOGGING_LEVEL="3",
    )
    proc = subprocess.Popen(
        cmd,
        cwd=str(settings.LIVEPORTRAIT_DIR),
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        env=env,
    )
    started = time.time()
    try:
        while True:
            if jobs.is_cancelled(job_id):
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                raise LivePortraitError("Animación cancelada por el usuario.")
            if time.time() - started > settings.LIVEPORTRAIT_TIMEOUT:
                proc.kill()
                raise LivePortraitError("Timeout de LivePortrait en CPU. Prueba con un vídeo más corto.")
            if proc.poll() is not None:
                break
            # Progreso honesto desde el log del motor (fases reales, sin % inventados).
            try:
                tail = log_path.read_bytes().decode("utf-8", "replace")
                if "animated video consists of" in tail:
                    report("Animando frames en CPU (puede tardar varios minutos)…", None)
                elif "Making motion templates" in tail:
                    report("Extrayendo movimiento de referencia…", None)
                elif "Load appearance_feature_extractor" in tail:
                    report("Cargando modelos LivePortrait en CPU…", None)
                else:
                    report("Procesando con LivePortrait en CPU…", None)
            except Exception:
                pass
            time.sleep(5)
        rc = proc.returncode
    except LivePortraitError:
        raise
    except Exception as exc:
        proc.kill()
        raise LivePortraitError(f"Fallo al ejecutar LivePortrait: {redact(str(exc))}") from exc
    finally:
        log_fh.close()

    if rc != 0:
        tail = ""
        try:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-1500:]
        except Exception:
            pass
        raise LivePortraitError(f"LivePortrait terminó con error (rc={rc}): {redact(tail)}")

    mp4s = sorted(out_dir.rglob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if not mp4s:
        raise LivePortraitError("LivePortrait no generó un MP4. Revisa los archivos de entrada.")
    result = mp4s[-1]
    final = unique_path(settings.EXPORTS_DIR, f"anim_{stamp}.mp4")
    result.replace(final)
    return final


# ---------------- Wav2Lip (real, con pesos convertidos) ----------------
# El checkpoint oficial wav2lip_gan.pth viene como TorchScript con tensores CUDA.
# Se convierte UNA vez a {"state_dict": ...} en formato legacy (wav2lip_gan_state.pth)
# para que el inference.py del repo lo cargue en CPU sin modificarlo.


def wav2lip_check() -> dict:
    state = settings.WAV2LIP_CHECKPOINTS / "wav2lip_gan_state.pth"
    sfd = settings.WAV2LIP_DIR / "face_detection" / "detection" / "sfd" / "s3fd.pth"
    has_weights = state.exists() and state.stat().st_size > 10_000_000 and sfd.exists() and sfd.stat().st_size > 1_000_000
    if has_weights:
        return {"name": "Wav2Lip", "available": True, "device": "CPU",
                "message": "Listo (pesos oficiales cargados y convertidos a CPU)."}
    if (settings.WAV2LIP_CHECKPOINTS / "wav2lip_gan.pth").exists():
        return {"name": "Wav2Lip", "available": False, "device": "CPU",
                "message": "Peso oficial presente pero sin convertir: ejecuta tests/convert_w2l.py."}
    return {
        "name": "Wav2Lip", "available": False, "device": "CPU",
        "message": "Pendiente: falta wav2lip_gan.pth en Wav2Lip\\checkpoints\\ (fuente oficial: Google Drive del README de Wav2Lip).",
    }


def wav2lip_sync(job_id: int, face_video: str | Path, audio: str | Path, report) -> Path:
    """Sincronización labial real con el inference.py del repo (su venv CPU)."""
    state = settings.WAV2LIP_CHECKPOINTS / "wav2lip_gan_state.pth"
    py = settings.WAV2LIP_DIR / ".venv" / "Scripts" / "python.exe"
    face_p, audio_p = Path(face_video), Path(audio)
    if not state.exists():
        raise RuntimeError(
            "Wav2Lip pendiente: falta el checkpoint convertido (wav2lip_gan_state.pth). "
            "Ver INFORME_FINAL.md para la conversión desde el peso oficial."
        )
    if not py.exists():
        raise RuntimeError("No se encontró el intérprete de Wav2Lip (.venv).")
    if not face_p.exists():
        raise RuntimeError(f"No existe el vídeo/imagen base: {face_p.name}")
    if not audio_p.exists():
        raise RuntimeError(f"No existe el audio: {audio_p.name}")

    stamp = int(time.time())
    out = unique_path(settings.EXPORTS_DIR, f"lipsync_{stamp}.mp4")
    cmd = [
        str(py), str(settings.WAV2LIP_DIR / "inference.py"),
        "--checkpoint_path", str(state),
        "--face", str(face_p),
        "--audio", str(audio_p),
        "--outfile", str(out),
        "--pads", "0", "10", "0", "0",
        "--wav2lip_batch_size", str(settings.WAV2LIP_BATCH),
        "--face_det_batch_size", str(settings.WAV2LIP_FACE_DET_BATCH),
        "--resize_factor", str(settings.WAV2LIP_RESIZE_FACTOR),
    ]
    log_path = settings.LOGS_DIR / f"wav2lip_{stamp}.log"
    settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_fh = log_path.open("w", encoding="utf-8", errors="replace")
    report("Cargando Wav2Lip en CPU…", None)
    # inference.py detecta CPU solo; PYTHONUTF8 evita el crash del emoji de tqdm en cp1252.
    # Perfil LOW_RAM_12GB: hilos limitados y batch mínimo.
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
               OMP_NUM_THREADS=str(settings.CPU_THREADS), MKL_NUM_THREADS=str(settings.CPU_THREADS))
    proc = subprocess.Popen(
        cmd, cwd=str(settings.WAV2LIP_DIR), stdout=log_fh, stderr=subprocess.STDOUT, env=env,
    )
    started = time.time()
    try:
        while True:
            if jobs.is_cancelled(job_id):
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                raise RuntimeError("Lip sync cancelado por el usuario.")
            if time.time() - started > 1800:
                proc.kill()
                raise RuntimeError("Timeout de Wav2Lip en CPU. Prueba con audio más corto.")
            if proc.poll() is not None:
                break
            time.sleep(3)
        rc = proc.returncode
    finally:
        log_fh.close()
    if rc != 0 or not out.exists() or out.stat().st_size < 1000:
        tail = ""
        try:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-1200:]
        except Exception:
            pass
        raise RuntimeError(f"Wav2Lip falló (rc={rc}): {redact(tail)}")
    return out
