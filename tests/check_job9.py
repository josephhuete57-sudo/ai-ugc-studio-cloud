import sqlite3

import requests

j = requests.get("http://127.0.0.1:8001/api/jobs/9", timeout=30).json()
log = (j.get("log") or "").encode("ascii", "replace").decode()
print(log[-2500:])
c = sqlite3.connect(r"C:\AI_UGC_STUDIO\app\studio.db")
p = c.execute(
    "SELECT status,audio_path,animated_path,lipsync_path,final_path FROM projects WHERE id=1"
).fetchone()
print("PROJECT", p)
print("GENS", c.execute("SELECT type,path FROM generations WHERE project_id=1 ORDER BY id").fetchall())
