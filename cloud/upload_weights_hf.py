"""Sube los pesos de Wav2Lip (ya convertidos) y s3fd a un repo HF público.

Los pesos son modelos públicos: no contienen secretos. Alojarlos en HF evita
la descarga frágil de Google Drive dentro del worker de Kaggle.
"""
from pathlib import Path

from huggingface_hub import HfApi, create_repo

REPO = "josjshid99/ai-ugc-studio-weights"
BASE = Path(r"C:\AI_UGC_STUDIO")
FILES = [
    (BASE / "Wav2Lip" / "checkpoints" / "wav2lip_gan_state.pth", "wav2lip_gan_state.pth"),
    (BASE / "Wav2Lip" / "face_detection" / "detection" / "sfd" / "s3fd.pth", "s3fd.pth"),
]


def main() -> None:
    api = HfApi()
    create_repo(REPO, repo_type="model", exist_ok=True, private=False)
    print("REPO_OK", REPO)
    for local, remote in FILES:
        if not local.exists():
            print("FALTA", local)
            continue
        print(f"SUBiendo {remote} ({local.stat().st_size} bytes)…")
        api.upload_file(
            path_or_fileobj=str(local),
            path_in_repo=remote,
            repo_id=REPO,
            repo_type="model",
        )
        print("SUBIDO", remote)
    info = api.model_info(REPO, files_metadata=True)
    for s in info.siblings:
        print("HF_FILE", s.rfilename, s.size)
    print("HF_UPLOAD_OK")


if __name__ == "__main__":
    main()
