import asyncio
import logging
import sys
import threading
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .capabilities.errors import CapabilityError
from .capabilities.errors import status_code_for_error as capability_status_code
from .config import settings
from .db import init_db
from .queue_worker import job_queue
from .routers.api import router
from .routers.codirector import router as codirector_router
from .routers.extra import router as extra_router
from .master_sheet import router as master_sheet_router, ensure_master_sheet_tables
from .avatar_studio import router as avatar_studio_router, ensure_avatar_tables
from .editor_sequences import router as editor_sequences_router, ensure_editor_tables
from .knowledgebase_api import router as knowledgebase_router
from .references.api import router as references_router
from .capabilities.api import router as capabilities_router

logger = logging.getLogger(__name__)

_PREV_EXCEPT_HOOK = sys.excepthook
_PREV_THREAD_EXCEPT_HOOK = getattr(threading, "excepthook", None)


def _install_exception_hooks() -> None:
    """Log uncaught exceptions without terminating the process for setup failures."""

    def _excepthook(exc_type, exc, tb):  # noqa: ANN001
        logger.error(
            "Uncaught exception (process continues unless fatal):\n%s",
            "".join(traceback.format_exception(exc_type, exc, tb)),
        )
        # Preserve default behavior for BaseException subclasses that should exit
        # (e.g. KeyboardInterrupt / SystemExit) via the previous hook.
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            _PREV_EXCEPT_HOOK(exc_type, exc, tb)

    sys.excepthook = _excepthook

    if _PREV_THREAD_EXCEPT_HOOK is not None:
        def _thread_excepthook(args):  # noqa: ANN001
            logger.error(
                "Uncaught thread exception thread=%s op_hint=%s\n%s",
                getattr(args, "thread", None) and getattr(args.thread, "name", None),
                getattr(args, "thread", None) and getattr(args.thread, "name", None),
                "".join(
                    traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
                ),
            )
            # Do not re-raise — pack install threads must never kill the API.

        threading.excepthook = _thread_excepthook

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    if loop is not None:
        def _asyncio_handler(loop, context):  # noqa: ANN001
            message = context.get("message") or "Unhandled asyncio exception"
            exc = context.get("exception")
            if exc is not None:
                logger.error(
                    "Unhandled asyncio exception: %s\n%s",
                    message,
                    "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                )
            else:
                logger.error("Unhandled asyncio exception: %s context=%s", message, context)

        try:
            loop.set_exception_handler(_asyncio_handler)
        except Exception:  # noqa: BLE001
            pass


@asynccontextmanager
async def lifespan(_: FastAPI):
    _install_exception_hooks()
    init_db()
    try:
        ensure_master_sheet_tables()
    except Exception:
        pass
    try:
        ensure_avatar_tables()
    except Exception:
        pass
    try:
        ensure_editor_tables()
    except Exception:
        pass
    try:
        from .setup.operations import recover_stale_operations

        recovered = recover_stale_operations()
        if recovered:
            logger.warning("Recovered %s stale setup operation(s) after restart", len(recovered))
    except Exception:
        logger.exception("Setup operation recovery failed")
    try:
        from .source_manager.migration import ensure_migrated

        ensure_migrated()
    except Exception:
        logger.exception("Source Manager migration failed")
    try:
        from .source_manager.downloads.queue import get_queue_manager

        recovery = get_queue_manager().recover_interrupted()
        if recovery.get("interrupted"):
            logger.warning(
                "Download queue recovery interrupted=%s resumable=%s",
                len(recovery.get("interrupted") or []),
                len(recovery.get("resumable") or []),
            )
    except Exception:
        logger.exception("Download queue recovery failed")
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


@app.exception_handler(CapabilityError)
async def _capability_error_handler(_request, exc: CapabilityError):
    """Translate a service-layer capability failure into the structured error envelope.

    Same shape the Co-Director gateway already returns, so `studio-web/src/api.ts` surfaces
    `code`, `message`, and `recommendedAction` without any per-route handling.
    """
    return JSONResponse(
        status_code=capability_status_code(exc.code),
        content={"detail": exc.to_dict()},
    )


app.include_router(router, prefix="/api")
app.include_router(codirector_router, prefix="/api")
app.include_router(extra_router, prefix="/api")
app.include_router(master_sheet_router, prefix="/api")
app.include_router(avatar_studio_router, prefix="/api")
app.include_router(editor_sequences_router, prefix="/api")
app.include_router(knowledgebase_router, prefix="/api")
app.include_router(references_router, prefix="/api")
app.include_router(capabilities_router, prefix="/api")
try:
    from .source_manager.api import router as source_manager_router

    app.include_router(source_manager_router, prefix="/api")
except Exception:
    logger.exception("Source Manager router failed to load")
try:
    from .source_manager.downloads.api import router as downloads_router

    app.include_router(downloads_router, prefix="/api")
except Exception:
    logger.exception("Downloads router failed to load")

# Playwright / functional-audit control surface (disabled unless STUDIO_E2E=1).
import os as _os

if _os.environ.get("STUDIO_E2E", "").strip() in ("1", "true", "TRUE", "yes", "YES"):
    from .routers.e2e import router as e2e_router

    app.include_router(e2e_router, prefix="/api")


# Serve local media for previews
media_root = settings.data_dir
media_root.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(media_root)), name="media")


@app.get("/")
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}


@app.get("/health")
async def root_health():
    """Operator alias for `/api/health` (no secrets)."""
    from .routers.api import health as api_health

    return await api_health()


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

