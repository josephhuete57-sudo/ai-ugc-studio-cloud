import re

import requests

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0"})
r = s.get(
    "https://drive.google.com/uc?export=download&id=15G3U08c8xsCkOqQxE38Z2XXDnPcOptNk",
    timeout=60,
)
t = r.text
i = t.find("download-form")
print("FORM_CTX:", t[i - 100 : i + 600] if i >= 0 else "NO FORM")
print("---HIDDEN---")
for m in re.finditer(r'<input[^>]+name="(confirm|uuid|id|export)"[^>]*>', t):
    print(m.group(0)[:300])
print("---LINKS---")
for m in re.finditer(r'href="([^"]*confirm[^"]*)"', t):
    print(m.group(1)[:400])
