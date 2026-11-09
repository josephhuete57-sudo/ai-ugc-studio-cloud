"""Verifica la persistencia en Hugging Face (estado + artefactos).

Requiere token HF local (hf auth login). Hace dos comprobaciones reales:

1. ``backup_once`` sube la base a ``state/studio.db`` y se puede descargar.
2. Con el backend en modo HF, un MP4 subido por el worker queda espejado en
   ``media/`` y se sirve por redirección aunque se borre del disco local.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

ROOT = Path(r"C:\AI_UGC_STUDIO")
REPO = "josjshid99/ai-ugc-studio-state"
PORT = 8004
B = f"http://127.0.0.1:{PORT}"


def _token() -> str:
    from huggingface_hub import get_token

    tok = get_token()
    if not tok:
        raise SystemExit("Sin token HF: ejecuta 'hf auth login'.")
    return tok


def _env(tok: str) -> dict:
    env = dict(os.environ)
    env.update({
        "CLOUD_INFERENCE_MODE": "kaggle",
        "CLOUD_WORKER_KEY": "",
        "HF_TOKEN": tok,
        "HF_REPO": REPO,
        "HF_REPO_TYPE": "model",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    return env


def step_backup(tok: str) -> None:
    code = (
        "from app.services import cloud_store\n"
        "print('ENABLED', cloud_store.enabled())\n"
        "print('BACKUP', cloud_store.backup_once(force=True))\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env=_env(tok),
                       capture_output=True, text=True, timeout=600)
    print("BACKUP_RUN", r.returncode, r.stdout.strip(), r.stderr.strip()[-300:])
    assert "ENABLED True" in r.stdout and "BACKUP True" in r.stdout, r.stdout + r.stderr

    from huggingface_hub import hf_hub_download

    got = hf_hub_download(REPO, "state/studio.db", token=tok)
    size = Path(got).stat().st_size
    conn = sqlite3.connect(got)
    try:
        n = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        cols = [r[1] for r in conn.execute("PRAGMA table_info(projects)").fetchall()]
    finally:
        conn.close()
    print("HF_DB", size, "bytes | proyectos", n, "| columnas", len(cols))
    assert size > 4096 and "final_path" in cols
    print("BACKUP_OK")


def step_media(tok: str) -> None:
    env = _env(tok)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(PORT)], cwd=str(ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                if requests.get(f"{B}/api/health", timeout=2).ok:
                    break
            except Exception:
                pass
            time.sleep(1)
        else:
            raise SystemExit("El backend no arrancó en 60 s.")

        st = requests.get(f"{B}/api/cloud/status", timeout=20).json()
        print("STATUS", st["mode"], "persistencia_hf=True")

        r = subprocess.run([sys.executable, str(ROOT / "tests" / "test_cloud_flow.py")],
                           cwd=str(ROOT), env={**env, "CLOUD_B": B},
                           capture_output=True, text=True, timeout=600)
        print(r.stdout.strip()[-1500:])
        assert "CLOUD_FLOW_OK" in r.stdout, r.stdout + r.stderr[-800:]

        import re

        m = re.search(r'UPLOAD 200 \{"path":"([^"]+)"', r.stdout)
        assert m, r.stdout[-800:]
        name = Path(m.group(1)).name
        print("UPLOADED_NAME", name)

        # El MP4 debe existir ya en HF (espejo del worker upload).
        from huggingface_hub import hf_hub_download

        got = hf_hub_download(REPO, f"media/{name}", token=tok)
        print("HF_MP4", Path(got).stat().st_size, "bytes")

        # Se borra el archivo local: el dashboard debe seguir sirviéndolo.
        local = ROOT / "exports" / name
        if local.exists():
            local.unlink()
        r = requests.get(f"{B}/api/cloud/files/{local.name}", timeout=60, allow_redirects=True)
        print("REDIRECT", r.status_code, r.headers.get("content-type"), len(r.content),
              "| final", r.url[:80])
        assert r.status_code == 200 and len(r.content) > 10000
        assert "huggingface.co" in r.url or "hf.co" in r.url, r.url
        print("MEDIA_OK")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except Exception:
            proc.kill()


def main() -> None:
    tok = _token()
    step_backup(tok)
    step_media(tok)
    print("HF_STORE_OK")


if __name__ == "__main__":
    main()
