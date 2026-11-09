"""Configuración del backend cloud (todo por variables de entorno)."""
from __future__ import annotations

import os
from pathlib import Path


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


BASE_DIR = Path(__file__).resolve().parents[2]
_load_env_file(BASE_DIR / ".env")
_load_env_file(BASE_DIR / "CLOUD_ENV")  # opcional, específico de cloud


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


class CloudSettings:
    BASE_DIR: Path = BASE_DIR
    HOST: str = os.environ.get("CLOUD_HOST", "0.0.0.0")
    PORT: int = _int("CLOUD_PORT", 8002)
    MODE: str = os.environ.get("CLOUD_MODE", "FREE_CLOUD").upper()  # FREE_CLOUD | CLOUD_GPU
    ALLOW_PAID: bool = os.environ.get("ALLOW_PAID", "").strip().lower() in ("1", "true", "yes", "si")
    API_TOKEN: str = os.environ.get("CLOUD_API_TOKEN", "")
    INFERENCE_URL: str = os.environ.get("INFERENCE_URL", "")  # URL del Space ZeroGPU
    FISH_AUDIO_API_KEY: str = os.environ.get("FISH_AUDIO_API_KEY", "")
    FISH_AUDIO_REFERENCE_ID: str = os.environ.get("FISH_AUDIO_REFERENCE_ID", "")
    MAX_UPLOAD_MB: int = _int("CLOUD_MAX_UPLOAD_MB", 30)
    MAX_JOB_SECONDS: int = _int("CLOUD_MAX_JOB_SECONDS", 1800)
    MAX_DAILY_JOBS: int = _int("CLOUD_MAX_DAILY_JOBS", 10)
    MAX_VIDEO_MB: int = _int("CLOUD_MAX_VIDEO_MB", 200)
    DATA_DIR: Path = Path(os.environ.get("CLOUD_DATA_DIR", str(BASE_DIR / "cloud" / "data")))
    DB_PATH: Path = DATA_DIR / "cloud.db"
    STORAGE_DIR: Path = Path(os.environ.get("CLOUD_STORAGE_DIR", str(BASE_DIR / "cloud" / "storage")))

    # S3-compatible (opcional)
    S3_ENDPOINT: str = os.environ.get("S3_ENDPOINT", "")
    S3_BUCKET: str = os.environ.get("S3_BUCKET", "")
    S3_ACCESS_KEY: str = os.environ.get("S3_ACCESS_KEY", "")
    S3_SECRET_KEY: str = os.environ.get("S3_SECRET_KEY", "")

    @classmethod
    def check_mode(cls) -> None:
        """Guarda anti-facturación: pago solo si ALLOW_PAID=1 explícito."""
        if cls.MODE == "CLOUD_GPU" and not cls.ALLOW_PAID:
            raise ValueError(
                "CLOUD_GPU requiere ALLOW_PAID=1 explícito. Sin eso se fuerza FREE_CLOUD."
            )

    @classmethod
    def effective_mode(cls) -> str:
        if cls.MODE == "CLOUD_GPU" and cls.ALLOW_PAID:
            return "CLOUD_GPU"
        return "FREE_CLOUD"


settings = CloudSettings()
