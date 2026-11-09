import html
import os
import re

import requests

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0"})
r = s.get(
    "https://drive.google.com/uc?export=download&id=15G3U08c8xsCkOqQxE38Z2XXDnPcOptNk",
    timeout=60,
)
print("PAGE", r.status_code, r.headers.get("content-type"))
m = re.search(r'<form id="download-form" action="([^"]+)"', r.text)
print("FORM", bool(m))
if m:
    u = html.unescape(m.group(1))
    print("URL", u[:250])
    r2 = s.get(u, timeout=900, stream=True)
    print("R2", r2.status_code, r2.headers.get("content-type"), r2.headers.get("content-length"))
    if r2.status_code == 200 and not r2.headers.get("content-type", "").startswith("text/html"):
        dest = r"C:\AI_UGC_STUDIO\Wav2Lip\checkpoints\wav2lip_gan.pth"
        with open(dest, "wb") as f:
            for ch in r2.iter_content(1024 * 1024):
                f.write(ch)
        print("SAVED", os.path.getsize(dest))
