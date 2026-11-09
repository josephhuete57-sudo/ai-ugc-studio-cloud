import re

import requests

r = requests.get("https://huggingface.co/spaces/josjshid99/ai-ugc-studio-web", timeout=30)
print("PAGE", r.status_code, len(r.text))
m = re.findall(r"hf\.space[^\"]{0,80}", r.text)[:8]
print("HF_SUBS")
for x in m:
    print(" ", x)
m2 = re.findall(r"embed[^\"]{0,60}", r.text)[:5]
print("EMBEDS")
for x in m2:
    print(" ", x)
