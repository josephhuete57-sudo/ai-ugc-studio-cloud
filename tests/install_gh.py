import io
import zipfile
from pathlib import Path

import requests

r = requests.get("https://api.github.com/repos/cli/cli/releases/latest", timeout=60)
assets = [a["name"] for a in r.json()["assets"]]
print("ASSETS", assets)
url = [a["browser_download_url"] for a in r.json()["assets"]
       if a["name"].endswith("windows_amd64.zip") or a["name"].endswith("windows_x86_64.zip")]
print("URL", url)
if url:
    data = requests.get(url[0], timeout=300, stream=True).content
    z = zipfile.ZipFile(io.BytesIO(data))
    z.extractall(r"C:\AI_UGC_STUDIO\tools")
    gh = [p for p in z.namelist() if p.endswith("bin/gh.exe")]
    print("FOUND", gh)
