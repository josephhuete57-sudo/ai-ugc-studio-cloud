import json
import time
from pathlib import Path

import requests

B = "http://127.0.0.1:8001"
BASE = Path(r"C:\AI_UGC_STUDIO")
start = time.time()
LOG = BASE / "logs" / "ram_validation.json"


def sn():
    return requests.get(f"{B}/api/system/memory", timeout=30).json()


before = sn()
print("BEFORE free", before["free_gb"], "used", before["used_gb"], "load", before["load_percent"])
samples = []
last = None
while True:
    j = requests.get(f"{B}/api/jobs/14", timeout=30).json()
    last = j
    if j["status"] in ("done", "error", "cancelled"):
        break
    m = sn()
    samples.append({
        "t": round(time.time() - start, 1),
        "free_gb": m["free_gb"], "used_gb": m["used_gb"], "load_percent": m["load_percent"],
        "lp": m["liveportrait_mb"], "w2l": m["wav2lip_mb"], "py": m["python_mb"],
        "step": j["step"],
    })
    print(f"[{int(time.time()-start)}s] {j['status']} {j['step']} free={m['free_gb']}GB LP={m['liveportrait_mb']}MB W2L={m['wav2lip_mb']}MB", flush=True)
    time.sleep(45)

after = sn()
print("AFTER free", after["free_gb"], "used", after["used_gb"], "load", after["load_percent"])
hist = {
    "before": before,
    "after": after,
    "project_id": 4,
    "job": {"id": 14, "status": last["status"], "result_path": last.get("result_path"),
            "error": (last.get("error") or "")[:500]},
    "elapsed_s": round(time.time() - start, 1),
    "min_free_gb": min((s["free_gb"] for s in samples), default=after["free_gb"]),
    "max_lp_mb": max((s["lp"] for s in samples), default=0),
    "max_w2l_mb": max((s["w2l"] for s in samples), default=0),
    "max_py_mb": max((s["py"] for s in samples), default=after["python_mb"]),
    "samples": samples,
    "final_path": last.get("result_path"),
}
LOG.write_text(json.dumps(hist, indent=2, ensure_ascii=False), encoding="utf-8")
print("ELAPSED", hist["elapsed_s"], "MIN_FREE", hist["min_free_gb"], "MAX_LP", hist["max_lp_mb"], "MAX_W2L", hist["max_w2l_mb"])
print("FINAL", hist["final_path"])
