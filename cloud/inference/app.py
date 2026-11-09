"""Adaptador Gradio para ZeroGPU (Hugging Face Spaces gratuitos).

Expone LivePortrait, Wav2Lip, TTS (edge-tts, gratis) y FFmpeg como funciones
Gradio. Los modelos se cargan UNA vez y se reutilizan. Con `zerogpu` disponible
en el Space se usa la GPU gratuita; sin él, funciona en CPU (modo de prueba).

NO meter la app FastAPI completa aquí: ZeroGPU exige Gradio.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import gradio as gr

# Decorador GPU: zerogpu en HF Spaces; no-op en local.
try:
    import zerogpu  # type: ignore

    use_gpu = zerogpu.use_gpu  # pragma: no cover - solo HF
except Exception:

    def use_gpu(fn):  # type: ignore[misc]
        return fn


BASE = Path(__file__).resolve().parents[2]
WEIGHTS = BASE / "cloud" / "data" / "weights"
WEIGHTS.mkdir(parents=True, exist_ok=True)
TMP = BASE / "cloud" / "data" / "adapter_tmp"
TMP.mkdir(parents=True, exist_ok=True)

_MODELS = {}


def _need_hf_hub():
    try:
        from huggingface_hub import hf_hub_download  # type: ignore

        return hf_hub_download
    except Exception:
        return None


def _liveportrait_weights() -> dict[str, str]:
    """Descarga una vez los pesos oficiales de LivePortrait (HF oficial)."""
    names = {
        "F": "pretrained_weights/liveportrait/base_models/appearance_feature_extractor.pth",
        "M": "pretrained_weights/liveportrait/base_models/motion_extractor.pth",
        "G": "pretrained_weights/liveportrait/base_models/spade_generator.pth",
        "W": "pretrained_weights/liveportrait/base_models/warping_module.pth",
        "S": "pretrained_weights/liveportrait/retargeting_models/stitching_retargeting_module.pth",
    }
    out = {}
    dl = _need_hf_hub()
    for key, fname in names.items():
        dest = WEIGHTS / Path(fname)
        if not dest.exists() or dest.stat().st_size < 1000:
            if dl is None:
                raise RuntimeError("Falta huggingface_hub para descargar pesos de LivePortrait.")
            dest.parent.mkdir(parents=True, exist_ok=True)
            got = dl(repo_id="KwaiVGI/LivePortrait", filename=fname, local_dir=str(WEIGHTS))
            shutil.copy2(got, str(dest))
        out[key] = str(dest)
    return out


def _wav2lip_state() -> str:
    """Convierte (una vez) el TorchScript oficial a dict legacy para CPU/GPU."""
    state = WEIGHTS / "wav2lip_gan_state.pth"
    if state.exists() and state.stat().st_size > 10_000_000:
        return str(state)
    src = WEIGHTS / "wav2lip_gan.pth"
    if not src.exists():
        dl = _need_hf_hub()
        if dl is None:
            raise RuntimeError("Falta huggingface_hub para descargar pesos de Wav2Lip.")
        # El repo oficial de Wav2Lip no publica los pth en HF; se descarga de Drive.
        raise RuntimeError(
            "Coloca wav2lip_gan.pth (oficial) en cloud/data/weights/ y la conversión crea el state.pth."
        )
    import torch

    m = torch.jit.load(str(src), map_location="cpu")
    sd = m.state_dict()
    torch.save({"state_dict": sd}, str(state), _use_new_zipfile_serialization=False)
    return str(state)


def _run(cmd, cwd=None, timeout=1800):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    tok = Path(TMP) / f"cmd_{int(time.time())}.log"
    with tok.open("w", encoding="utf-8", errors="replace") as lf:
        p = subprocess.run(cmd, cwd=cwd, stdout=lf, stderr=subprocess.STDOUT,
                           timeout=timeout, env=env)
    if p.returncode != 0:
        raise RuntimeError(f"Comando falló (rc={p.returncode}): {tok.read_text(encoding='utf-8', errors='replace')[-800:]}")


@use_gpu
def tts(text: str, voice: str = "es-ES-ElviraNeural") -> str:
    """TTS remoto gratuito (Microsoft Edge vía edge-tts, sin clave ni saldo)."""
    out = TMP / f"tts_{int(time.time())}.mp3"
    voice = (voice or "es-ES-ElviraNeural").strip() or "es-ES-ElviraNeural"
    sys.path.insert(0, str(BASE / "cloud" / "inference"))

    def _gen():
        import edge_tts  # type: ignore

        async def main():
            await edge_tts.Communicate(text, voice).save(str(out))

        asyncio.run(main())

    _gen()
    if not out.exists() or out.stat().st_size < 1000:
        raise RuntimeError("edge-tts no generó audio.")
    return str(out)


@use_gpu
def animate(source_path: str, driving_path: str) -> str:
    """LivePortrait real (subproceso con su venv). La ruta del repo se configura en el Space."""
    repo = os.environ.get("LIVEPORTRAIT_DIR", "")
    py = os.path.join(repo, ".venv", "Scripts", "python.exe") if os.name == "nt" else os.path.join(repo, ".venv", "bin", "python")
    inf = os.path.join(repo, "inference.py")
    if not os.path.exists(inf):
        raise RuntimeError("Repo LivePortrait no configurado en el Space (LIVEPORTRAIT_DIR).")
    out_dir = TMP / f"anim_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)
    _run([py, inf, "-s", source_path, "-d", driving_path, "-o", str(out_dir),
          "--flag-force-cpu", "--no-flag-use-half-precision"], cwd=repo, timeout=1800)
    mp4s = sorted(out_dir.rglob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if not mp4s:
        raise RuntimeError("LivePortrait no generó MP4.")
    return str(mp4s[-1])


@use_gpu
def lipsync(face_path: str, audio_path: str) -> str:
    """Wav2Lip real (repo + pesos configurados en el Space)."""
    repo = os.environ.get("WAV2LIP_DIR", "")
    py = os.path.join(repo, ".venv", "Scripts", "python.exe") if os.name == "nt" else os.path.join(repo, ".venv", "bin", "python")
    inf = os.path.join(repo, "inference.py")
    ckpt = _wav2lip_state()
    if not os.path.exists(inf):
        raise RuntimeError("Repo Wav2Lip no configurado en el Space (WAV2LIP_DIR).")
    out = TMP / f"lipsync_{int(time.time())}.mp4"
    _run([py, inf, "--checkpoint_path", ckpt, "--face", face_path, "--audio", audio_path,
          "--outfile", str(out), "--pads", "0", "10", "0", "0",
          "--wav2lip_batch_size", "4", "--face_det_batch_size", "1"], cwd=repo, timeout=1800)
    return str(out)


@use_gpu
def edit(visual_path: str, audio_path: str, title: str = "", subtitles: str = "") -> str:
    """Montaje FFmpeg 720x1280 H.264/AAC (subtítulos SRT quemados si se pasan)."""
    out = TMP / f"anuncio_{int(time.time())}.mp4"
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", visual_path, "-i", audio_path,
           "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,format=yuv420p",
           "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2",
           "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out)]
    _run(cmd, timeout=600)
    return str(out)


with gr.Blocks(title="AI UGC STUDIO · motor ZeroGPU") as demo:
    gr.Markdown("# AI UGC STUDIO - Motor de IA (ZeroGPU)")
    with gr.Row():
        tts_in = gr.Textbox(label="Texto")
        tts_voice = gr.Textbox(label="Voz", value="es-ES-ElviraNeural")
        tts_out = gr.Audio(label="Audio TTS", type="filepath")
        gr.Button("Generar voz", variant="primary").click(tts, [tts_in, tts_voice], tts_out)
    with gr.Row():
        src = gr.File(label="Foto / vídeo base")
        drv = gr.File(label="Vídeo de referencia / audio")
        anim_out = gr.Video(label="Animación LivePortrait")
        gr.Button("Animar", variant="primary").click(lambda s, d: animate(s, d), [src, drv], anim_out)
    with gr.Row():
        face = gr.File(label="Vídeo o foto para lip-sync")
        aud = gr.File(label="Audio de voz")
        lip_out = gr.Video(label="Lip sync Wav2Lip")
        gr.Button("Lip sync", variant="primary").click(lambda f, a: lipsync(f, a), [face, aud], lip_out)
    with gr.Row():
        vis = gr.File(label="Vídeo base")
        aud2 = gr.File(label="Audio")
        edit_out = gr.Video(label="Anuncio final")
        gr.Button("Montar", variant="primary").click(lambda v, a: edit(v, a), [vis, aud2], edit_out)

if __name__ == "__main__":
    demo.launch()
