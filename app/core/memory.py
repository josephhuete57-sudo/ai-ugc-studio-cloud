"""Monitor de RAM y presión de memoria (Windows, sin dependencias extra).

Lee la memoria física con GlobalMemoryStatusEx y el consumo de procesos
hijos (LivePortrait / Wav2Lip) con el cmdline vía CIM. Cache de 5 s para
no castigar al sistema con polling frecuente.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import time
from typing import Any

from app.core.config import settings

_CACHE: dict[str, Any] = {"ts": 0.0, "data": {}}
_CPU_PREV: dict[str, int] = {"idle": 0, "kernel": 0, "user": 0}


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_ulonglong),
        ("WorkingSetSize", ctypes.c_ulonglong),
        ("QuotaPeakPagedPoolUsage", ctypes.c_ulonglong),
        ("QuotaPagedPoolUsage", ctypes.c_ulonglong),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_ulonglong),
        ("QuotaNonPagedPoolUsage", ctypes.c_ulonglong),
        ("PagefileUsage", ctypes.c_ulonglong),
        ("PeakPagefileUsage", ctypes.c_ulonglong),
    ]


def _gb(num_bytes: float) -> float:
    return round(num_bytes / (1024 ** 3), 2)


def _process_working_set_mb(pid: int) -> float:
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x0400, False, int(pid))  # PROCESS_QUERY_INFORMATION
        if not h:
            return 0.0
        try:
            pmc = _PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(pmc)
            if ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
                return round(pmc.WorkingSetSize / (1024 * 1024), 1)
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    except Exception:
        pass
    return 0.0


def _children_memory() -> dict[str, float]:
    """RAM de procesos python hijos (LivePortrait / Wav2Lip) por cmdline."""
    out = {"liveportrait_mb": 0.0, "wav2lip_mb": 0.0, "python_mb": 0.0}
    try:
        ps = (
            "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
            "ForEach-Object { \"$($_.ProcessId)|$([math]::Round($_.WorkingSetSize/1MB))|$($_.CommandLine)\" }"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=10,
        )
        for line in (r.stdout or "").splitlines():
            parts = line.strip().split("|", 2)
            if len(parts) < 3:
                continue
            pid, mb, cmd = parts
            try:
                mb_f = float(mb)
            except ValueError:
                continue
            low = cmd.lower()
            if "liveportrait" in low and "inference.py" in low:
                out["liveportrait_mb"] += mb_f
            elif "wav2lip" in low and "inference.py" in low:
                out["wav2lip_mb"] += mb_f
            elif int(pid) == os.getpid():
                out["python_mb"] = mb_f
    except Exception:
        pass
    if out["python_mb"] == 0.0:
        out["python_mb"] = _process_working_set_mb(os.getpid())
    return out


def _cpu_load() -> float | None:
    """Carga de CPU del sistema (delta entre lecturas; None la primera vez)."""
    try:
        idle, kernel, user = ctypes.c_ulonglong(), ctypes.c_ulonglong(), ctypes.c_ulonglong()
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        now = {"idle": idle.value, "kernel": kernel.value, "user": user.value}
        prev = dict(_CPU_PREV)
        _CPU_PREV.update(now)
        if not prev.get("idle"):
            return None
        idle_d = now["idle"] - prev["idle"]
        total_d = (now["kernel"] - prev["kernel"]) + (now["user"] - prev["user"])
        if total_d <= 0:
            return None
        return round(max(0.0, min(100.0, (1 - idle_d / total_d) * 100)), 1)
    except Exception:
        return None


def memory_snapshot() -> dict[str, Any]:
    now = time.time()
    if now - _CACHE["ts"] < 5.0 and _CACHE["data"]:
        return dict(_CACHE["data"])
    try:
        m = _MEMORYSTATUSEX()
        m.dwLength = ctypes.sizeof(m)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        total_gb = _gb(m.ullTotalPhys)
        free_gb = _gb(m.ullAvailPhys)
        used_gb = round(total_gb - free_gb, 2)
        load = int(m.dwMemoryLoad)
    except Exception:
        total_gb = free_gb = used_gb = 0.0
        load = 0
    min_free = float(getattr(settings, "MIN_FREE_RAM_GB", 2.5))
    if free_gb < min_free:
        level = "critica"
    elif free_gb < min_free + 1.5 or load > 70:
        level = "elevada"
    else:
        level = "normal"
    children = _children_memory()
    data = {
        "total_gb": total_gb,
        "used_gb": used_gb,
        "free_gb": free_gb,
        "load_percent": load,
        "level": level,
        "min_free_gb": min_free,
        "cpu_percent": _cpu_load(),
        "python_mb": children["python_mb"],
        "liveportrait_mb": children["liveportrait_mb"],
        "wav2lip_mb": children["wav2lip_mb"],
        "profile": getattr(settings, "PROFILE", "LOW_RAM_12GB"),
    }
    _CACHE["ts"] = now
    _CACHE["data"] = data
    return dict(data)


def ensure_free_ram(report=None, max_wait_s: int = 600) -> None:
    """Pausa si la RAM libre está por debajo del mínimo (con aviso, sin fallar).

    Espera a que se libere con reintentos; si expira, continúa con advertencia
    (nunca impone un límite artificial que provoque error de asignación).
    """
    def say(msg: str) -> None:
        if report:
            report(msg, None)

    snap = memory_snapshot()
    if snap["free_gb"] >= snap["min_free_gb"]:
        return
    say(f"RAM baja: {snap['free_gb']} GB libres (mínimo {snap['min_free_gb']} GB). Pausando trabajo pesado…")
    started = time.time()
    while time.time() - started < max_wait_s:
        time.sleep(10)
        snap = memory_snapshot()
        if snap["free_gb"] >= snap["min_free_gb"]:
            say(f"RAM liberada: {snap['free_gb']} GB libres. Reanudando…")
            return
    say(f"RAM sigue baja ({snap['free_gb']} GB libres) tras {max_wait_s}s. Continúo con advertencia (sin límite artificial).")
