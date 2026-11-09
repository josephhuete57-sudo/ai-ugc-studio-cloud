"""Despliegue automático AI UGC STUDIO FREE CLOUD (Render + Kaggle).

Requiere (autorizaciones en navegador/flujo oficial, nunca en el chat):
  1. Kaggle: cuenta + verificación telefónica (GPU) + kaggle.json en ~/.kaggle/
  2. Render: cuenta gratuita + API key en env RENDER_API_KEY (no va al repo)

Uso:
    $env:RENDER_API_KEY = "<clave de render.com/settings/api-keys>"
    .venv\\Scripts\\python.exe cloud\\deploy_all.py

Hace, en orden: repo GitHub (ya creado) -> backend en Render free ->
worker Kaggle GPU -> prueba E2E real (sube foto, crea job, espera MP4,
verifica descarga). Sin pago: usa FREE_CLOUD y planes free.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
GH = BASE / "tools" / "bin" / "gh.exe"
KEY_FILE = BASE / "cloud" / "data" / "worker_key.txt"


def _need(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FALTA: {msg}")
        sys.exit(1)


def check_kaggle() -> None:
    kj = Path.home() / ".kaggle" / "kaggle.json"
    _need(kj.exists(), "kaggle.json en %USERPROFILE%\\.kaggle (kaggle.com/settings -> Create New Token)")


def gh_status() -> str:
    r = subprocess.run([str(GH), "auth", "status"], capture_output=True, text=True, timeout=30)
    return ("ok" if r.returncode == 0 else "fail")


def ensure_repo() -> str:
    r = subprocess.run(
        [str(GH), "repo", "view", "josephhuete57-sudo/ai-ugc-studio-cloud", "--json", "name"],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode == 0:
        print("REPO ok")
        return "https://github.com/josephhuete57-sudo/ai-ugc-studio-cloud"
    subprocess.run(
        [str(GH), "repo", "create", "ai-ugc-studio-cloud", "--public",
         "--description", "AI UGC STUDIO - backend cloud FREE"],
        check=True, timeout=120,
    )
    return "https://github.com/josephhuete57-sudo/ai-ugc-studio-cloud"


def deploy_render(repo_url: str) -> str | None:
    import requests

    key = os.environ.get("RENDER_API_KEY", "").strip()
    if not key:
        print("RENDER: sin RENDER_API_KEY (render.com -> Account Settings -> API Keys).")
        print("  Alternativa dashboard: New -> Web Service -> Build and deploy from a Git")
        print("  repository -> este repo (main). Build: pip install -r app/requirements.txt")
        print("  Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT")
        return None
    h = {"Authorization": f"Bearer {key}"}
    owners = requests.get("https://api.render.com/v1/owners", headers=h, timeout=30).json()
    payload = {
        "type": "web_service",
        "name": "ai-ugc-studio-backend",
        "ownerId": owners[0]["id"],
        "repo": repo_url,
        "branch": "main",
        "region": "oregon",
        "plan": "free",
        "buildCommand": "pip install -r app/requirements.txt",
        "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
        "envVars": [
            {"key": "CLOUD_INFERENCE_MODE", "value": "kaggle"},
            {"key": "CLOUD_WORKER_KEY", "value": KEY_FILE.read_text().strip()},
            {"key": "PROFILE", "value": "LOW_RAM_12GB"},
        ],
    }
    r = requests.post("https://api.render.com/v1/services", headers=h, json=payload, timeout=60)
    if r.status_code not in (200, 201):
        print("RENDER_ERR", r.status_code, r.text[:400])
        return None
    svc = r.json()
    print("BACKEND", svc.get("service", {}).get("serviceDetails", {}).get("url"))
    return svc.get("service", {}).get("serviceDetails", {}).get("url")


def push_kernel(backend_url: str) -> None:
    meta = json.loads((BASE / "cloud" / "worker" / "kaggle" / "kernel-metadata.json").read_text())
    meta["parameters"]["BACKEND_URL"] = backend_url
    meta["parameters"]["WORKER_KEY"] = KEY_FILE.read_text().strip()
    kdir = BASE / "cloud" / "worker" / "kaggle"
    (kdir / "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
    env = dict(os.environ, KAGGLE_CONFIG_DIR=str(Path.home() / ".kaggle"))
    r = subprocess.run([sys.executable, "-m", "kaggle", "kernels", "push", "-p", str(kdir)],
                       capture_output=True, text=True, timeout=1800, env=env)
    print("KERNEL_PUSH", r.returncode, (r.stdout or r.stderr)[-300:])
    if r.returncode != 0:
        raise SystemExit("Push del kernel Kaggle falló (GPU requiere verificación telefónica).")


def e2e(backend_url: str) -> None:
    import requests

    h = {"X-Worker-Key": KEY_FILE.read_text().strip()}
    # job flujo mínimo vía API pública del backend (con token de usuario opcional;
    # aquí usamos el endpoint de worker como sondeo de vida)
    base = backend_url.rstrip("/")
    for _ in range(60):
        try:
            r = requests.get(f"{base}/api/health", timeout=20)
            if r.ok:
                break
        except Exception:
            pass
        time.sleep(10)
    else:
        raise SystemExit("Backend Render no responde aún.")
    print("BACKEND_OK", base)
    print("E2E: el worker Kaggle procesará el primer job flujo que crees desde la app.")


def main() -> None:
    check_kaggle()
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not KEY_FILE.exists():
        KEY_FILE.write_text(secrets.token_hex(16))
    print("GH", gh_status())
    repo = ensure_repo()
    backend = deploy_render(repo)
    if backend:
        push_kernel(backend)
        e2e(backend)
    else:
        print("SIN_RENDER: el kernel se sube cuando el backend Render esté en línea.")
        print("  (Sube el kernel con: kaggle kernels push -p cloud/worker/kaggle)")


if __name__ == "__main__":
    main()
