"""Configuración central de AI UGC STUDIO (CPU-first, sin secretos al frontend)."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]  # C:\AI_UGC_STUDIO


def _load_env_file(env_path: Path) -> None:
    """Lee el .env sin dependencias externas; nunca imprime valores."""
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(BASE_DIR / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


class Settings:
    BASE_DIR: Path = BASE_DIR
    HOST: str = os.environ.get("APP_HOST", "127.0.0.1")
    PORT: int = _int("APP_PORT", 8000)

    # Video
    VIDEO_WIDTH: int = _int("VIDEO_WIDTH", 720)
    VIDEO_HEIGHT: int = _int("VIDEO_HEIGHT", 1280)
    VIDEO_FPS: int = _int("VIDEO_FPS", 24)

    # Fish Audio (solo servidor; nunca se expone al frontend)
    FISH_AUDIO_API_KEY: str = os.environ.get("FISH_AUDIO_API_KEY", "")
    FISH_AUDIO_REFERENCE_ID: str = os.environ.get("FISH_AUDIO_REFERENCE_ID", "")
    FISH_AUDIO_FORMAT: str = os.environ.get("FISH_AUDIO_FORMAT", "mp3")
    FISH_AUDIO_MODEL: str = os.environ.get("FISH_AUDIO_MODEL", "s2.1-pro")

    # Proveedor LLM opcional para guiones (OpenAI-compatible)
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    # Límites de subida
    MAX_UPLOAD_MB: int = _int("MAX_UPLOAD_MB", 25)
    ALLOWED_IMAGES = {".jpg", ".jpeg", ".png", ".webp"}
    ALLOWED_VIDEOS = {".mp4", ".mov", ".webm"}
    ALLOWED_AUDIOS = {".mp3", ".wav", ".m4a", ".ogg"}

    # Rutas
    LIVEPORTRAIT_DIR: Path = BASE_DIR / "LivePortrait"
    LIVEPORTRAIT_PYTHON: Path = LIVEPORTRAIT_DIR / ".venv" / "Scripts" / "python.exe"
    LIVEPORTRAIT_INFERENCE: Path = LIVEPORTRAIT_DIR / "inference.py"
    LIVEPORTRAIT_WEIGHTS: Path = LIVEPORTRAIT_DIR / "pretrained_weights" / "liveportrait"
    WAV2LIP_DIR: Path = BASE_DIR / "Wav2Lip"
    WAV2LIP_CHECKPOINTS: Path = WAV2LIP_DIR / "checkpoints"

    ASSETS_DIR: Path = BASE_DIR / "assets"
    INFLUENCERS_DIR: Path = ASSETS_DIR / "influencers"
    AUDIO_DIR: Path = ASSETS_DIR / "audio"
    MUSIC_DIR: Path = ASSETS_DIR / "music"
    PROJECTS_DIR: Path = BASE_DIR / "projects"
    EXPORTS_DIR: Path = BASE_DIR / "exports"
    LOGS_DIR: Path = BASE_DIR / "logs"
    FRONTEND_DIR: Path = BASE_DIR / "app" / "frontend"
    DB_PATH: Path = BASE_DIR / "app" / "studio.db"

    # Perfil de memoria CPU (LOW_RAM_12GB)
    PROFILE: str = os.environ.get("PROFILE", "LOW_RAM_12GB")
    CLOUD_INFERENCE_MODE: str = os.environ.get("CLOUD_INFERENCE_MODE", "local")  # local | kaggle
    CLOUD_WORKER_KEY: str = os.environ.get("CLOUD_WORKER_KEY", "")
    CPU_THREADS: int = _int("CPU_THREADS", 2)
    FFMPEG_THREADS: int = _int("FFMPEG_THREADS", 2)
    MIN_FREE_RAM_GB: float = float(os.environ.get("MIN_FREE_RAM_GB", "2.5"))
    LIVEPORTRAIT_SOURCE_MAX_DIM: int = _int("LIVEPORTRAIT_SOURCE_MAX_DIM", 512)
    WAV2LIP_FACE_DET_BATCH: int = _int("WAV2LIP_FACE_DET_BATCH", 1)
    WAV2LIP_BATCH: int = _int("WAV2LIP_BATCH", 2)
    WAV2LIP_RESIZE_FACTOR: int = _int("WAV2LIP_RESIZE_FACTOR", 2)

    # Fish (timeout) y LivePortrait (timeout largo CPU)
    FISH_TIMEOUT: int = _int("FISH_TIMEOUT", 180)
    LIVEPORTRAIT_TIMEOUT: int = _int("LIVEPORTRAIT_TIMEOUT", 1800)

    @classmethod
    def fish_configured(cls) -> bool:
        return bool(cls.FISH_AUDIO_API_KEY and cls.FISH_AUDIO_REFERENCE_ID)

    @classmethod
    def llm_configured(cls) -> bool:
        return bool(cls.OPENAI_API_KEY)


settings = Settings()
