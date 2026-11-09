"""Despliega el motor ZeroGPU (HF Space) con un solo token gratuito.

Uso (sin tarjeta, cuenta HF gratuita):
    $env:HF_TOKEN = "hf_tu_token..."
    .venv\\Scripts\\python.exe cloud\\deploy_hf.py

Crea/actualiza el repo del Space, sube app.py + requirements.txt + README.md,
y devuelve la URL pública. No printa el token nunca.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
INF = BASE / "cloud" / "inference"


def main() -> None:
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        try:
            from huggingface_hub import get_token

            token = (get_token() or "").strip()
        except Exception:
            pass
    if not token:
        sys.exit("Falta token HF. Haz login con `hf auth login` (flujo navegador).")
    from huggingface_hub import HfApi, whoami

    me = whoami(token=token)
    user = me.get("name") or me.get("email", "usuario")
    repo_id = f"{user}/ai-ugc-studio-motor"
    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="gradio", exist_ok=True)
    print("REPO", repo_id)
    for fname in ("app.py", "requirements.txt", "README.md"):
        src = INF / fname
        if src.exists():
            api.upload_file(
                path_or_fileobj=str(src),
                path_in_repo=fname,
                repo_id=repo_id,
                repo_type="space",
            )
            print("UPLOADED", fname)
    url = f"https://{user.lower().replace('_', '-')}-ai-ugc-studio-motor.hf.space"
    print("SPACE_URL", url)
    print("INFERENCE_URL para el backend:", url)


if __name__ == "__main__":
    main()
