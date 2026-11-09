"""Despliega el frontend estático (Space gratuito) en tu cuenta HF.

Uso: hf auth login (navegador) y luego:
    .venv\\Scripts\\python.exe cloud\\deploy_frontend.py

Crea/actualiza <usuario>/ai-ugc-studio-web (sdk static) y devuelve la URL.
La URL del backend cloud se pega en la cabecera del dashboard (token incluido).
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
FRONT = BASE / "cloud" / "frontend_static"


def main() -> None:
    from huggingface_hub import HfApi, get_token

    token = get_token()
    if not token:
        sys.exit("Sin token HF. Ejecuta: hf auth login")
    api = HfApi(token=token)
    who = api.whoami()
    user = who.get("name") or who.get("email", "usuario")
    repo_id = f"{user}/ai-ugc-studio-web"
    api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="static", exist_ok=True)
    api.upload_folder(
        folder_path=str(FRONT),
        path_in_repo=".",
        repo_id=repo_id,
        repo_type="space",
    )
    url = f"https://{user.lower().replace('_', '-')}-ai-ugc-studio-web.hf.space"
    print("FRONTEND_URL", url)
    print("Pega la URL del backend cloud y el token en la cabecera del dashboard.")


if __name__ == "__main__":
    main()
