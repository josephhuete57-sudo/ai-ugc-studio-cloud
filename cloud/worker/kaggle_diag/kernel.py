"""Diagnóstico del entorno GPU de Kaggle para AI UGC STUDIO.

Comprueba: CUDA, internet, instalación de dependencias reales y descarga de
pesos desde Hugging Face. No procesa vídeo (eso lo hace el worker).
"""
import platform
import subprocess
import sys
import time

print("PYTHON", sys.version.split()[0], platform.platform(), flush=True)

# ---------- GPU ----------
HAS_CUDA = False
try:
    import torch
    HAS_CUDA = torch.cuda.is_available()
    print("TORCH", torch.__version__, "cuda", HAS_CUDA, flush=True)
    if HAS_CUDA:
        print("GPU", torch.cuda.get_device_name(0),
              torch.cuda.get_device_properties(0).total_memory // 1024**2, "MB", flush=True)
    print("TORCH_CUDA_BUILD", torch.version.cuda, flush=True)
except Exception as exc:
    print("TORCH_FAIL", repr(exc), flush=True)

# ---------- internet ----------
NET = False
try:
    import socket
    socket.gethostbyname("huggingface.co")
    print("DNS_OK huggingface.co", flush=True)
    import urllib.request
    t0 = time.time()
    with urllib.request.urlopen("https://huggingface.co", timeout=20) as r:
        print("HTTP_OK", r.status, round(time.time() - t0, 1), "s", flush=True)
    NET = True
except Exception as exc:
    print("NET_FAIL", repr(exc)[:300], flush=True)

# ---------- dependencias ----------
for mod in ("insightface", "onnxruntime", "cv2", "tyro", "pykalman", "lmdb",
            "onnx", "imageio_ffmpeg", "skimage", "albumentations", "gradio",
            "scipy", "librosa", "soundfile", "edge_tts", "huggingface_hub"):
    try:
        m = __import__(mod)
        print("OK", mod, getattr(m, "__version__", ""), flush=True)
    except Exception as exc:
        print("MISSING", mod, type(exc).__name__, flush=True)

print("FFMPEG", subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
      .stdout.splitlines()[:1], flush=True)

# ---------- instalación real ----------
if NET:
    pkgs = []
    for mod, pkg in (("onnxruntime", "onnxruntime-gpu"), ("tyro", "tyro"),
                     ("pykalman", "pykalman"), ("lmdb", "lmdb"),
                     ("librosa", "librosa"), ("soundfile", "soundfile"),
                     ("edge_tts", "edge-tts"), ("ffmpeg", "ffmpeg-python")):
        try:
            __import__(mod)
        except Exception:
            pkgs.append(pkg)
    if pkgs:
        print("PIP_INSTALL", pkgs, flush=True)
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", *pkgs],
                           capture_output=True, text=True, timeout=1800)
        print("PIP_RC", r.returncode, flush=True)
        print((r.stderr or "")[-1200:], flush=True)
    for mod in ("onnxruntime", "tyro", "pykalman", "lmdb", "librosa", "edge_tts"):
        try:
            __import__(mod)
            print("AFTER_OK", mod, flush=True)
        except Exception as exc:
            print("AFTER_FAIL", mod, repr(exc)[:200], flush=True)

    # ---------- pesos desde HF ----------
    try:
        from huggingface_hub import hf_hub_download
        t0 = time.time()
        p = hf_hub_download("josjshid99/ai-ugc-studio-weights",
                            "wav2lip_gan_state.pth")
        import os
        print("HF_W2L_OK", os.path.getsize(p), round(time.time() - t0, 1), "s", flush=True)
    except Exception as exc:
        print("HF_W2L_FAIL", repr(exc)[:300], flush=True)
    try:
        from huggingface_hub import hf_hub_download
        p = hf_hub_download("josjshid99/ai-ugc-studio-weights",
                            "liveportrait/landmark.onnx")
        import os
        print("HF_LANDMARK_OK", os.path.getsize(p), flush=True)
    except Exception as exc:
        print("HF_LANDMARK_FAIL", repr(exc)[:300], flush=True)
else:
    print("SKIP_INSTALL sin internet", flush=True)

print("DISK", subprocess.run(["df", "-h", "/kaggle/working"], capture_output=True, text=True)
      .stdout.replace("\n", " | "), flush=True)
print("DIAG_DONE gpu=%s net=%s" % (HAS_CUDA, NET), flush=True)
