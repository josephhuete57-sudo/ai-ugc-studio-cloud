"""Comprueba que el build del kernel inyecta backend y clave privada (sin imprimirla)."""
from pathlib import Path

base = Path(__file__).resolve().parents[1] / "cloud" / "worker" / "kaggle" / "_build"
meta = (base / "kernel-metadata.json").read_text(encoding="utf-8")
code = (base / "kernel.py").read_text(encoding="utf-8")
print(meta)
print("PRIV_INYECTADA", 'WORKER_PRIV_HEX", "' in code)
print("BACKEND_INYECTADO", "ai-ugc-studio-backend.onrender.com" in code)
print("LONGITUD_KERNEL", len(code))
print("SIN_MARCADOR_CAMBIAR", "CAMBIAR" not in code)
