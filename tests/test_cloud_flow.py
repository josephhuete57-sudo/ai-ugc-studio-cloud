"""Prueba cloud del flujo rápido (subida foto+audio -> cola -> resultado -> descarga).

Se ejecuta contra un backend local en modo kaggle (simula Render). Sin GPU:
el "worker" sube un MP4 ya existente para validar todo el circuito HTTP.
Usa la MISMA autenticación firmada Ed25519 que el worker real de Kaggle.
"""
import time
from pathlib import Path

import requests
from cryptography.hazmat.primitives import serialization

B = "http://127.0.0.1:8003"
ROOT = r"C:\AI_UGC_STUDIO"
_KEY = serialization.load_pem_private_key(
    Path(ROOT, "cloud", "data", "worker_ed25519.pem").read_bytes(), password=None)


def wk(path: str) -> dict:
    ts = str(int(time.time()))
    return {
        "X-Worker-Timestamp": ts,
        "X-Worker-Signature": _KEY.sign(f"{ts}:{path}".encode()).hex(),
    }


def drain():
    while True:
        d = requests.get(f"{B}/api/cloud/worker/next",
                         headers=wk("/api/cloud/worker/next"), timeout=20).json()
        if not d.get("id"):
            return
        requests.post(f"{B}/api/cloud/worker/result",
                      headers=wk("/api/cloud/worker/result"),
                      json={"id": d["id"], "status": "failed", "error": "drain"}, timeout=20)


def main() -> None:
    drain()

    # CORS para el dashboard público
    r = requests.options(f"{B}/api/health", headers={
        "Origin": "https://josjshid99-ai-ugc-studio-web.static.hf.space",
        "Access-Control-Request-Method": "GET"}, timeout=20)
    assert r.ok, r.text
    allow = r.headers.get("access-control-allow-origin", "")
    print("CORS", r.status_code, allow)
    assert allow in ("*", "https://josjshid99-ai-ugc-studio-web.static.hf.space")

    # status de cola + latido del worker
    st = requests.get(f"{B}/api/cloud/status", timeout=20).json()
    print("STATUS", st)
    assert st["mode"] == "kaggle"
    assert "worker" in st and st["worker"]["online"] is True

    # subir foto
    with open(f"{ROOT}\\assets\\influencers\\s0.jpg", "rb") as fh:
        up = requests.post(f"{B}/api/influencers/upload", files={"photo": ("foto.jpg", fh)}, timeout=60).json()
    print("PHOTO", up["path"])

    # subir audio
    with open(f"{ROOT}\\assets\\audio\\prueba_tono.mp3", "rb") as fh:
        au = requests.post(f"{B}/api/upload/audio", files={"audio": ("voz.mp3", fh)}, timeout=60).json()
    print("AUDIO", au["path"])

    # proyecto
    proj = requests.post(f"{B}/api/projects", json={
        "name": "Prueba cloud", "script": "Hola, esto es una prueba real.", "status": "draft"}, timeout=20).json()
    print("PROJECT", proj["id"])

    # flujo
    r = requests.post(f"{B}/api/flow/generate", json={
        "project_id": proj["id"], "influencer_photo": up["path"],
        "driving_video": "projects/driving_short15.mp4",
        "audio_path": au["path"], "script": "Hola, esto es una prueba real.",
        "title": "Prueba", "use_lipsync": True, "resolution": "720x1280"}, timeout=30)
    print("FLOW", r.status_code, r.text[:200])
    assert r.ok, r.text
    job_id = r.json()["job_id"]

    j = requests.get(f"{B}/api/jobs/{job_id}", timeout=20).json()
    print("JOB", j["status"], j.get("ext_id"))
    assert j["status"] == "pending"

    # worker reclama (firma Ed25519, como el kernel real)
    ext = requests.get(f"{B}/api/cloud/worker/next",
                       headers=wk("/api/cloud/worker/next"),
                       params={"gpu": "TEST-GPU", "v": "test"}, timeout=30).json()
    print("CLAIM", ext.get("id"), ext.get("kind"))
    assert ext.get("id"), ext
    assert ext["kind"] == "flujo"
    assert ext["payload"]["audio_path"] == au["path"], ext["payload"]
    assert ext["payload"]["script"] == "Hola, esto es una prueba real."

    st = requests.get(f"{B}/api/cloud/status", timeout=20).json()
    print("WORKER", st["worker"])
    assert st["worker"]["online"] is True and st["worker"]["gpu"] == "TEST-GPU"

    # descarga de input con firma
    r = requests.get(f"{B}/api/cloud/worker/files",
                     headers=wk("/api/cloud/worker/files"),
                     params={"path": ext["payload"]["photo_path"]}, timeout=30)
    print("DL_INPUT", r.status_code, len(r.content))
    assert r.ok and len(r.content) > 1000

    # sube resultado (MP4 real ya generado localmente en pruebas anteriores)
    with open(f"{ROOT}\\exports\\anuncio_1794251176.mp4", "rb") as fh:
        r = requests.post(f"{B}/api/cloud/worker/upload",
                          headers=wk("/api/cloud/worker/upload"),
                          files={"file": ("anuncio.mp4", fh)}, timeout=120)
    print("UPLOAD", r.status_code, r.text[:120])
    assert r.ok
    result = r.json()["path"]

    r = requests.post(f"{B}/api/cloud/worker/result",
                      headers=wk("/api/cloud/worker/result"),
                      json={"id": ext["id"], "status": "completed", "result_path": result}, timeout=20)
    print("RESULT", r.status_code)
    assert r.ok

    j = requests.get(f"{B}/api/jobs/{job_id}", timeout=20).json()
    print("JOB_FINAL", j["status"], j["result_path"])
    assert j["status"] == "completed" and j["result_path"] == result

    p = requests.get(f"{B}/api/projects/{proj['id']}", timeout=20).json()
    print("PROJECT_FINAL", p["status"], p["final_path"])
    assert p["final_path"] == result

    # descarga pública desde el dashboard (misma ruta que assetUrl)
    r = requests.get(f"{B}/api/cloud/files/{result}", timeout=60)
    print("PUBLIC_FILE", r.status_code, len(r.content), r.headers.get("content-type"))
    assert r.ok and len(r.content) > 10000

    r = requests.get(f"{B}/api/cloud/files/{result}", params={"download": 1}, timeout=60)
    print("DOWNLOAD", r.status_code, r.headers.get("content-disposition"))
    assert "attachment" in (r.headers.get("content-disposition") or "")

    print("CLOUD_FLOW_OK")


if __name__ == "__main__":
    main()
