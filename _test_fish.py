import os, re, requests
from pathlib import Path
from dotenv import load_dotenv

p = Path(r"C:\AI_UGC_STUDIO")
load_dotenv(p / ".env")
key = os.getenv("FISH_AUDIO_API_KEY") or os.getenv("FISH_API_KEY")
if not key:
    print("FISH_ERROR: No se encontró la variable de API")
else:
    try:
        r = requests.get(
            "https://api.fish.audio/model",
            headers={"Authorization": f"Bearer {key}"},
            timeout=25
        )
        print("FISH_HTTP_STATUS:", r.status_code)
        print("FISH_CONNECTION:", "OK" if r.ok else "REVISAR CREDENCIALES O API")
    except Exception as e:
        print("FISH_ERROR:", str(e))
