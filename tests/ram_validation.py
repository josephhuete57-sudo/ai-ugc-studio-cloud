"""Validación completa UGC con medición de RAM (LOW_RAM_12GB).

Crea un proyecto nuevo, genera voz local, flujo completo y reporta:
RAM antes/mínima libre/después, tiempo total, artefactos y ffprobe final.
"""
import json
import sqlite3
import subprocess
import time
from pathlib import Path

import requests

B = "http://127.0.0.1:8001"
BASE_DIR = Path(r"C:\AI_UGC_STUDIO")
LOG = BASE_DIR / "logs" / "ram_validation.json"
history = {"samples": []}


def sn() -> dict:
    return requests.get(f"{B}/api/system/memory", timeout=30).json()


start = time.time()
before = sn()
history["before"] = before
print("BEFORE free", before["free_gb"], "used", before["used_gb"], "load", before["load_percent"])

# Proyecto nuevo
r = requests.post(
    f"{B}/api/projects",
    json={
        "name": "Validacion RAM UGC",
        "influencer_id": 1,
        "product": "protector solar invisible",
        "script": "Deja de gastar dinero en lo mismo. Prueba esto antes de que se agote.",
        "status": "draft",
    },
    timeout=30,
)
pid = r.json()["id"]
print("PROJECT", pid)

# Audio local (sin Fish, evita depender de saldo)
r = requests.post(
    f"{B}/api/voice/generate",
    json={"text": "Deja de gastar dinero en lo mismo. Prueba esto antes de que se agote.",
          "provider": "local", "project_id": pid},
    timeout=180,
)
print("VOICE", r.status_code, r.json().get("path"))

# Flujo completo con lip-sync
r = requests.post(
    f"{B}/api/flow/generate",
    json={
        "project_id": pid,
        "driving_video": str(BASE_DIR / "projects" / "driving_short.mp4"),
        "use_lipsync": True,
        "title": "VALIDACION RAM",
        "audio_provider": "local",
        "resolution": "720x1280",
    },
    timeout=30,
)
jid = r.json()["job_id"]
print("JOB", jid)

last = None
while True:
    j = requests.get(f"{B}/api/jobs/{jid}", timeout=30).json()
    last = j
    if j["status"] in ("done", "error", "cancelled"):
        break
    m = sn()
    history["samples"].append({
        "t": round(time.time() - start, 1),
        "free_gb": m["free_gb"],
        "used_gb": m["used_gb"],
        "load_percent": m["load_percent"],
        "liveportrait_mb": m["liveportrait_mb"],
        "wav2lip_mb": m["wav2lip_mb"],
        "python_mb": m["python_mb"],
        "stage": j["step"],
    })
    if int(time.time() - start) % 120 < 30:
        print(f"[{int(time.time()-start)}s] {j['status']} {j['step']} free={m['free_gb']}GB LP={m['liveportrait_mb']}MB W2L={m['wav2lip_mb']}MB")
    time.sleep(30)

after = sn()
history["after"] = after
history["job"] = {"id": jid, "status": last["status"], "result_path": last.get("result_path"),
                  "error": (last.get("error") or "")[:500]}
history["project_id"] = pid
history["elapsed_s"] = round(time.time() - start, 1)
samples = history["samples"]
history["min_free_gb"] = min((s["free_gb"] for s in samples), default=after["free_gb"])
history["max_lp_mb"] = max((s["liveportrait_mb"] for s in samples), default=0)
history["max_w2l_mb"] = max((s["wav2lip_mb"] for s in samples), default=0)
history["max_python_mb"] = max((s["python_mb"] for s in samples), default=after["python_mb"])

if last.get("result_path"):
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration,size",
         "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate",
         "-of", "json", last["result_path"]],
        capture_output=True, text=True, timeout=60,
    )
    history["ffprobe"] = json.loads(out.stdout)
    history["final_path"] = last["result_path"]

c = sqlite3.connect(str(BASE_DIR / "app" / "studio.db"))
history["project"] = c.execute(
    "SELECT status,audio_path,animated_path,lipsync_path,final_path FROM projects WHERE id=?", (pid,)
).fetchone()

LOG.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
print("ELAPSED", history["elapsed_s"], "MIN_FREE", history["min_free_gb"])
print("MAX_LP", history["max_lp_mb"], "MAX_W2L", history["max_w2l_mb"], "MAX_PY", history["max_python_mb"])
print("FINAL", history.get("final_path"))
print("WROTE", LOG)
