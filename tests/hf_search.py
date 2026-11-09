"""Busca Spaces públicos de LivePortrait y prueba inferencia remota (patrón ZeroGPU)."""
import requests

S = requests.Session()
r = S.get(
    "https://huggingface.co/api/spaces",
    params={"search": "liveportrait", "full": "true", "limit": "30"},
    timeout=60,
)
print("HTTP", r.status_code)
data = r.json()
print("COUNT", len(data))
cands = []
for sp in data:
    sid = sp.get("id", "")
    runtime = (sp.get("runtime") or {}).get("hardware", "")
    likes = sp.get("likes", 0)
    sdk = sp.get("sdk", "")
    cands.append((likes, sid, runtime, sdk))
cands.sort(reverse=True)
for likes, sid, runtime, sdk in cands[:12]:
    print(f"LIKES={likes} SDK={sdk} HW={runtime} SP={sid}")
