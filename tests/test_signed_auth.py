"""Verifica la autenticación firmada del worker (sin secreto en el backend)."""
import time
from pathlib import Path

import requests
from cryptography.hazmat.primitives import serialization

B = "http://127.0.0.1:8003"
PRIV = Path(r"C:\AI_UGC_STUDIO\cloud\data\worker_ed25519.pem")
key = serialization.load_pem_private_key(PRIV.read_bytes(), password=None)


def signed(path: str, ts: int | None = None) -> dict:
    ts = ts or int(time.time())
    sig = key.sign(f"{ts}:{path}".encode()).hex()
    return {"X-Worker-Timestamp": str(ts), "X-Worker-Signature": sig}


def main() -> None:
    r = requests.get(f"{B}/api/cloud/worker/next", timeout=20)
    print("SIN_FIRMA", r.status_code)
    assert r.status_code == 401

    r = requests.get(f"{B}/api/cloud/worker/next",
                     headers=signed("/api/cloud/worker/next"), timeout=20)
    print("FIRMA_OK", r.status_code, r.text[:80])
    assert r.ok

    r = requests.get(f"{B}/api/cloud/worker/next",
                     headers=signed("/api/cloud/worker/next", int(time.time()) - 5000), timeout=20)
    print("FIRMA_CADUCADA", r.status_code)
    assert r.status_code == 401

    h = signed("/api/cloud/worker/next")
    h["X-Worker-Signature"] = "00" * 64
    r = requests.get(f"{B}/api/cloud/worker/next", headers=h, timeout=20)
    print("FIRMA_FALSA", r.status_code)
    assert r.status_code == 401

    print("SIGNED_AUTH_OK")


if __name__ == "__main__":
    main()
