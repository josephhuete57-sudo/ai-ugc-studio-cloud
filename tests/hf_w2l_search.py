"""Busca Spaces públicos de Wav2Lip y prueba lip-sync real"""
import os

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
from gradio_client import Client
from huggingface_hub import get_token

TOKEN = get_token()
import requests

r = requests.get("https://huggingface.co/api/spaces", params={"search": "wav2lip", "limit": "20"}, timeout=30)
cands = sorted((s.get("likes", 0), s.get("id")) for s in r.json())
cands = [sid for _, sid in cands[-10:] if sid]
print("CANDS", cands)

PHOTO = r"C:\AI_UGC_STUDIO\assets\influencers\s0.jpg"
AUDIO = r"C:\AI_UGC_STUDIO\assets\audio\prueba_tono.wav"
for space in cands[:4]:
    try:
        c = Client(space, token=TOKEN)
        api = c.view_api()
        eps = list((api or {}).get("named_endpoints") or {})
        print("SPACE", space, "EPS", eps, flush=True)
    except Exception as exc:
        print("  LIST_FAIL", space, str(exc)[:120], flush=True)
