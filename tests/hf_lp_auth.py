"""Reintenta LivePortrait público CON token HF (ZeroGPU exige auth)."""
from gradio_client import Client
from huggingface_hub import get_token

TOKEN = get_token()
print("TOKEN_OK", bool(TOKEN))

client = Client("KlingTeam/LivePortrait", token=TOKEN, hf_token=TOKEN) \
    if False else Client("KlingTeam/LivePortrait", token=TOKEN)
res = client.predict(
    r"C:\AI_UGC_STUDIO\assets\influencers\s0.jpg",
    {"video": r"C:\AI_UGC_STUDIO\projects\driving_short15.mp4", "subtitles": None},
    True, True, True,
    api_name="/gpu_wrapped_execute_video",
)
print("VIDEO_OK", str(res)[:400])
