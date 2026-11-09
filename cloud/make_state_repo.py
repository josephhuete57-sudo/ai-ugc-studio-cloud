"""Crea el repo HF donde el backend guarda estado y artefactos (si se usa).

Repo público: guarda ``state/studio.db`` (metadatos de proyectos, sin
secretos) y ``media/`` (fotos, audios y MP4 generados) para que sobrevivan a
los reinicios de Render free. No imprime el token.
"""
from __future__ import annotations

from huggingface_hub import HfApi, create_repo, get_token

REPO = "josjshid99/ai-ugc-studio-state"


def main() -> None:
    token = get_token()
    if not token:
        raise SystemExit("Sin token HF: ejecuta 'hf auth login'.")
    create_repo(REPO, repo_type="model", exist_ok=True, private=False, token=token)
    api = HfApi(token=token)
    who = api.whoami()
    print("REPO_OK", REPO, "| usuario", who.get("name"))
    print("CONFIG_RENDER HF_REPO=" + REPO)
    print("CONFIG_RENDER HF_REPO_TYPE=model")


if __name__ == "__main__":
    main()
