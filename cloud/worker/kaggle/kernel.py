"""Worker remoto (Kaggle o GitHub Actions) — AI UGC STUDIO FREE CLOUD.

Polls la cola del backend y ejecuta en CPU/GPU: edge-tts, Wav2Lip y FFmpeg.
Sin cómputo local: este script corre en la nube gratuita.
Params: BACKEND_URL, WORKER_KEY, HF_TOKEN(optional).
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
MAX_RUNTIME_MIN = int(os.environ.get("MAX_RUNTIME_MIN", "170"))
# Pesos públicos alojados en HF (evita Google Drive y descargas frágiles).
WEIGHTS_REPO = os.environ.get("WEIGHTS_REPO", "josjshid99/ai-ugc-studio-weights")
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
    """Instala lo que falta para Wav2Lip + TTS + FFmpeg.

    Kaggle ya trae torch/CUDA, cv2, scipy, imageio-ffmpeg y ffmpeg.
    Solo se instala lo ausente.
    """
    missing = []
    onnx_pkg = "onnxruntime-gpu" if _has_nvidia() else "onnxruntime"
    for mod, pkg in [
        ("onnxruntime", onnx_pkg),
        ("cv2", "opencv-python-headless"),
        ("huggingface_hub", "huggingface_hub"),
        ("requests", "requests"),
        ("edge_tts", "edge-tts"),
        ("scipy", "scipy"),
        ("librosa", "librosa"),
        ("soundfile", "soundfile"),
        ("cryptography", "cryptography"),
        ("torch", "torch"),
        ("tyro", "tyro"),
        ("pykalman", "pykalman"),
        ("lmdb", "lmdb"),
        ("ffmpeg", "ffmpeg-python"),
        ("rich", "rich"),
        ("imageio", "imageio"),
        ("matplotlib", "matplotlib"),
        # Wav2Lip: detección de cara (torchvision) y lectura de imagen (pillow).
        ("torchvision", "torchvision"),
        ("PIL", "pillow"),
        ("tqdm", "tqdm"),
    ]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        _log(f"Instalando deps: {missing}")
        try:
            _pip(*missing)
        except subprocess.CalledProcessError:
            # onnxruntime-gpu puede no tener rueda para la versión de Python:
            # se cae a la variante CPU (LivePortrait sigue funcionando en GPU con torch).
            _log(f"Fallback: instalando deps sin {onnx_pkg}")
            _pip(*[p for p in missing if p != onnx_pkg], "onnxruntime")
    for mod in ("onnxruntime", "tyro", "pykalman", "lmdb", "librosa", "edge_tts",
                "torchvision", "PIL"):
        try:
            __import__(mod)
            _log(f"DEP OK {mod}")
        except Exception as exc:
            _log(f"DEP FALLA {mod}: {exc!r}")


def _has_nvidia() -> bool:
    try:
        r = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=30)
        return r.returncode == 0 and "GPU" in r.stdout
    except Exception:
        return False


def _ensure_torch_cuda() -> None:
    """Si hay GPU pero torch es la build CPU, reinstala torch con CUDA.

    La imagen de Kaggle sin GPU verificada trae ``torch +cpu``. Si eso pasara
    también con GPU activa, LivePortrait acabaría en CPU (20 min por vídeo);
    aquí se corrige automáticamente usando el índice oficial de PyTorch.
    """
    if not _has_nvidia():
        _log("Sin nvidia-smi: se asume CPU")
        return
    try:
        import torch

        if torch.cuda.is_available():
            _log(f"TORCH CUDA OK {torch.__version__} {torch.cuda.get_device_name(0)}")
            return
        _log(f"TORCH sin CUDA ({torch.__version__}): reinstalando build CUDA")
    except Exception:
        _log("torch no importable: instalando build CUDA")
    idx = "https://download.pytorch.org/whl/cu124"
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--force-reinstall",
                        "--no-cache-dir", "--index-url", idx, "torch", "torchvision"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import importlib

        import torch as _t

        importlib.reload(_t)
        _log(f"TORCH CUDA {_t.__version__} disponible={_t.cuda.is_available()}")
    except Exception as exc:
        _log(f"AVISO: no se pudo instalar torch CUDA ({exc!r}); se sigue en CPU")


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


def _err_text(exc: BaseException, limit: int = 480) -> str:
    """El backend corta el error a 500 caracteres desde el INICIO.

    Un traceback útil termina en la última línea (tipo + mensaje), así que se
    envía la cola del texto para que no se pierda la causa real.
    """
    msg = f"{type(exc).__name__}: {exc}"
    return msg if len(msg) <= limit else "…" + msg[-limit:]


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


def _hf_get(filename: str, dest: Path, repo: str | None = None) -> Path:
    """Descarga un archivo de HF (con caché) y lo copia al destino esperado."""
    from huggingface_hub import hf_hub_download

    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    got = hf_hub_download(repo_id=repo or WEIGHTS_REPO, filename=filename,
                          token=HF_TOKEN or None)
    shutil.copy2(got, str(dest))
    return dest


def _photo_motion(photo: Path, seconds: float = 6.0) -> Path:
    """Clip vertical con zoom lento a partir de la foto (sin IA, FFmpeg puro).

    Sustituye a LivePortrait para el paso 'animacion': no inventa movimiento
    facial, solo un Ken Burns honesto que sirve de base para Wav2Lip/editor.
    """
    _require_input(photo, "foto")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg no disponible para animar la foto")
    out = WORK / f"photo_motion_{int(time.time())}.mp4"
    vf = ("scale=1440:-2,crop=1440:2560,"
          "zoompan=z='min(zoom+0.0006,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
          "d=1:s=720x1280:fps=24,format=yuv420p")
    subprocess.run([ffmpeg, "-y", "-loop", "1", "-i", str(photo), "-t", f"{seconds:.2f}",
                    "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    str(out)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=300)
    if not out.is_file() or out.stat().st_size < 2048:
        raise RuntimeError("FFmpeg no pudo animar la foto")
    return out



def _on_gpu() -> bool:
    """True solo si torch tiene CUDA real (no basta con 'nvidia-smi')."""
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _require_input(path: Path, label: str) -> None:
    """Falla con un mensaje claro si la descarga del backend quedó vacía."""
    if not path.is_file() or path.stat().st_size < 512:
        raise RuntimeError(f"Entrada inválida ({label}): no se pudo descargar del backend")


def _patch_w2l(repo: Path) -> None:
    """Compatibilidad de Wav2Lip con librosa >= 0.10 (kwargs obligatorios)."""
    audio = repo / "audio.py"
    if not audio.exists():
        return
    src = audio.read_text(encoding="utf-8")
    old = "return librosa.filters.mel(hp.sample_rate, hp.n_fft, n_mels=hp.num_mels,"
    new = "return librosa.filters.mel(sr=hp.sample_rate, n_fft=hp.n_fft, n_mels=hp.num_mels,"
    if old in src:
        audio.write_text(src.replace(old, new), encoding="utf-8")
        _log("audio.py de Wav2Lip parcheado para librosa nuevo")


def _w2l_weights() -> str:
    """Pesos de Wav2Lip + s3fd desde HF (el checkpoint ya está convertido)."""
    repo = _clone("https://github.com/Rudrabha/Wav2Lip.git", "Wav2Lip")
    _patch_w2l(repo)
    state = _hf_get("wav2lip_gan_state.pth", CACHE / "wav2lip_gan_state.pth")
    sfd = repo / "face_detection" / "detection" / "sfd" / "s3fd.pth"
    if not (sfd.exists() and sfd.stat().st_size > 1_000_000):
        _hf_get("s3fd.pth", sfd)
    return str(state)



def _lipsync(face: Path, audio: Path) -> Path:
    """Wav2Lip sobre una foto (modo estático) o un vídeo, en CPU o GPU."""
    _require_input(face, "foto/cara")
    _require_input(audio, "audio")
    repo = _clone("https://github.com/Rudrabha/Wav2Lip.git", "Wav2Lip")
    ckpt = _w2l_weights()
    # Wav2Lip escribe temp/temp.wav y temp/result.avi relativos al cwd.
    (repo / "temp").mkdir(exist_ok=True)
    out = WORK / f"lipsync_{int(time.time())}.mp4"
    log = WORK / f"lipsync_{int(time.time())}.log"
    cmd = [sys.executable, str(repo / "inference.py"),
           "--checkpoint_path", ckpt, "--face", str(face),
           "--audio", str(audio), "--outfile", str(out),
           "--pads", "0", "10", "0", "0",
           "--wav2lip_batch_size", "16", "--face_det_batch_size", "1",
           "--fps", "24"]
    if face.suffix.lower() in (".jpg", ".jpeg", ".png"):
        cmd += ["--static", "True"]
    with log.open("w", encoding="utf-8", errors="replace") as fh:
        proc = subprocess.run(cmd, cwd=str(repo), stdout=fh, stderr=subprocess.STDOUT,
                              timeout=3600,
                              env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))
    if proc.returncode != 0 or not out.exists() or out.stat().st_size < 2048:
        tail = log.read_text(encoding="utf-8", errors="replace")[-1800:]
        raise RuntimeError(f"Wav2Lip falló ({proc.returncode}): {tail}")
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

    def _ts(sec: float) -> str:
        sec = max(0.0, sec)
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"

    lines, cur = [], 0.0
    for i, p in enumerate(parts, 1):
        span = dur * (len(p) / total)
        lines.append(f"{i}\n{_ts(cur)} --> {_ts(cur + span)}\n{p}\n")
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
        def _secs(tc: str) -> float:
            h, m, s = tc.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)

        entries = []
        for block in subs.read_text(encoding="utf-8", errors="ignore").strip().split("\n\n"):
            rows = [l.strip() for l in block.splitlines() if l.strip()]
            if len(rows) >= 3:
                a, b = rows[1].split("-->")
                entries.append((_secs(a.strip().replace(",", ".")),
                                _secs(b.strip().replace(",", ".")),
                                " ".join(rows[2:])))
        if entries:
            filters = []
            for i, (a, b, txt) in enumerate(entries):
                tf = WORK / f"sub{i}.txt"
                tf.write_text(txt, encoding="utf-8")
                filters.append(f"drawtext=fontfile='{font}':textfile='{tf.as_posix()}':fontsize=38:"
                               f"fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:"
                               f"y=h-text_h-110:enable='between(t,{a:.3f},{b:.3f})'")
            subs_filter = ",".join(filters) + ","
    title_filter = ""
    if title and font:
        tf = WORK / "title.txt"
        tf.write_text(title[:60], encoding="utf-8")
        title_filter = (f"drawtext=fontfile='{font}':textfile='{tf.as_posix()}':fontsize=44:"
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
        final = _photo_motion(src)
    elif kind == "lipsync":
        face = dl(payload["face_path"], "face.mp4")
        aud = dl(payload["audio_path"], "audio.wav")
        final = _lipsync(face, aud)
    elif kind == "editor":
        vis = dl(payload["visual_path"], "visual.mp4")
        aud = dl(payload.get("audio_path") or "", "audio.wav")
        subs = _srt(payload.get("script", "") or " ", aud) if aud.is_file() else None
        final = _edit(vis, aud, payload.get("title", ""), subs, "720x1280")
    elif kind == "flujo":
        photo = dl(payload["photo_path"], "foto.jpg")
        # Path("") == Path(".") y existe: hay que comprobar is_file(), no exists().
        if not audio_path.is_file() or audio_path.stat().st_size < 1024:
            _progress(jid, "Generando voz (edge-tts)…")
            audio_path = _tts(payload.get("script") or "Anuncio", tmp / "voz.mp3")
        # Cadena sin LivePortrait: la propia foto es la cara de Wav2Lip
        # (modo estático). El vídeo de referencia del payload se ignora.
        _progress(jid, "Wav2Lip…", 55)
        if payload.get("use_lipsync", True):
            visual = _lipsync(photo, audio_path)
        else:
            visual = _photo_motion(photo)
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
    _ensure_torch_cuda()
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
            from urllib.parse import quote as _q

            r = _http("GET", f"/api/cloud/worker/next?gpu={_q(_gpu())}&v=kaggle-1.0")
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
            _result(job["id"], "failed", "", _err_text(exc))
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
