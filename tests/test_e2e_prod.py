"""Prueba E2E REAL: crea un anuncio desde el backend público y espera el MP4.

No procesa vídeo en local: solo llama a la API de Render, que encola el trabajo
para el worker GPU de Kaggle, y descarga el resultado público.

Uso:
    .venv\\Scripts\\python.exe tests\\test_e2e_prod.py [segundos_max]
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

B = os.environ.get("CLOUD_B", "https://ai-ugc-studio-backend.onrender.com").rstrip("/")
ROOT = Path(r"C:\AI_UGC_STUDIO")
PHOTO = ROOT / "assets" / "influencers" / "s0.jpg"
DRIVING = ROOT / "projects" / "driving_short15.mp4"
SCRIPT = ("Descubre el nuevo serum de vitamina C. Textura ligera, resultados "
          "visibles en dos semanas. Tu piel merece este brillo.")
OUT = ROOT / "exports" / "e2e_kaggle.mp4"


def _wait_awake(limit: int = 120) -> None:
    t0 = time.time()
    while time.time() - t0 < limit:
        try:
            if requests.get(f"{B}/api/health", timeout=20).ok:
                return
        except Exception:
            pass
        time.sleep(5)
    raise SystemExit("El backend no despertó a tiempo.")


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 900
    _wait_awake()

    with PHOTO.open("rb") as fh:
        r = requests.post(f"{B}/api/influencers/upload", files={"photo": (PHOTO.name, fh)}, timeout=300)
    r.raise_for_status()
    photo_path = r.json()["path"]
    print("PHOTO", photo_path)

    inf = requests.post(f"{B}/api/influencers",
                        json={"name": "E2E Kaggle", "photo_path": photo_path}, timeout=120).json()
    print("INFLUENCER", inf["id"])

    with DRIVING.open("rb") as fh:
        r = requests.post(f"{B}/api/upload/video", files={"video": (DRIVING.name, fh)}, timeout=300)
    r.raise_for_status()
    driving_path = r.json()["path"]
    print("DRIVING", driving_path)

    proj = requests.post(f"{B}/api/projects", json={
        "name": "E2E Kaggle GPU", "influencer_id": inf["id"],
        "product": "Serum vitamina C", "campaign": "e2e", "script": SCRIPT,
    }, timeout=120).json()
    pid = proj["id"]
    print("PROJECT", pid)

    r = requests.post(f"{B}/api/flow/generate", json={
        "project_id": pid, "influencer_photo": photo_path, "driving_video": driving_path,
        "use_lipsync": True, "title": "Serum vitamina C", "resolution": "720x1280",
        "script": SCRIPT,
    }, timeout=180)
    print("FLOW", r.status_code, r.text[:160])
    r.raise_for_status()
    ext_id = r.json().get("ext_id", "")
    print("JOB", r.json().get("job_id"), "EXT", ext_id)

    t0 = time.time()
    final = ""
    while time.time() - t0 < limit:
        time.sleep(20)
        p = requests.get(f"{B}/api/projects/{pid}", timeout=60).json()
        st = requests.get(f"{B}/api/cloud/status", timeout=60).json()
        w = st.get("worker", {})
        print(f"t={int(time.time()-t0)}s status={p.get('status')} final={bool(p.get('final_path'))} "
              f"worker={w.get('online')} gpu={w.get('gpu')!r} queue={st.get('queue')}", flush=True)
        if p.get("final_path"):
            final = p["final_path"]
            break
        if p.get("status") == "error":
            raise SystemExit(f"Trabajo fallido: {json.dumps(p)[:600]}")

    if not final:
        raise SystemExit("TIMEOUT sin MP4 final")

    name = Path(final).name
    url = f"{B}/api/cloud/files/{name}"
    r = requests.get(url, timeout=600)
    print("DOWNLOAD", r.status_code, r.headers.get("content-type"), len(r.content), url)
    r.raise_for_status()
    OUT.write_bytes(r.content)
    print("SAVED", OUT, OUT.stat().st_size)
    print("E2E_OK", pid, name, url)


if __name__ == "__main__":
    main()
