import re
from pathlib import Path

p = Path(r"C:\AI_UGC_STUDIO\app\frontend\js\app.js")
t = p.read_text(encoding="utf-8")
fixed, n = re.subn(r"assetUrl\(encodeURIComponent\(([^)]+)\)\}\"", r'assetUrl(encodeURIComponent(\1))}"', t)
p.write_text(fixed, encoding="utf-8")
print("FIXED", n)
