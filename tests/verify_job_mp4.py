"""Verifica el MP4 de un job remoto (descarga 2x, SHA-256 y ffprobe)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import requests

B = "https://ai-ugc-studio-backend.onrender.com"
ROOT = Path(r"C:\AI_UGC_STUDIO")


def main() -> None:
    jid = sys.argv[1] if len(sys.argv) > 1 else "7"
    j = requests.get(f"{B}/api/jobs/{jid}", timeout=60).json()
    print("JOB", jid, json.dumps({k: j.get(k) for k in
                                  ("status", "step", "progress", "ext_id", "result_path", "error")},
                                 ensure_ascii=False))
    res = j.get("result_path") or ""
    if not res:
        print("SIN_MP4")
        raise SystemExit(1)
    name = res.rsplit("/", 1)[-1]
    url = f"{B}/api/cloud/files/{name}"
    r1 = requests.get(url, timeout=900)
    r2 = requests.get(url, timeout=900)
    print("HTTP", r1.status_code, r1.headers.get("content-type"), len(r1.content), url)
    r1.raise_for_status()
    h1, h2 = hashlib.sha256(r1.content).hexdigest(), hashlib.sha256(r2.content).hexdigest()
    out = ROOT / "exports" / f"job{jid}_{name}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r1.content)
    print("SHA256", h1)
    print("IGUAL_2_DESCARGAS", h1 == h2, "| BYTES", len(r1.content), "==", out.stat().st_size)

    pr = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                         "-show_format", "-show_streams", str(out)],
                        capture_output=True, text=True, timeout=120)
    info = json.loads(pr.stdout or "{}")
    for s in info.get("streams", []):
        print("STREAM", s.get("codec_type"), s.get("codec_name"),
              f"{s.get('width')}x{s.get('height')}", s.get("r_frame_rate"),
              s.get("pix_fmt"), "dur", s.get("duration"))
    print("DURATION", info.get("format", {}).get("duration"), "SIZE", info.get("format", {}).get("size"))
    print("SAVED", out)


if __name__ == "__main__":
    main()
