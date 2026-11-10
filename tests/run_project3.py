"""Lanza el flujo real sobre el proyecto 3 (el del trabajo ext_e4247e0142).

No procesa vídeo en local: sube el clip de referencia y encola en Render.
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

B = "https://ai-ugc-studio-backend.onrender.com"
ROOT = Path(r"C:\AI_UGC_STUDIO")
DRIVING = ROOT / "projects" / "driving_short15.mp4"
PHOTO = "/opt/render/project/src/assets/influencers/s0_7.jpg"
SCRIPT = ("Descubre el nuevo serum de vitamina C. Textura ligera, resultados "
          "visibles en dos semanas. Tu piel merece este brillo.")
PID = 3


def main() -> None:
    with DRIVING.open("rb") as fh:
        r = requests.post(f"{B}/api/upload/video",
                          files={"video": (DRIVING.name, fh)}, timeout=300)
    r.raise_for_status()
    driving = r.json()["path"]
    print("DRIVING", driving)

    r = requests.post(f"{B}/api/flow/generate", json={
        "project_id": PID, "influencer_photo": PHOTO, "driving_video": driving,
        "use_lipsync": True, "title": "Serum vitamina C", "resolution": "720x1280",
        "script": SCRIPT,
    }, timeout=180)
    print("FLOW", r.status_code, r.text[:200])
    r.raise_for_status()
    print("JOB", r.json().get("job_id"), "EXT", r.json().get("ext_id"))


if __name__ == "__main__":
    main()
