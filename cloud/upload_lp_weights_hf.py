"""Sube a HF los pesos de LivePortrait/insightface que el worker necesita.

- landmark.onnx (114 MB)
- insightface buffalo_l: det_10g.onnx + 2d106det.onnx
Así el worker no depende de descargas lentas ni de Google Drive.
"""
from pathlib import Path

from huggingface_hub import HfApi

REPO = "josjshid99/ai-ugc-studio-weights"
LP = Path(r"C:\AI_UGC_STUDIO\LivePortrait\pretrained_weights")
FILES = [
    (LP / "liveportrait" / "landmark.onnx", "liveportrait/landmark.onnx"),
    (LP / "insightface" / "models" / "buffalo_l" / "det_10g.onnx",
     "insightface/models/buffalo_l/det_10g.onnx"),
    (LP / "insightface" / "models" / "buffalo_l" / "2d106det.onnx",
     "insightface/models/buffalo_l/2d106det.onnx"),
]


def main() -> None:
    api = HfApi()
    for local, remote in FILES:
        if not local.exists():
            print("FALTA", local)
            continue
        print(f"SUBIENDO {remote} ({local.stat().st_size} bytes)…", flush=True)
        api.upload_file(
            path_or_fileobj=str(local),
            path_in_repo=remote,
            repo_id=REPO,
            repo_type="model",
        )
        print("SUBIDO", remote, flush=True)
    for s in api.model_info(REPO, files_metadata=True).siblings:
        print("HF_FILE", s.rfilename, s.size)
    print("HF_EXTRA_OK")


if __name__ == "__main__":
    main()
