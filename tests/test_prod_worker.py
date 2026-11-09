"""Verifica en PRODUCCIÓN (Render + HF) la cadena que usa el worker GPU.

No genera vídeo (eso exige la GPU de Kaggle): comprueba todo lo demás de la
cadena real, con firmas Ed25519 y archivos reales:

1. `/api/cloud/status` en producción (modo, worker, persistencia).
2. Rechazo sin firma y aceptación con firma Ed25519 válida.
3. Subida de un MP4 real por el endpoint del worker.
4. Descarga pública desde `/api/cloud/files/...` (inline y attachment).
5. Persistencia en HF: si `persistence` es true, el archivo debe sobrevivir
   como copia remota y la descarga debe seguir funcionando.

Uso:
    .venv\\Scripts\\python.exe tests\\test_prod_worker.py
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests
from cryptography.hazmat.primitives import serialization

B = os.environ.get("CLOUD_B", "https://ai-ugc-studio-backend.onrender.com").rstrip("/")
ROOT = Path(r"C:\AI_UGC_STUDIO")
PRIV = ROOT / "cloud" / "data" / "worker_ed25519.pem"
SAMPLE = ROOT / "exports" / "anuncio_1794251176.mp4"


def _sample() -> Path:
    if SAMPLE.exists() and SAMPLE.stat().st_size > 10000:
        return SAMPLE
    for p in sorted((ROOT / "exports").glob("*.mp4"), key=lambda x: x.stat().st_size, reverse=True):
        if p.stat().st_size > 10000:
            return p
    raise SystemExit("No hay ningún MP4 local de muestra para la prueba.")


def signed(key, path: str, ts: int | None = None) -> dict:
    ts = ts or int(time.time())
    sig = key.sign(f"{ts}:{path}".encode()).hex()
    return {"X-Worker-Timestamp": str(ts), "X-Worker-Signature": sig}


def main() -> None:
    key = serialization.load_pem_private_key(PRIV.read_bytes(), password=None)

    st = requests.get(f"{B}/api/cloud/status", timeout=90)
    st.raise_for_status()
    info = st.json()
    print("STATUS", st.status_code, info)
    assert info["mode"] == "kaggle"
    assert info["worker_configured"] is True
    assert "persistence" in info, "backend sin el campo persistence (despliegue viejo)"

    r = requests.get(f"{B}/api/cloud/worker/next", timeout=90)
    print("SIN_FIRMA", r.status_code)
    assert r.status_code == 401

    r = requests.get(f"{B}/api/cloud/worker/next",
                     headers=signed(key, "/api/cloud/worker/next"), timeout=90)
    print("FIRMA_OK", r.status_code, r.text[:90])
    assert r.ok

    sample = _sample()
    with sample.open("rb") as fh:
        r = requests.post(f"{B}/api/cloud/worker/upload",
                          headers=signed(key, "/api/cloud/worker/upload"),
                          files={"file": (sample.name, fh)}, timeout=600)
    print("UPLOAD", r.status_code, r.text[:160])
    r.raise_for_status()
    path = r.json()["path"]
    name = Path(path).name
    remote = r.json().get("remote", "")
    print("REMOTE", remote or "(sin espejo HF)")

    pub = requests.get(f"{B}/api/cloud/files/{name}", timeout=180)
    print("PUBLICO", pub.status_code, pub.headers.get("content-type"), len(pub.content))
    assert pub.status_code == 200
    assert pub.headers.get("content-type", "").startswith("video/mp4")
    assert len(pub.content) == sample.stat().st_size

    dl = requests.get(f"{B}/api/cloud/files/{name}?download=true", timeout=180)
    print("DESCARGA", dl.status_code, dl.headers.get("content-disposition"), len(dl.content))
    assert dl.status_code == 200
    assert "attachment" in (dl.headers.get("content-disposition") or "")

    if info.get("persistence"):
        assert remote, "persistencia activa pero el MP4 no se espejó"
        print("PERSISTENCIA_OK", remote)

    print("PROD_CHAIN_OK", f"{B}/api/cloud/files/{name}")


if __name__ == "__main__":
    main()
