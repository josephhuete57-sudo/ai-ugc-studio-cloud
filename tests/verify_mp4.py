"""Verifica un MP4 entregado por el worker: descarga, ffprobe, HTTP 200 y SHA-256.

No procesa vídeo: solo descarga el resultado público de Render y lo audita.

Uso: .venv\\Scripts\\python.exe tests\\verify_mp4.py <project_id> [salida.mp4]
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import requests

B = "https://ai-ugc-studio-backend.onrender.com"
ROOT = Path(r"C:\AI_UGC_STUDIO")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "exports" / f"proyecto_{pid}.mp4"

    p = requests.get(f"{B}/api/projects/{pid}", timeout=120).json()
    final = p.get("final_path") or ""
    print("PROJECT", pid, "status=", p.get("status"), "final_path=", final)
    if not final:
        print("SIN_MP4")
        raise SystemExit(1)

    name = Path(final).name
    url = f"{B}/api/cloud/files/{name}"
    r1 = requests.get(url, timeout=900)
    print("HTTP", r1.status_code, r1.headers.get("content-type"), len(r1.content), url)
    r1.raise_for_status()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r1.content)

    # Segunda descarga: los bytes públicos deben ser idénticos (mismo objeto).
    r2 = requests.get(url, timeout=900)
    same = sha(r1.content) == sha(r2.content) == sha(out.read_bytes())
    print("SHA256", sha(r1.content))
    print("BYTES", len(r1.content), "== guardado", out.stat().st_size, "| identico_en_2_descargas", same)

    pr = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                         "-show_format", "-show_streams", str(out)],
                        capture_output=True, text=True, timeout=120)
    info = json.loads(pr.stdout or "{}")
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), {})
    fmt = info.get("format", {})
    print("VIDEO", v.get("codec_name"), f"{v.get('width')}x{v.get('height')}",
          "fps=", v.get("r_frame_rate"), "pix=", v.get("pix_fmt"))
    print("AUDIO", a.get("codec_name"), a.get("sample_rate"), "ch=", a.get("channels"))
    print("DURATION", fmt.get("duration"), "SIZE", fmt.get("size"))
    ok = (v.get("codec_name") == "h264" and a.get("codec_name") == "aac"
          and int(v.get("height") or 0) > int(v.get("width") or 0)
          and float(fmt.get("duration") or 0) > 0 and len(r1.content) > 10000 and same)
    print("VERIFY", "OK" if ok else "FAIL")
    raise SystemExit(0 if ok else 2)


if __name__ == "__main__":
    main()
