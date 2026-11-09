"""Pruebas automatizadas de AI UGC STUDIO (unittest, sin dependencias extra).

Uso: .venv\\Scripts\\python.exe -m unittest tests.test_studio -v
Requiere el backend en http://127.0.0.1:8001 (o BASE_URL).
"""
import os
import time
import unittest
from pathlib import Path

import requests

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8001")
BASE_DIR = Path(__file__).resolve().parents[1]
PHOTO = BASE_DIR / "LivePortrait" / "assets" / "examples" / "source" / "s0.jpg"


class TestStudio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = requests.get(f"{BASE}/api/health", timeout=10)
        assert r.ok, "Backend no responde"
        cls.influencer_photo = None
        cls.project_id = None

    def test_01_health(self):
        self.assertEqual(requests.get(f"{BASE}/api/health", timeout=10).json()["status"], "ok")

    def test_02_engines(self):
        e = requests.get(f"{BASE}/api/engines", timeout=60).json()
        self.assertTrue(e["liveportrait"]["available"], e["liveportrait"])
        self.assertTrue(e["ffmpeg"]["available"])
        self.assertTrue(e["wav2lip"]["available"], e["wav2lip"])  # pesos convertidos a CPU
        self.assertTrue(e["local_tts"]["available"])

    def test_03_config_sin_secretos(self):
        c = requests.get(f"{BASE}/api/config", timeout=10).json()
        self.assertIn("fish_configured", c)
        self.assertNotIn("api_key", str(c).lower())

    def test_04_upload_y_crear_influencer(self):
        assert PHOTO.exists(), f"Falta foto de ejemplo: {PHOTO}"
        with PHOTO.open("rb") as f:
            r = requests.post(f"{BASE}/api/influencers/upload",
                              files={"photo": ("s0.jpg", f, "image/jpeg")}, timeout=60)
        self.assertTrue(r.ok, r.text[:300])
        photo_path = r.json()["path"]
        r2 = requests.post(f"{BASE}/api/influencers",
                           json={"name": "Test UGC", "photo_path": photo_path}, timeout=30)
        self.assertTrue(r2.ok, r2.text[:300])
        type(self).influencer_photo = photo_path
        lst = requests.get(f"{BASE}/api/influencers", timeout=30).json()
        self.assertTrue(any(x["photo_path"] == photo_path for x in lst))

    def test_05_guiones(self):
        r = requests.post(f"{BASE}/api/scripts/generate",
                          json={"product": "protector solar", "campaign": "acabado invisible"}, timeout=30)
        self.assertTrue(r.ok, r.text[:300])
        data = r.json()
        self.assertEqual(len(data["variantes"]), 3)
        for v in data["variantes"]:
            self.assertTrue(v["guion"] and v["duracion_segundos"] > 0)

    def test_06_proyecto_persistencia(self):
        r = requests.post(f"{BASE}/api/projects",
                          json={"name": "Proyecto Tests", "product": "protector solar",
                                "script": "Prueba de persistencia del studio."}, timeout=30)
        self.assertTrue(r.ok, r.text[:300])
        pid = r.json()["id"]
        type(self).project_id = pid
        r2 = requests.get(f"{BASE}/api/projects/{pid}", timeout=30)
        self.assertEqual(r2.json()["name"], "Proyecto Tests")

    def test_07_preview_ffmpeg(self):
        r = requests.post(f"{BASE}/api/editor/preview",
                          json={"image_path": str(PHOTO)}, timeout=30)
        self.assertTrue(r.ok, r.text[:300])
        jid = r.json()["job_id"]
        deadline = time.time() + 900  # la cola es de 1 worker CPU: puede haber una animación delante
        while time.time() < deadline:
            j = requests.get(f"{BASE}/api/jobs/{jid}", timeout=30).json()
            if j["status"] in ("done", "error", "cancelled"):
                break
            time.sleep(3)
        self.assertEqual(j["status"], "done", j.get("error"))
        self.assertTrue(Path(j["result_path"]).exists())
        self.assertTrue(j["result_path"].endswith(".mp4"))

    def test_08_voz_local(self):
        r = requests.post(f"{BASE}/api/voice/generate",
                          json={"text": "Prueba de voz local.", "provider": "local"}, timeout=120)
        self.assertTrue(r.ok, r.text[:300])
        self.assertTrue(r.json()["path"].endswith(".wav"))

    def test_09_lipsync_encola_trabajo(self):
        r = requests.post(f"{BASE}/api/lipsync/run",
                          json={"face_path": str(PHOTO),
                                "audio_path": str(BASE_DIR / "assets" / "audio" / "prueba_tono.wav")}, timeout=30)
        self.assertIn(r.status_code, (200, 409))  # 200: pesos listos; 409: pendiente sin pesos
        if r.status_code == 200:
            self.assertIn("job_id", r.json())

    def test_10_rechazo_ext_no_permitida(self):
        r = requests.post(f"{BASE}/api/influencers/upload",
                          files={"photo": ("evil.exe", b"MZ", "application/octet-stream")}, timeout=30)
        self.assertIn(r.status_code, (400, 413, 422))

    def test_11_monitor_ram(self):
        r = requests.get(f"{BASE}/api/system/memory", timeout=30)
        self.assertTrue(r.ok, r.text[:200])
        m = r.json()
        self.assertEqual(m["profile"], "LOW_RAM_12GB")
        self.assertGreater(m["total_gb"], 10)
        self.assertIn(m["level"], ("normal", "elevada", "critica"))


if __name__ == "__main__":
    unittest.main()
