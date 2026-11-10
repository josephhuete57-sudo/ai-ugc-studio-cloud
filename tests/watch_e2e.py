"""Vigila el trabajo E2E pendiente y descarga el MP4 en cuanto esté listo.

Se ejecuta en segundo plano para que la entrega ocurra aunque la sesión de
OpenCode termine. No procesa vídeo: solo consulta la API pública y descarga.

Uso: .venv\\Scripts\\python.exe tests\\watch_e2e.py [horas]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

B = "https://ai-ugc-studio-backend.onrender.com"
PID = 1
OUT = Path(r"C:\AI_UGC_STUDIO\exports\e2e_kaggle.mp4")
LOG = Path(r"C:\AI_UGC_STUDIO\logs\watch_e2e.log")


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def main() -> None:
    global PID, OUT
    if len(sys.argv) > 2:
        PID = int(sys.argv[2])
        OUT = Path(rf"C:\AI_UGC_STUDIO\exports\proyecto_{PID}.mp4")
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0
    deadline = time.time() + hours * 3600
    log(f"WATCH start project={PID} hours={hours}")
    last = ""
    while time.time() < deadline:
        try:
            st = requests.get(f"{B}/api/cloud/status", timeout=60).json()
            p = requests.get(f"{B}/api/projects/{PID}", timeout=60).json()
            w = st.get("worker", {})
            cur = (f"worker_online={w.get('online')} gpu={w.get('gpu')!r} "
                   f"queue={st.get('queue')} status={p.get('status')} "
                   f"final={bool(p.get('final_path'))}")
            if cur != last:
                log(cur)
                last = cur
            if p.get("final_path"):
                name = Path(p["final_path"]).name
                url = f"{B}/api/cloud/files/{name}"
                r = requests.get(url, timeout=900)
                log(f"DOWNLOAD {r.status_code} {r.headers.get('content-type')} {len(r.content)} {url}")
                if r.ok and len(r.content) > 10000:
                    OUT.write_bytes(r.content)
                    log(f"E2E_DONE {url} bytes={OUT.stat().st_size} path={OUT}")
                else:
                    log("DOWNLOAD_FAIL")
                return
            if p.get("status") == "error":
                log(f"JOB_ERROR {str(p)[:400]}")
                return
        except Exception as exc:
            log(f"poll_error {type(exc).__name__}")
        time.sleep(60)
    log("WATCH timeout")


if __name__ == "__main__":
    main()
