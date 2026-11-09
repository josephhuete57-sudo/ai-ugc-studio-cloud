import time

import requests

B = "http://127.0.0.1:8001"
r = requests.post(
    f"{B}/api/editor/render",
    json={
        "visual_path": r"C:\AI_UGC_STUDIO\assets\influencers\s0.jpg",
        "audio_path": r"C:\AI_UGC_STUDIO\assets\audio\voz_local_1794247183.wav",
        "resolution": "1080x1920",
        "trim_start": 1.0,
        "trim_end": 3.0,
        "title": "PRUEBA 1080",
        "project_id": 1,
    },
    timeout=30,
)
print("RENDER1080", r.status_code, r.text[:200])
jid = r.json()["job_id"]
for _ in range(90):
    j = requests.get(f"{B}/api/jobs/{jid}", timeout=30).json()
    print("JOB", j["status"], j["step"], j["progress"], j.get("result_path"))
    if j["status"] in ("done", "error", "cancelled"):
        print("ERR", (j.get("error") or "")[:400])
        break
    time.sleep(3)
