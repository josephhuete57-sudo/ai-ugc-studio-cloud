"""Generación de subtítulos (.srt/.vtt) repartiendo la duración del audio por frase."""
from __future__ import annotations

import re
import time
from pathlib import Path

from app.services.media import probe_duration, unique_path


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+", (text or "").strip())
    out = []
    for p in parts:
        p = p.strip()
        if p:
            # Frases muy largas se cortan por comas para subtítulos legibles.
            while len(p) > 90:
                cut = p.rfind(",", 0, 90)
                if cut <= 0:
                    break
                out.append(p[: cut + 1].strip())
                p = p[cut + 1 :].strip()
            out.append(p)
    return out or [(text or "").strip()]


def _ts(seconds: float, dot: bool = False) -> str:
    ms = int(max(0.0, seconds) * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    sep = "." if dot else ","
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def build_subtitles(text: str, audio_path: str | Path, out_dir: Path) -> Path:
    sentences = split_sentences(text)
    duration = probe_duration(audio_path) or max(3.0, sum(len(s) for s in sentences) / 14.0)
    weights = [max(1, len(s)) for s in sentences]
    total = sum(weights)

    entries: list[tuple[float, float, str]] = []
    cursor = 0.0
    for s, w in zip(sentences, weights):
        span = duration * (w / total)
        entries.append((cursor, cursor + span, s))
        cursor += span

    stamp = int(time.time())
    out_dir.mkdir(parents=True, exist_ok=True)
    srt = unique_path(out_dir, f"subs_{stamp}.srt")
    lines = []
    for i, (a, b, s) in enumerate(entries, 1):
        lines.append(f"{i}\n{_ts(a)} --> {_ts(b)}\n{s}\n")
    srt.write_text("\n".join(lines), encoding="utf-8")

    vtt = srt.with_suffix(".vtt")
    vtt.write_text("WEBVTT\n\n" + "\n".join(
        f"{_ts(a, True)} --> {_ts(b, True)}\n{s}\n" for a, b, s in entries
    ), encoding="utf-8")
    return srt
