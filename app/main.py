"""AI UGC STUDIO — FastAPI app."""
from __future__ import annotations

import logging
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core import database
from app.core.config import settings

# Los logs/ no viajan en git (checkout en Render sin esa carpeta): crearlos
# ANTES del FileHandler para no tumbar el arranque (exit 1 en Render).
settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.FileHandler(str(settings.LOGS_DIR / "studio.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("ai-ugc-studio")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    for d in (settings.ASSETS_DIR, settings.INFLUENCERS_DIR, settings.AUDIO_DIR,
              settings.MUSIC_DIR, settings.PROJECTS_DIR, settings.EXPORTS_DIR, settings.LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
    database.init_db()
    logger.info("AI UGC STUDIO listo en http://%s:%s", settings.HOST, settings.PORT)
    yield


app = FastAPI(title="AI UGC Studio", version="1.0.0", lifespan=lifespan)
# Frontend público en HF Static (*.static.hf.space) + desarrollo local.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://josjshid99-ai-ugc-studio-web.static.hf.space",
        "https://huggingface.co",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "*",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
def index():
    index_path = settings.FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path), media_type="text/html")
    return {"status": "ok", "app": "AI UGC STUDIO"}


app.mount("/frontend", StaticFiles(directory=str(settings.FRONTEND_DIR)), name="frontend")


if __name__ == "__main__":
    import uvicorn

    try:
        webbrowser.open(f"http://{settings.HOST}:{settings.PORT}")
    except Exception:
        pass
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT)
