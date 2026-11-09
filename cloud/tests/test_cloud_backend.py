"""Pruebas del backend cloud (auth, upload, trabajos, descarga, cuotas/modo)."""
import os
import time

import requests

B = "http://127.0.0.1:8002"
H = {"Authorization": "Bearer test-token-cloud-123"}
PHOTO = r"C:\AI_UGC_STUDIO\LivePortrait\assets\examples\source\s0.jpg"

def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name, extra)
    assert cond, name

# health + modo
r = requests.get(f"{B}/api/cloud/health", timeout=15)
check("health", r.ok and r.json()["mode"] == "FREE_CLOUD", r.text[:120])
r = requests.get(f"{B}/api/cloud/mode", headers=H, timeout=15)
check("mode", r.ok and r.json()["mode"] == "FREE_CLOUD" and r.json()["allow_paid"] is False, r.text[:160])

# auth: sin token -> 401 (ya verificado en plano; aquí con token mal)
r = requests.get(f"{B}/api/cloud/jobs", headers={"Authorization": "Bearer mal"}, timeout=15)
check("auth-malo-401", r.status_code == 401, r.text[:80])

# upload foto
with open(PHOTO, "rb") as f:
    r = requests.post(f"{B}/api/cloud/upload", headers=H, files={"file": ("s0.jpg", f, "image/jpeg")}, timeout=60)
check("upload", r.ok, r.text[:120])
photo_key = r.json()["key"]

# rechaza .exe
r = requests.post(f"{B}/api/cloud/upload", headers=H, files={"file": ("x.exe", b"MZ", "application/octet-stream")}, timeout=15)
check("upload-exe-400", r.status_code == 400, r.text[:80])

# crear trabajo (worker llamará al adaptador; sin INFERENCE_URL fallará limpio estado failed)
r = requests.post(
    f"{B}/api/cloud/jobs", headers=H,
    json={"photo_key": photo_key, "script": "Prueba cloud", "voice": "es-ES-ElviraNeural", "use_lipsync": False},
    timeout=30,
)
check("job-202", r.status_code == 202, r.text[:150])
job_id = r.json()["id"]
time.sleep(3)
j = requests.get(f"{B}/api/cloud/jobs/{job_id}", headers=H, timeout=15).json()
check("job-estado", j["status"] in ("pending", "processing", "failed", "completed"), j["status"])
print("JOB:", j["id"], j["status"], (j.get("error") or "")[:120])

# descarga fichero con token en query
r = requests.get(f"{B}/api/cloud/files/{photo_key}", params={"token": "test-token-cloud-123"}, timeout=30)
check("download", r.ok and len(r.content) > 1000, str(len(r.content)))

print("ALL_CLOUD_TESTS_OK")
