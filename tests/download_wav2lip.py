"""Descarga pesos oficiales Wav2Lip (Drive confirm-token flow) y s3fd. Solo fuentes oficiales del README."""
import html
import re
import requests
from pathlib import Path

WAV = Path(r"C:\AI_UGC_STUDIO\Wav2Lip")
CKPT = WAV / "checkpoints"
SFD = WAV / "face_detection" / "detection" / "sfd"
CKPT.mkdir(parents=True, exist_ok=True)
SFD.mkdir(parents=True, exist_ok=True)

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0"})


def drive_download(file_id: str, dest: Path):
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    r = S.get(url, timeout=60, stream=True)
    ct = r.headers.get("content-type", "")
    if ct.startswith("text/html"):
        html = r.text
        m = re.search(r'name="confirm" value="([^"]+)"', html)
        uuid = re.search(r'name="uuid" value="([^"]+)"', html)
        action = re.search(r'<form id="download-form" action="([^"]+)"', html)
        if action:
            dl_url = html.unescape(action.group(1))
            print("ACTION:", dl_url[:200])
            r2 = S.get(dl_url, timeout=600, stream=True)
            print("ACTION_STATUS:", r2.status_code, r2.headers.get("content-type"), r2.headers.get("content-length"))
            if r2.status_code != 200 or not r2.headers.get("content-type", "").startswith("application/"):
                Path(r"C:\AI_UGC_STUDIO\logs\drive_action_debug.txt").write_text(
                    (r2.text[:2000] if "text" in r2.headers.get("content-type", "") else ""), encoding="utf-8", errors="ignore")
            r2.raise_for_status()
            ct2 = r2.headers.get("content-type", "")
            if ct2.startswith("text/html"):
                # segundo salto de confirmación: buscar otro form
                html2 = r2.text
                action2 = re.search(r'<form id="download-form" action="([^"]+)"', html2)
                if not action2:
                    m2 = re.search(r'name="confirm" value="([^"]+)"', html2)
                    if m2:
                        r2 = S.get(url + f"&confirm={m2.group(1)}", timeout=900, stream=True)
                    else:
                        raise SystemExit("Doble confirmación sin token.")
                else:
                    r2 = S.get(html.unescape(action2.group(1)), timeout=900, stream=True)
            with open(dest, "wb") as f:
                for chunk in r2.iter_content(1024 * 1024):
                    f.write(chunk)
            print("OK via form action:", dest, dest.stat().st_size)
            return
        if m:
            token = m.group(1)
            url2 = url + f"&confirm={token}"
            if uuid:
                url2 += f"&uuid={uuid.group(1)}"
            r3 = S.get(url2, timeout=900, stream=True)
            with open(dest, "wb") as f:
                for chunk in r3.iter_content(1024 * 1024):
                    f.write(chunk)
            print("OK via token:", dest, dest.stat().st_size)
            return
        Path(r"C:\AI_UGC_STUDIO\logs\drive_debug.html").write_text(html[:3000], encoding="utf-8", errors="ignore")
        raise SystemExit(f"No confirm token found for {file_id}; debug saved.")
    else:
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                f.write(chunk)
        print("OK direct:", dest, dest.stat().st_size)


def dl(url: str, dest: Path):
    r = S.get(url, timeout=900, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1024 * 1024):
            f.write(chunk)
    print("OK:", dest, dest.stat().st_size)


# s3fd (face detection) - enlace oficial del README
dl("https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth", SFD / "s3fd.pth")

# Wav2Lip + GAN - ids de Google Drive del README oficial
dl_gan = CKPT / "wav2lip_gan.pth"
if not (dl_gan.exists() and dl_gan.stat().st_size > 10_000_000):
    drive_download("15G3U08c8xsCkOqQxE38Z2XXDnPcOptNk", dl_gan)

for p in (SFD / "s3fd.pth", dl_gan):
    b = Path(p).open("rb").read(4) if Path(p).exists() else b""
    print("FILE", p, "size", Path(p).stat().st_size if Path(p).exists() else 0, "magic", b)
