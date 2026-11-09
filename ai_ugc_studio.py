import os
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")

OUT = BASE / "output"
AUDIO = OUT / "audio"
VIDEO = OUT / "videos"

AUDIO.mkdir(parents=True, exist_ok=True)
VIDEO.mkdir(parents=True, exist_ok=True)

def generate_voice(text):
    key = os.getenv("FISH_AUDIO_API_KEY")
    ref = os.getenv("FISH_AUDIO_REFERENCE_ID")

    if not key or not ref:
        raise RuntimeError(
            "Configura FISH_AUDIO_API_KEY y "
            "FISH_AUDIO_REFERENCE_ID en .env"
        )

    url = "https://api.fish.audio/v1/tts"

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    payload = {
        "text": text,
        "reference_id": ref,
        "format": os.getenv("FISH_AUDIO_FORMAT", "mp3")
    }

    response = requests.post(
        url, headers=headers, json=payload, timeout=180
    )
    response.raise_for_status()

    path = AUDIO / "influencer_voice.mp3"
    path.write_bytes(response.content)

    return path

def create_video(image_path, audio_path):
    image_path = Path(image_path)
    audio_path = Path(audio_path)

    if not image_path.exists():
        raise FileNotFoundError(f"No existe la imagen: {image_path}")

    output = VIDEO / "ugc_preview.mp4"

    command = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-i", str(audio_path),
        "-vf",
        "scale=720:1280:force_original_aspect_ratio=increase,"
        "crop=720:1280,zoompan=z='min(zoom+0.0005,1.08)':"
        "d=1:s=720x1280:fps=24,format=yuv420p",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        str(output)
    ]

    subprocess.run(command, check=True)
    return output

if __name__ == "__main__":
    print("AI UGC STUDIO preparado.")
    print("Configura tu API de Fish Audio en .env")
    print("Motor de voz: Fish Audio")
    print("Motor de edición: FFmpeg")
