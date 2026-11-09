"""Cola de trabajos en segundo plano (1 worker CPU, estados, logs, cancelación)."""
from __future__ import annotations

import gc
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

from app.core import database, memory

_cancel_flags: dict[int, threading.Event] = {}
_flags_lock = threading.Lock()
_executor: Optional[ThreadPoolExecutor] = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        # CPU compartido: un solo trabajo pesado a la vez para no bloquear la UI ni saturar RAM.
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ugc-worker")
    return _executor


def is_cancelled(job_id: int) -> bool:
    with _flags_lock:
        ev = _cancel_flags.get(job_id)
    return bool(ev and ev.is_set())


def request_cancel(job_id: int) -> bool:
    with _flags_lock:
        ev = _cancel_flags.get(job_id)
        if ev is None:
            return False
        ev.set()
        return True


def submit_job(kind: str, project_id: Optional[int], runner: Callable[[int, Callable[[str, Optional[float]], None]], Path]) -> int:
    """runner(job_id, report) -> Path del artefacto final. report(step, progress)."""
    job_id = database.create_job(kind, project_id)
    with _flags_lock:
        _cancel_flags[job_id] = threading.Event()

    def _run() -> None:
        def report(step: str, progress: Optional[float] = None) -> None:
            database.update_job(job_id, step=step, progress=progress)
            database.append_job_log(job_id, f"{step} ({int(progress)}%)" if progress is not None else step)

        try:
            if is_cancelled(job_id):
                database.update_job(job_id, status="cancelled", step="Cancelado")
                return
            database.update_job(job_id, status="running", step="Iniciando…")
            database.append_job_log(job_id, f"Trabajo #{job_id} ({kind}) iniciado.")
            snap = memory.memory_snapshot()
            database.append_job_log(
                job_id,
                f"RAM al iniciar: {snap['free_gb']} GB libres / {snap['total_gb']} GB ({snap['load_percent']}% uso, perfil {snap['profile']}).",
            )
            memory.ensure_free_ram(report)
            result = runner(job_id, report)
            if is_cancelled(job_id):
                database.update_job(job_id, status="cancelled", step="Cancelado")
                database.append_job_log(job_id, "Cancelado por el usuario.")
                return
            database.update_job(
                job_id, status="done", step="Completado", progress=100.0, result_path=str(result or "")
            )
            database.append_job_log(job_id, f"OK: {result}")
        except Exception as exc:  # noqa: BLE001 - se registra como error del trabajo
            database.update_job(job_id, status="error", step="Error", error=str(exc)[:2000])
            database.append_job_log(job_id, f"ERROR: {exc}")
        finally:
            with _flags_lock:
                _cancel_flags.pop(job_id, None)
            gc.collect()  # liberar memoria tras cada tarea pesada

    _get_executor().submit(_run)
    return job_id
