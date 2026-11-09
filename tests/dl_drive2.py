import html
import os
import re

import requests

FILE_ID = "15G3U08c8xsCkOqQxE38Z2XXDnPcOptNk"
DEST = r"C:\AI_UGC_STUDIO\Wav2Lip\checkpoints\wav2lip_gan.pth"

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0"})
r = s.get(f"https://drive.google.com/uc?export=download&id={FILE_ID}", timeout=60)
t = r.text
fields = dict(re.findall(r'name="(id|export|confirm|uuid)" value="([^"]*)"', t))
print("FIELDS", fields)
action = re.search(r'<form id="download-form" action="([^"]+)"', t)
base = html.unescape(action.group(1)) if action else "https://drive.usercontent.google.com/download"
url = base + "?" + "&".join(f"{k}={v}" for k, v in fields.items())
print("URL", url[:250])
r2 = s.get(url, timeout=900, stream=True)
print("R2", r2.status_code, r2.headers.get("content-type"), r2.headers.get("content-length"))
assert r2.status_code == 200 and not r2.headers.get("content-type", "").startswith("text/html"), "Descarga no binaria"
with open(DEST, "wb") as f:
    for ch in r2.iter_content(1024 * 1024):
        f.write(ch)
print("SAVED", os.path.getsize(DEST))
print("MAGIC", open(DEST, "rb").read(4))
