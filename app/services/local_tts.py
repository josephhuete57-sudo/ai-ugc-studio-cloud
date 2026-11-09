"""TTS local gratuito con voces SAPI de Windows (System.Speech).

Sin instalación extra: usa las voces de Windows
(Microsoft Helena es-ES, Jarvis es-MX, Zira en-US por defecto).
Genera WAV PCM 16 kHz mono listo para Wav2Lip / FFmpeg.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from app.core.config import settings
from app.services.media import unique_path

_PS1 = Path(__file__).with_name("sapi_tts.ps1")


class LocalTTSError(RuntimeError):
    pass


def list_voices() -> list[dict]:
    """Voces SAPI instaladas (nombre, idioma, género)."""
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() | "
        "ForEach-Object { \"$($_.VoiceInfo.Name)|$($_.VoiceInfo.Culture)|$($_.VoiceInfo.Gender)\" }"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True, text=True, timeout=60, check=True,
        )
    except Exception as exc:
        raise LocalTTSError(f"No se pudieron listar las voces locales: {exc}") from exc
    voices = []
    for line in out.stdout.splitlines():
        parts = line.strip().split("|")
        if len(parts) == 3 and parts[0]:
            voices.append({"id": parts[0], "name": parts[0], "culture": parts[1], "gender": parts[2]})
    return voices


def synthesize(
    text: str,
    voice_name: str | None = None,
    rate: int = 0,
    output_name: str | None = None,
) -> Path:
    """Sintetiza texto a WAV con System.Speech (SAPI)."""
    text = (text or "").strip()
    if not text:
        raise LocalTTSError("El guion está vacío.")
    if len(text) > 2000:
        raise LocalTTSError("El guion supera 2000 caracteres.")
    voices = list_voices()
    if not voices:
        raise LocalTTSError("No hay voces SAPI instaladas en Windows.")
    chosen = None
    if voice_name:
        for v in voices:
            if voice_name.lower() in v["id"].lower():
                chosen = v["id"]
                break
    if chosen is None:
        # Español primero (Helena es-ES / Jarvis es-MX), si no, la primera.
        for v in voices:
            if v["culture"].lower().startswith("es"):
                chosen = v["id"]
                break
        chosen = chosen or voices[0]["id"]

    stamp = int(time.time())
    filename = output_name or f"voz_local_{stamp}.wav"
    out = unique_path(settings.AUDIO_DIR, Path(filename).name)
    final_wav = out if out.suffix.lower() == ".wav" else out.with_suffix(".wav")
    tmp_wav = final_wav.with_name(final_wav.stem + "_raw.wav")
    ps_cmd = (
        f'Add-Type -AssemblyName System.Speech; '
        f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
        f'$s.SelectVoice("{chosen}"); $s.Rate = {int(rate)}; '
        f'$s.SetOutputToWaveFile("{tmp_wav}"); '
        f'$s.Speak("{text.replace(chr(34), chr(39))}"); $s.Dispose(); '
        f'Write-Output "OK {chosen}"'
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=180, check=True,
        )
    except Exception as exc:
        raise LocalTTSError(f"Fallo la síntesis SAPI: {exc}") from exc
    if not tmp_wav.exists() or tmp_wav.stat().st_size < 1000:
        raise LocalTTSError("SAPI no generó audio (revisa la voz seleccionada en Windows).")
    # Normalizar a 16 kHz mono para Wav2Lip.
    r2 = subprocess.run(
        ["ffmpeg", "-y", "-i", str(tmp_wav), "-ar", "16000", "-ac", "1",
         "-c:a", "pcm_s16le", str(final_wav)],
        capture_output=True, text=True, timeout=60,
    )
    tmp_wav.unlink(missing_ok=True)
    if r2.returncode != 0 or not final_wav.exists():
        raise LocalTTSError("No se pudo convertir el audio local a WAV 16 kHz.")
    return final_wav
