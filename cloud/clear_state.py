"""Borra el estado de prueba del repo HF (deja el repo vacío para producción).

Uso: .venv\\Scripts\\python.exe cloud\\clear_state.py
"""
from __future__ import annotations

from huggingface_hub import HfApi

REPO = "josjshid99/ai-ugc-studio-state"


def main() -> None:
    api = HfApi()
    files = [s.rfilename for s in api.model_info(REPO, files_metadata=True).siblings]
    for name in files:
        if name.startswith("media/") or name.startswith("state/"):
            api.delete_file(name, repo_id=REPO, repo_type="model")
            print("BORRADO", name)
    left = [s.rfilename for s in api.model_info(REPO, files_metadata=True).siblings]
    print("QUEDAN", left)
    print("STATE_CLEAR_OK")


if __name__ == "__main__":
    main()
