"""Editor de vídeo con FFmpeg: composición 9:16, subtítulos, música y exportación MP4."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from app.core import jobs
from app.core.config import settings
from app.services.media import probe_duration, redact, unique_path

_FONT_FILE = "C:/Windows/Fonts/arial.ttf"


def _parse_resolution(resolution: str) -> tuple[int, int]:
    for sep in ("x",):
        if sep in (resolution or ""):
            w, _, h = resolution.lower().partition(sep)
            try:
                W, H = int(w), int(h)
            except ValueError:
                return settings.VIDEO_WIDTH, settings.VIDEO_HEIGHT
            if 240 <= W <= 3840 and 240 <= H <= 3840 and W % 2 == 0 and H % 2 == 0:
                return W, H
    return settings.VIDEO_WIDTH, settings.VIDEO_HEIGHT


def _parse_srt(path: Path) -> list[tuple[float, float, str]]:
    entries: list[tuple[float, float, str]] = []
    blocks = path.read_text(encoding="utf-8", errors="ignore").strip().split("\n\n")
    for b in blocks:
        lines = [l.strip() for l in b.strip().splitlines() if l.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        rng = lines[1].split("-->")
        try:
            def _ts(s: str) -> float:
                s = s.replace(",", ".").strip()
                h, m, sec = s.split(":")
                return int(h) * 3600 + int(m) * 60 + float(sec)

            entries.append((_ts(rng[0]), _ts(rng[1]), " ".join(lines[2:])))
        except (ValueError, IndexError):
            continue
    return entries


def _subtitle_drawtext_filters(srt_path: Path, out_dir: Path) -> str:
    """Un drawtext por entrada con textfile (evita escapes y fontconfig/libass).

    Se usa cwd=out_dir y nombres relativos para evitar ':' en el parser del filtro.
    """
    entries = _parse_srt(srt_path)
    filters = []
    for i, (a, b, text) in enumerate(entries):
        tf = out_dir / f"line_{i}.txt"
        tf.write_text(text, encoding="utf-8")
        filters.append(
            f"drawtext=fontfile='arial.ttf':textfile='line_{i}.txt':"
            f"fontsize=38:fontcolor=white:borderw=2:bordercolor=black:"
            f"x=(w-text_w)/2:y=h-text_h-110:line_spacing=6:enable='between(t,{a:.2f},{b:.2f})'"
        )
    return ",".join(filters)


class VideoEditorError(RuntimeError):
    pass


def _esc_filter_path(p: Path) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:")


def render_announcement(
    job_id: int,
    visual: str | Path,
    audio: str | Path | None = None,
    music: str | Path | None = None,
    subtitles: str | Path | None = None,
    title: str = "",
    voice_volume: float = 1.0,
    music_volume: float = 0.25,
    zoom: bool = True,
    resolution: str = "720x1280",
    trim_start: float = 0.0,
    trim_end: float | None = None,
    report=None,
) -> Path:
    """Compone el anuncio con FFmpeg (H.264 ultrafast CPU + AAC).

    Progreso real: se calcula sobre la duración total del audio (o del visual).
    Sin audio: se genera pista silenciosa AAC para mantener el contenedor válido.
    """
    def say(step: str, pct: float | None = None) -> None:
        if report:
            report(step, pct)

    visual_p = Path(visual)
    if not visual_p.exists():
        raise VideoEditorError(f"No existe el vídeo/imagen base: {visual_p.name}")
    is_video = visual_p.suffix.lower() in settings.ALLOWED_VIDEOS
    W, H = _parse_resolution(resolution)
    FPS = settings.VIDEO_FPS

    duration = 0.0
    if audio and Path(audio).exists():
        duration = probe_duration(audio) or 0.0
    if not duration and is_video:
        duration = probe_duration(visual_p) or 0.0
    if not duration:
        duration = 6.0
    if trim_end is not None and trim_end > 0:
        duration = max(1.0, min(float(trim_end) - float(trim_start), duration))

    stamp = int(time.time())
    out = unique_path(settings.EXPORTS_DIR, f"anuncio_{stamp}.mp4")
    work_dir = unique_path(settings.PROJECTS_DIR / "subs", f"render_{stamp}")
    work_dir.mkdir(parents=True, exist_ok=True)
    # Fuente local sin ':' en la ruta (el parser del filtro rompe con 'C:/...').
    font_local = work_dir / "arial.ttf"
    if not font_local.exists():
        src_font = Path(_FONT_FILE)
        if src_font.exists():
            font_local.write_bytes(src_font.read_bytes())
            font_name = "arial.ttf"
        else:
            font_name = None
    else:
        font_name = "arial.ttf"

    # --- filtros de vídeo ---
    vf = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        f"zoompan=z='min(zoom+0.0006,1.10)':d=1:s={W}x{H}:fps={FPS},"
    ) if (zoom and not is_video) else (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
    )
    if title and font_name:
        title_file = work_dir / "title.txt"
        title_file.write_text(title[:60], encoding="utf-8")
        vf += (
            f"drawtext=fontfile='{font_name}':textfile='title.txt':"
            f"fontsize=44:fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:y=60,"
        )
    if subtitles and Path(subtitles).exists() and font_name:
        vf += _subtitle_drawtext_filters(Path(subtitles), work_dir) + ","
    vf += "format=yuv420p[vout]"

    # --- comando ---
    cmd: list[str] = ["ffmpeg", "-y"]
    seek = ["-ss", f"{max(0.0, float(trim_start)):.2f}"] if trim_start and float(trim_start) > 0 else []
    if is_video:
        cmd += [*seek, "-stream_loop", "-1", "-i", str(visual_p)]
    else:
        cmd += ["-loop", "1", "-i", str(visual_p)]
    audio_idx = None
    if audio and Path(audio).exists():
        cmd += [*seek, "-i", str(audio)]
        audio_idx = 1
        audio_label = "[1:a]"
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        audio_idx = 1
        audio_label = "[1:a]"

    music_idx = None
    if music and Path(music).exists():
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        music_idx = 2

    if music_idx is not None:
        fc = f"{vf};{audio_label}volume={voice_volume}[va];[2:a]volume={music_volume}[ma];[va][ma]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    else:
        fc = f"{vf};{audio_label}volume={voice_volume}[aout]"
    cmd += ["-filter_complex", fc, "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "ultrafast", "-threads", str(settings.FFMPEG_THREADS),
            "-pix_fmt", "yuv420p",
            "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
            "-t", f"{duration:.2f}", "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats", str(out)]

    say(f"Renderizando anuncio ({W}x{H}, {FPS} fps)…", 5.0)
    log_file = work_dir / "ffmpeg.log"
    log_fh = log_file.open("w", encoding="utf-8", errors="replace")
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(work_dir), stdout=subprocess.PIPE, stderr=log_fh, text=True,
            encoding="utf-8", errors="replace",
        )
        last_progress = 5.0
        assert proc.stdout is not None
        for line in proc.stdout:
            if jobs.is_cancelled(job_id):
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                raise VideoEditorError("Render cancelado por el usuario.")
            line = line.strip()
            if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
                try:
                    us = float(line.split("=", 1)[1])
                    last_progress = min(99.0, 5.0 + 94.0 * (us / 1_000_000 / max(duration, 0.1)))
                    say("Renderizando…", last_progress)
                except ValueError:
                    pass
        rc = proc.wait(timeout=300)
    except VideoEditorError:
        raise
    except Exception as exc:
        proc.kill()
        raise VideoEditorError(f"Fallo al ejecutar FFmpeg: {redact(str(exc))}") from exc
    finally:
        log_fh.close()

    if rc != 0 or not out.exists() or out.stat().st_size < 1000:
        tail = ""
        try:
            tail = log_file.read_text(encoding="utf-8", errors="replace")[-1500:]
        except Exception:
            pass
        raise VideoEditorError(f"FFmpeg falló al exportar: {redact(tail)}")
    say("MP4 exportado ✔", 100.0)
    return out


def render_preview_from_image(
    job_id: int, image: str | Path, seconds: float = 6.0, report=None
) -> Path:
    """Mini-preview síncrono para probar FFmpeg sin necesidad de audio."""
    def say(step: str, pct: float | None = None) -> None:
        if report:
            report(step, pct)
    image_p = Path(image)
    if not image_p.exists():
        raise VideoEditorError("Imagen no encontrada para la vista previa.")
    stamp = int(time.time())
    out = unique_path(settings.EXPORTS_DIR, f"preview_{stamp}.mp4")
    W, H, FPS = settings.VIDEO_WIDTH, settings.VIDEO_HEIGHT, settings.VIDEO_FPS
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(image_p),
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},format=yuv420p",
        "-c:v", "libx264", "-preset", "ultrafast", "-threads", str(settings.FFMPEG_THREADS), "-r", str(FPS),
        "-c:a", "aac", "-b:a", "128k", "-t", f"{seconds:.1f}",
        "-movflags", "+faststart", str(out),
    ]
    say("Vista previa FFmpeg…", 20.0)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0 or not out.exists():
        raise VideoEditorError(f"FFmpeg falló: {redact((r.stderr or '')[-800:])}")
    say("Vista previa lista ✔", 100.0)
    return out
