from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db
from .queue_worker import job_queue
from .routers.api import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    job_queue.start()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")

# Serve local media for previews
media_root = settings.data_dir
media_root.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(media_root)), name="media")


@app.get("/")
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}


@app.get("/api/assets/{asset_id}/file")
def get_asset_file(asset_id: str):
    from .db import SessionLocal, Asset

    db = SessionLocal()
    try:
        asset = db.get(Asset, asset_id)
        if not asset:
            return {"error": "not found"}
        p = Path(asset.path)
        if not p.exists():
            return {"error": "missing"}
        return FileResponse(p)
    finally:
        db.close()


@app.get("/api/file")
def get_file(path: str):
    p = Path(path)
    if not p.exists() or not p.is_file():
        return {"error": "not found"}
    try:
        p.resolve().relative_to(settings.data_dir.resolve())
    except ValueError:
        return {"error": "forbidden"}
    return FileResponse(p)

