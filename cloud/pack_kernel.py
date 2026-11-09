"""Empaqueta el worker Kaggle inyectando backend y la clave privada Ed25519.

Kaggle no inyecta kernel parameters como variables de entorno en script
kernels vía CLI, así que el despliegue genera en _build/ una copia con los
valores sustituidos. _build/ está gitignored: la clave privada nunca se
publica en GitHub (solo la pública, cloud/worker_public_key.txt).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization

BASE = Path(__file__).resolve().parents[1]
SRC = BASE / "cloud" / "worker" / "kaggle"
BUILD = SRC / "_build"
PRIV = BASE / "cloud" / "data" / "worker_ed25519.pem"


def main() -> None:
    backend = (sys.argv[1] if len(sys.argv) > 1
               else "https://ai-ugc-studio-backend.onrender.com").rstrip("/")
    if not PRIV.exists():
        raise SystemExit("Falta la clave privada (ejecuta cloud/make_worker_keys.py).")
    key = serialization.load_pem_private_key(PRIV.read_bytes(), password=None)
    priv_hex = key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    ).hex()

    if BUILD.exists():
        shutil.rmtree(BUILD)
    shutil.copytree(SRC, BUILD, ignore=shutil.ignore_patterns("_build", "__pycache__"))
    src = BUILD / "kernel.py"
    code = src.read_text(encoding="utf-8")
    before = code
    code = code.replace(
        'BACKEND = os.environ.get("BACKEND_URL", "").rstrip("/")',
        f'BACKEND = os.environ.get("BACKEND_URL", "{backend}").rstrip("/")',
    ).replace(
        'PRIV_HEX = os.environ.get("WORKER_PRIV_HEX", "")',
        f'PRIV_HEX = os.environ.get("WORKER_PRIV_HEX", "{priv_hex}")',
    )
    if code == before:
        raise SystemExit("No se pudo inyectar la configuración en kernel.py.")
    src.write_text(code, encoding="utf-8")
    meta = json.loads((BUILD / "kernel-metadata.json").read_text(encoding="utf-8"))
    meta["parameters"] = {"BACKEND_URL": backend, "MAX_RUNTIME_MIN": "55"}
    (BUILD / "kernel-metadata.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print("BUILD OK", BUILD, "| BACKEND", backend, "| firma", priv_hex[:8] + "…")


if __name__ == "__main__":
    main()
