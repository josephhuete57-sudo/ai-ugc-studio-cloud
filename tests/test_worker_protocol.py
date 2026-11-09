"""Prueba del protocolo backend<>worker (modo kaggle) sin GPU: claim->upload->result."""
import requests

B = "http://127.0.0.1:8003"
WK = {"X-Worker-Key": "test-worker-key"}

# 0) drena cola de pruebas anteriores (trabajos huérfanos)
while True:
    r = requests.get(f"{B}/api/cloud/worker/next", headers=WK, timeout=20)
    data = r.json()
    if not data.get("id"):
        break
    requests.post(f"{B}/api/cloud/worker/result", headers=WK,
                  json={"id": data["id"], "status": "failed", "error": "drain-test"}, timeout=20)
print("DRAINED")

# 1) crear influencer/proyecto y encolar animación remota
r = requests.post(f"{B}/api/influencers", json={"name": "W", "photo_path": r"C:\AI_UGC_STUDIO\assets\influencers\s0.jpg"}, timeout=20)
inf = r.json()["id"]
r = requests.post(f"{B}/api/animation/run", json={
    "source_path": r"C:\AI_UGC_STUDIO\assets\influencers\s0.jpg",
    "driving_path": r"C:\AI_UGC_STUDIO\projects\driving_short15.mp4"}, timeout=20)
print("ENQUEUE", r.status_code, r.text[:200])
jid = r.json()["job_id"]

j = requests.get(f"{B}/api/jobs/{jid}", timeout=20).json()
print("JOB_QUEUED", j["status"], j.get("ext_id"))

# 2) worker pregunta sin clave -> 401
r = requests.get(f"{B}/api/cloud/worker/next", timeout=20)
print("NEXT_NOKEY", r.status_code)
assert r.status_code == 401

# 3) worker reclama
r = requests.get(f"{B}/api/cloud/worker/next", headers=WK, timeout=20)
print("NEXT", r.status_code, r.text[:300])
ext = r.json()
assert ext.get("id")

# 4) worker descarga un input
r = requests.get(f"{B}/api/cloud/worker/files", headers=WK,
                 params={"path": ext["payload"]["driving_path"]}, timeout=30)
print("DL", r.status_code, len(r.content))
assert r.ok and len(r.content) > 1000

# 5) worker sube resultado (mp4 ya generado por el editor local)
with open(r"C:\AI_UGC_STUDIO\exports\anuncio_1794251176.mp4", "rb") as f:
    r = requests.post(f"{B}/api/cloud/worker/upload", headers=WK,
                      files={"file": ("resultado.mp4", f)}, timeout=60)
print("UPLOAD", r.status_code, r.text[:150])
assert r.ok
path = r.json()["path"]

# 6) worker reporta result -> job completed y descarga OK
r = requests.post(f"{B}/api/cloud/worker/result", headers=WK,
                  json={"id": ext["id"], "status": "completed", "result_path": path}, timeout=20)
print("RESULT", r.status_code)
j = requests.get(f"{B}/api/jobs/{jid}", timeout=20).json()
print("JOB_DONE", j["status"], j.get("result_path"))
assert j["status"] == "completed" and j.get("result_path")
r = requests.get(f"{B}/api/assets", params={"path": path}, timeout=30)
print("ASSET_OK", r.ok, len(r.content))
assert r.ok and len(r.content) > 10000
print("PROTOCOL_OK")
