"""Worker GPU (Kaggle) — AI UGC STUDIO FREE CLOUD.

Polls la cola del backend, ejecuta en GPU: LivePortrait, Wav2Lip, FFmpeg y TTS.
Sin cómputo local: este script corre en Kaggle con GPU T4 gratuita.
Params por metadata del kernel: BACKEND_URL, WORKER_KEY, HF_TOKEN(optional).
"""
from __future__ import annotations

import asyncio
import gc
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

BACKEND = os.environ.get("BACKEND_URL", "").rstrip("/")
WKEY = os.environ.get("WORKER_KEY", "")
PRIV_HEX = os.environ.get("WORKER_PRIV_HEX", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
MAX_RUNTIME_MIN = int(os.environ.get("MAX_RUNTIME_MIN", "55"))
WORK = Path("/kaggle/working") if Path("/kaggle/working").exists() else Path(tempfile.gettempdir()) / "ugc_work"
WORK.mkdir(parents=True, exist_ok=True)
CACHE = WORK / "cache"
CACHE.mkdir(parents=True, exist_ok=True)


def _log(msg: str) -> None:
    print(f"[worker {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _pip(*pkgs: str) -> None:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *pkgs],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _ensure_deps() -> None:
    missing = []
    for mod, pkg in [("onnxruntime", "onnxruntime"), ("cv2", "opencv-python-headless"),
                     ("huggingface_hub", "huggingface_hub"), ("requests", "requests"),
                     ("edge_tts", "edge-tts"), ("scipy", "scipy"), ("librosa", "librosa==0.9.2"),
                     ("cryptography", "cryptography"), ("torch", "torch")]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        _log(f"Instalando deps: {missing}")
        _pip(*missing)


def _gpu() -> str:
    try:
        import torch

        return torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
    except Exception:
        return "CPU(desconocida)"


def _auth_headers(path: str) -> dict:
    """Firma Ed25519 (privada) o clave compartida; el backend acepta cualquiera."""
    headers: dict[str, str] = {}
    if PRIV_HEX:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        ts = str(int(time.time()))
        msg = f"{ts}:{path.split('?')[0]}".encode()
        sig = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(PRIV_HEX)).sign(msg).hex()
        headers["X-Worker-Timestamp"] = ts
        headers["X-Worker-Signature"] = sig
    if WKEY:
        headers["X-Worker-Key"] = WKEY
    return headers


def _http(method: str, path: str, **kw):
    import requests

    extra = kw.pop("headers", {}) or {}
    r = requests.request(method, BACKEND + path,
                         headers={**_auth_headers(path), **extra}, timeout=60, **kw)
    r.raise_for_status()
    return r


def _progress(job_id: str, step: str, pct: float | None = None) -> None:
    try:
        _http("POST", "/api/cloud/worker/progress",
              json={"id": job_id, "step": step, "progress": pct})
    except Exception:
        pass


def _result(job_id: str, status: str, result_path: str = "", error: str = "") -> None:
    _http("POST", "/api/cloud/worker/result",
          json={"id": job_id, "status": status, "result_path": result_path, "error": error})


def _download_artifact(container_path: str, dest: Path) -> Path:
    from urllib.parse import quote

    r = _http("GET", f"/api/cloud/worker/files?path={quote(container_path)}")
    dest.write_bytes(r.content)
    return dest


def _upload_result(local_path: Path) -> str:
    import requests

    with local_path.open("rb") as fh:
        r = requests.post(BACKEND + "/api/cloud/worker/upload",
                          headers=_auth_headers("/api/cloud/worker/upload"),
                          files={"file": (local_path.name, fh)}, timeout=600)
    r.raise_for_status()
    return r.json()["path"]


def _tts(text: str, out: Path, voice: str = "es-ES-ElviraNeural") -> Path:
    import edge_tts

    async def main():
        await edge_tts.Communicate(text, voice).save(str(out))

    asyncio.run(main())
    return out


def _clone(url: str, name: str) -> Path:
    dest = CACHE / name
    if not (dest / ".git").exists():
        subprocess.run(["git", "clone", "--depth", "1", url, str(dest)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dest


def _lp_weights() -> None:
    from huggingface_hub import hf_hub_download

    names = [
        "pretrained_weights/liveportrait/base_models/appearance_feature_extractor.pth",
        "pretrained_weights/liveportrait/base_models/motion_extractor.pth",
        "pretrained_weights/liveportrait/base_models/spade_generator.pth",
        "pretrained_weights/liveportrait/base_models/warping_module.pth",
        "pretrained_weights/liveportrait/retargeting_models/stitching_retargeting_module.pth",
    ]
    for fname in names:
        dest = CACHE / "LivePortrait" / fname
        if dest.exists() and dest.stat().st_size > 1000:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        got = hf_hub_download(repo_id="KwaiVGI/LivePortrait", filename=fname,
                              local_dir=str(CACHE / "LivePortrait"), token=HF_TOKEN or None)
        shutil.copy2(got, str(dest))


def _lp_animate(source: Path, driving: Path) -> Path:
    repo = _clone("https://github.com/KwaiVGI/LivePortrait.git", "LivePortrait")
    _lp_weights()
    out_dir = WORK / f"anim_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)
    on_gpu = _gpu() != "CPU"
    cmd = [sys.executable, str(repo / "inference.py"),
           "-s", str(source), "-d", str(driving), "-o", str(out_dir)]
    cmd += ["--flag-use-half-precision"] if on_gpu else [
        "--flag-force-cpu", "--no-flag-use-half-precision"]
    subprocess.run(cmd, cwd=str(repo), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800,
                   env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))
    mp4s = sorted(out_dir.rglob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if not mp4s:
        raise RuntimeError("LivePortrait sin MP4")
    return mp4s[-1]


def _w2l_weights() -> str:
    state = CACHE / "wav2lip_gan_state.pth"
    if state.exists() and state.stat().st_size > 10_000_000:
        return str(state)
    src = CACHE / "wav2lip_gan.pth"
    if not src.exists():
        import requests

        url = "https://drive.google.com/uc?export=download&id=15G3U08c8xsCkOqQxE38Z2XXDnPcOptNk"
        r = requests.get(url, timeout=60, stream=True, headers={"User-Agent": "Mozilla/5.0"})
        if r.headers.get("content-type", "").startswith("text/html"):
            import re

            fields = dict(re.findall(r'name="(id|export|confirm|uuid)" value="([^"]*)"', r.text))
            action = f"https://drive.usercontent.google.com/download?" + "&".join(
                f"{k}={v}" for k, v in fields.items())
            r = requests.get(action, timeout=900, stream=True)
        with src.open("wb") as fh:
            for ch in r.iter_content(1024 * 1024):
                fh.write(ch)
    # s3fd
    repo = _clone("https://github.com/Rudrabha/Wav2Lip.git", "Wav2Lip")
    sfd = repo / "face_detection" / "detection" / "sfd" / "s3fd.pth"
    if not sfd.exists():
        import requests

        sfd.write_bytes(requests.get(
            "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth",
            timeout=600, stream=True).content)
    import torch

    m = torch.jit.load(str(src), map_location="cpu")
    sd = m.state_dict()
    torch.save({"state_dict": sd}, str(state), _use_new_zipfile_serialization=False)
    return str(state)


def _lipsync(face: Path, audio: Path) -> Path:
    repo = _clone("https://github.com/Rudrabha/Wav2Lip.git", "Wav2Lip")
    ckpt = _w2l_weights()
    out = WORK / f"lipsync_{int(time.time())}.mp4"
    subprocess.run([sys.executable, str(repo / "inference.py"),
                    "--checkpoint_path", ckpt, "--face", str(face), "--audio", str(audio),
                    "--outfile", str(out), "--pads", "0", "10", "0", "0",
                    "--wav2lip_batch_size", "16", "--face_det_batch_size", "1"],
                   cwd=str(repo), check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=1800)
    return out


def _srt(text: str, audio: Path) -> Path:
    import json as _json

    out = WORK / f"subs_{int(time.time())}.srt"
    pr = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                         "-of", "json", str(audio)], capture_output=True, text=True, timeout=60)
    try:
        dur = float(_json.loads(pr.stdout)["format"]["duration"])
    except Exception:
        dur = 5.0
    parts = [p.strip() for p in text.replace("!", ".").replace("?", ".").split(".") if p.strip()]
    total = sum(len(p) for p in parts) or 1
    lines, cur = [], 0.0
    for i, p in enumerate(parts, 1):
        span = dur * (len(p) / total)
        lines.append(f"{i}\n00:00:{cur:06.3f} --> 00:00:{cur + span:06.3f}\n{p}\n")
        cur += span
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _font_file() -> str | None:
    import glob as _glob

    for pat in ("/usr/share/fonts/**/*.ttf", "/kaggle/lib/python*/site-packages/**/DejaVuSans.ttf"):
        hits = sorted(_glob.glob(pat, recursive=True))
        if hits:
            return hits[0]
    return None


def _edit(visual: Path, audio: Path, title: str, subs: Path | None, resolution: str) -> Path:
    W, _, H = (resolution or "720x1280").partition("x")
    W, H = int(W), int(H)
    out = WORK / f"anuncio_{int(time.time())}.mp4"
    subs_filter = ""
    font = _font_file()
    if subs and subs.exists() and font:
        entries = []
        for block in subs.read_text(encoding="utf-8", errors="ignore").strip().split("\n\n"):
            rows = [l.strip() for l in block.splitlines() if l.strip()]
            if len(rows) >= 3:
                a, b = rows[1].split("-->")
                entries.append((a.strip().replace(",", "."), b.strip().replace(",", "."), " ".join(rows[2:])))
        if entries:
            filters = []
            for i, (a, b, txt) in enumerate(entries):
                tf = WORK / f"sub{i}.txt"
                tf.write_text(txt, encoding="utf-8")
                filters.append(f"drawtext=fontfile='{font}':textfile='{tf.name}':fontsize=38:"
                               f"fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:"
                               f"y=h-text_h-110:enable='between(t,{a},{b})'")
            subs_filter = ",".join(filters) + ","
    title_filter = ""
    if title and font:
        tf = WORK / "title.txt"
        tf.write_text(title[:60], encoding="utf-8")
        title_filter = (f"drawtext=fontfile='{font}':textfile='{tf.name}':fontsize=44:"
                        f"fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:y=60,")
    dur_pr = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                             "-of", "json", str(audio)], capture_output=True, text=True, timeout=60)
    try:
        dur = float(__import__("json").loads(dur_pr.stdout)["format"]["duration"])
    except Exception:
        dur = 6.0
    ffmpeg = shutil.which("ffmpeg") or str(CACHE / "imageio-ffmpeg" / "ffmpeg")
    vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"{title_filter}{subs_filter}format=yuv420p[vout]")
    cmd = [ffmpeg, "-y", "-stream_loop", "-1", "-i", str(visual), "-i", str(audio),
           "-filter_complex", f"{vf};[1:a]volume=1.0[aout]",
           "-map", "[vout]", "-map", "[aout]",
           "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2", "-pix_fmt", "yuv420p",
           "-r", "24", "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
           "-t", f"{dur:.2f}", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
    return out


def process(job: dict) -> Path:
    kind, payload = job["kind"], job["payload"]
    base = payload.get("_download_base", BACKEND)
    jid = job["id"]
    tmp = WORK / f"job_{jid}"
    tmp.mkdir(parents=True, exist_ok=True)

    def dl(container_path: str, name: str) -> Path:
        if not container_path:
            return Path("")
        from urllib.parse import quote

        r = _http("GET", f"/api/cloud/worker/files?path={quote(container_path)}")
        dest = tmp / name
        dest.write_bytes(r.content)
        return dest

    audio_path = Path("")
    if payload.get("audio_path"):
        try:
            audio_path = dl(payload["audio_path"], "audio.wav")
        except Exception:
            audio_path = Path("")

    final = None
    if kind == "animacion":
        src = dl(payload["source_path"], "source.jpg")
        drv = dl(payload["driving_path"], "driving.mp4")
        final = _lp_animate(src, drv)
    elif kind == "lipsync":
        face = dl(payload["face_path"], "face.mp4")
        aud = dl(payload["audio_path"], "audio.wav")
        final = _lipsync(face, aud)
    elif kind == "editor":
        vis = dl(payload["visual_path"], "visual.mp4")
        aud = dl(payload.get("audio_path") or "", "audio.wav")
        subs = _srt(payload.get("script", "") or " ", aud) if aud.exists() else None
        final = _edit(vis, aud, payload.get("title", ""), subs, "720x1280")
    elif kind == "flujo":
        photo = dl(payload["photo_path"], "foto.jpg")
        drv = dl(payload["driving_path"], "driving.mp4")
        if not audio_path.exists():
            _progress(jid, "Generando voz (edge-tts)…")
            audio_path = _tts(payload.get("script") or "Anuncio", tmp / "voz.mp3")
        _progress(jid, "LivePortrait…", 30)
        animated = _lp_animate(photo, drv)
        visual = animated
        if payload.get("use_lipsync"):
            _progress(jid, "Wav2Lip…", 62)
            visual = _lipsync(animated, audio_path)
        _progress(jid, "FFmpeg…", 80)
        subs = _srt(payload.get("script") or " ", audio_path)
        final = _edit(visual, audio_path, payload.get("title", ""), subs,
                      (payload.get("resolution") or "720x1280"))
    else:
        raise RuntimeError(f"Kind no soportado: {kind}")
    if final is None or not Path(final).exists():
        raise RuntimeError("Procesamiento sin resultado")
    _progress(jid, "Subiendo MP4…", 95)
    return Path(final)


def main() -> None:
    if not BACKEND or not (WKEY or PRIV_HEX):
        raise SystemExit("Faltan BACKEND_URL y credenciales de worker (firma o clave).")
    _ensure_deps()
    _log(f"GPU: {_gpu()} | BACKEND={BACKEND}")
    start = time.time()
    try:
        import torch

        if torch.cuda.is_available():
            _log(f"CUDA {torch.cuda.get_device_name(0)} | {torch.cuda.get_device_properties(0).total_memory // 1024**2} MB")
    except Exception:
        pass
    while (time.time() - start) < MAX_RUNTIME_MIN * 60:
        try:
            r = _http("GET", "/api/cloud/worker/next")
        except Exception as exc:
            _log(f"Poll error: {exc}; reintento en 30s")
            time.sleep(30)
            continue
        try:
            data = r.json()
        except Exception:
            time.sleep(15)
            continue
        job = data if isinstance(data, dict) and data.get("id") else None
        if not job:
            _log("Sin trabajos. Polling 30s…")
            time.sleep(30)
            continue
        _log(f"Job {job['id']} ({job['kind']})")
        try:
            final = process({**job, "payload": job["payload"]})
            key = _upload_result(final)
            _result(job["id"], "completed", key)
            _log(f"Job {job['id']} completado -> {key}")
        except Exception as exc:
            _result(job["id"], "failed", "", str(exc)[:500])
            _log(f"Job {job['id']} failed: {exc}")
        finally:
            gc.collect()
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass


if __name__ == "__main__":
    main()
