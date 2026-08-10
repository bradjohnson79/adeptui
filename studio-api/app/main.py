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
from .routers.operator import router as operator_router
from .master_sheet import router as master_sheet_router, ensure_master_sheet_tables
from .avatar_studio import router as avatar_studio_router, ensure_avatar_tables
from .editor_sequences import router as editor_sequences_router, ensure_editor_tables
from .knowledgebase_api import router as knowledgebase_router
from .references.api import router as references_router
from .director_references.api import router as director_references_router
from .capabilities.api import router as capabilities_router
from .codirector.routers.knowledge import router as knowledge_cards_router
from .codirector.routers.diagnostics import router as diagnostics_router
from .codirector.vision.router import router as vision_router
from .codirector.vision.engine import set_engine_enabled
from .posecraft.router import router as posecraft_router

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
        from .codirector.m28.db import ensure_m28_tables

        ensure_m28_tables()
    except Exception:
        logger.exception("M2.8 table ensure failed")
    try:
        from .codirector.m29.db import ensure_m29_tables

        ensure_m29_tables()
    except Exception:
        logger.exception("M2.9 table ensure failed")
    try:
        from .codirector.m211.db import ensure_m211_tables

        ensure_m211_tables()
    except Exception:
        logger.exception("M2.11 table ensure failed")
    try:
        from .codirector.m212.db import ensure_m212_tables

        ensure_m212_tables()
    except Exception:
        logger.exception("M2.12 table ensure failed")
    try:
        from .codirector.m213.db import ensure_m213_tables

        ensure_m213_tables()
    except Exception:
        logger.exception("M2.13 table ensure failed")
    try:
        from .codirector.m214.db import ensure_m214_tables

        ensure_m214_tables()
    except Exception:
        logger.exception("M2.14 table ensure failed")
    try:
        from .templates_presets.db import ensure_m31a_tables

        ensure_m31a_tables()
    except Exception:
        logger.exception("M3.1a templates/presets table ensure failed")
    try:
        ensure_master_sheet_tables()
    except Exception:
        pass
    try:
        ensure_avatar_tables()
    except Exception:
        pass
    try:
        from .character_identity import ensure_character_identity_tables

        ensure_character_identity_tables()
    except Exception:
        logger.exception("M3.3 character identity table ensure failed")
    try:
        from .project_security.service import ensure_tables as ensure_project_security_tables

        ensure_project_security_tables()
    except Exception:
        logger.exception("Project security table ensure failed")
    try:
        from .voice_performance import ensure_tables as ensure_voice_performance_tables

        ensure_voice_performance_tables()
    except Exception:
        logger.exception("Voice Performance table ensure failed")
    try:
        from .voice_environment import ensure_tables as ensure_voice_environment_tables

        ensure_voice_environment_tables()
    except Exception:
        logger.exception("Voice Environment table ensure failed")
    try:
        from .spatial_map import ensure_tables as ensure_spatial_map_tables

        ensure_spatial_map_tables()
    except Exception:
        logger.exception("Spatial Map table ensure failed")
    try:
        from .audio_studio import ensure_tables as ensure_audio_studio_tables

        ensure_audio_studio_tables()
    except Exception:
        logger.exception("Audio Studio table ensure failed")
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
    # Render jobs read the fal credential from the secret store only, so a key that lives
    # in .env has to be promoted before the queue starts consuming jobs.
    from .fal_env_bridge import bridge_fal_key_at_startup

    await bridge_fal_key_at_startup()
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
    try:
        job_recovery = await job_queue.recover_interrupted()
        if job_recovery.get("resumed") or job_recovery.get("interrupted"):
            logger.warning(
                "Studio job queue recovery resumed=%s interrupted=%s",
                len(job_recovery.get("resumed") or []),
                len(job_recovery.get("interrupted") or []),
            )
    except Exception:
        logger.exception("Studio job queue recovery failed")
    job_queue.start()

    exec_worker_started = False
    try:
        from .feature_flags import refresh_feature_flags
        from .codirector.executive.worker import production_worker

        flags = refresh_feature_flags()
        if flags.production_executive_v1:
            # Configurable poll via STUDIO_PRODUCTION_EXECUTIVE_POLL_INTERVAL
            production_worker.poll_interval = float(
                __import__("os").environ.get("STUDIO_PRODUCTION_EXECUTIVE_POLL_INTERVAL", production_worker.poll_interval)
                or production_worker.poll_interval
            )
            production_worker.start()  # recover_running_jobs inside start
            exec_worker_started = True
            logger.info("Production Executive worker started (single-process)")
    except Exception:
        logger.exception("Production Executive worker failed to start")

    yield

    if exec_worker_started:
        try:
            from .codirector.executive.worker import production_worker
            production_worker.stop()
        except Exception:
            logger.exception("Production Executive worker stop failed")


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
try:
    from .project_security.middleware import ProjectPasswordLockMiddleware

    app.add_middleware(ProjectPasswordLockMiddleware)
except Exception:
    logger.exception("Project password lock middleware failed to load")


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
app.include_router(operator_router, prefix="/api")
try:
    from .scriptwriter.api import router as scriptwriter_router

    app.include_router(scriptwriter_router, prefix="/api")
except Exception:
    logger.exception("Scriptwriter M4.7 router failed to load")
try:
    from .docker_runtime.api import router as docker_runtime_router

    app.include_router(docker_runtime_router, prefix="/api")
except Exception:
    logger.exception("Docker Runtime W47 router failed to load")
try:
    from .project_security.router import router as project_security_router

    app.include_router(project_security_router, prefix="/api")
except Exception:
    logger.exception("Project security router failed to load")
app.include_router(master_sheet_router, prefix="/api")
app.include_router(avatar_studio_router, prefix="/api")
app.include_router(editor_sequences_router, prefix="/api")
app.include_router(knowledgebase_router, prefix="/api")
app.include_router(references_router, prefix="/api")
app.include_router(director_references_router, prefix="/api")
app.include_router(capabilities_router, prefix="/api")
# PoseCraft production persistence router (already carries /api/posecraft prefix).
app.include_router(knowledge_cards_router, prefix="/api")
app.include_router(diagnostics_router, prefix="/api")
app.include_router(vision_router, prefix="/api")
# PoseCraft production persistence router (already carries /api/posecraft prefix).
app.include_router(posecraft_router)
try:
    from .runtime_beta import router as runtime_beta_router

    app.include_router(runtime_beta_router, prefix="/api")
except Exception:
    logger.exception("Beta runtime status router failed to load")
try:
    from .generation_tools.api import router as generation_tools_router

    app.include_router(generation_tools_router, prefix="/api")
except Exception:
    logger.exception("Generation Tools router failed to load")
try:
    from .video_runtime.api import router as video_runtime_router

    app.include_router(video_runtime_router, prefix="/api")
    try:
        from .minimax_h3.api import router as minimax_h3_router

        app.include_router(minimax_h3_router, prefix="/api")
    except Exception:
        logger.exception("MiniMax H3 router failed to load")
    try:
        from .image_runtime.api import router as image_runtime_router

        app.include_router(image_runtime_router, prefix="/api")
    except Exception:
        pass
    try:
        from .image_product.api import router as image_product_router

        app.include_router(image_product_router, prefix="/api")
        try:
            from .image_studio.api import router as image_studio_router

            app.include_router(image_studio_router, prefix="/api")
        except Exception as exc:  # pragma: no cover
            logger.warning("image_studio router unavailable: %s", exc)
        try:
            from .image_pipeline.api import router as image_pipeline_router

            app.include_router(image_pipeline_router, prefix="/api")
        except Exception as exc:  # pragma: no cover
            logger.warning("image_pipeline router unavailable: %s", exc)
        try:
            from .image_pipeline.multi_shot.api import router as multi_shot_router

            app.include_router(multi_shot_router, prefix="/api")
        except Exception as exc:  # pragma: no cover
            logger.warning("multi_shot router unavailable: %s", exc)
        try:
            from .environment_reference_sheet.api import router as ers_router

            app.include_router(ers_router, prefix="/api")
        except Exception as exc:  # pragma: no cover
            logger.warning("environment_reference_sheet router unavailable: %s", exc)
        try:
            from .storyboard_studio.api import router as storyboard_studio_router

            app.include_router(storyboard_studio_router, prefix="/api")
        except Exception as exc:  # pragma: no cover
            logger.warning("storyboard_studio router unavailable: %s", exc)
    except Exception:
        logger.exception("Image Product router failed to load")
    try:
        from .magi.api import router as magi_router

        app.include_router(magi_router)
    except Exception:
        logger.exception("MAGI Editor router failed to load")

except Exception:
    logger.exception("Video Runtime router failed to load")
try:
    from .spatial_map.router import router as spatial_map_router

    app.include_router(spatial_map_router, prefix="/api")
except Exception as exc:  # pragma: no cover
    logger.warning("spatial_map router unavailable: %s", exc)
try:
    from .templates_presets.api import router as templates_presets_router

    app.include_router(templates_presets_router, prefix="/api")
except Exception:
    logger.exception("Templates/Presets router failed to load")
try:
    from .character_identity.api import router as character_identity_router

    app.include_router(character_identity_router, prefix="/api")
except Exception:
    logger.exception("Character Identity router failed to load")
try:
    from .continuity import models as _continuity_models  # noqa: F401 — register ORM
    from .continuity.router import router as continuity_router

    app.include_router(continuity_router, prefix="/api")
except Exception:
    logger.exception("Continuity (Wave 5) router failed to load")
try:
    from .scene_references import models as _scene_ref_models  # noqa: F401 — register ORM
    from .scene_references.router import router as scene_references_router

    app.include_router(scene_references_router, prefix="/api")
except Exception:
    logger.exception("Scene References (Wave 6P) router failed to load")
try:
    from .m42_wave6p.router import router as m42_wave6p_router

    app.include_router(m42_wave6p_router, prefix="/api")
except Exception:
    logger.exception("M42 Wave 6P gate router failed to load")
try:
    from .m42_w43.router import router as m42_w43_router

    app.include_router(m42_w43_router, prefix="/api")
except Exception:
    logger.exception("M42 W43 Character Creator gate router failed to load")
try:
    from .voice_performance.router import router as voice_performance_router

    app.include_router(voice_performance_router, prefix="/api")
except Exception:
    logger.exception("M42 W44 Voice Performance router failed to load")
try:
    from .voice_environment.router import router as voice_environment_router

    app.include_router(voice_environment_router, prefix="/api")
except Exception:
    logger.exception("M5.2 Voice Environment router failed to load")
try:
    from .audio_studio.router import router as audio_studio_router

    app.include_router(audio_studio_router, prefix="/api")
except Exception:
    logger.exception("M42 W45 Audio Studio router failed to load")
try:
    from .director_timeline_w46.router import router as director_timeline_w46_router

    app.include_router(director_timeline_w46_router, prefix="/api")
except Exception:
    logger.exception("M42 W46 Director Timeline Master router failed to load")
try:
    from .hosted_providers.router import router as hosted_providers_router

    app.include_router(hosted_providers_router, prefix="/api")
except Exception:
    logger.exception("Hosted AI Providers router failed to load")
try:
    from .model_storage.router import router as model_storage_router

    app.include_router(model_storage_router, prefix="/api")
except Exception:
    logger.exception("Model Storage router failed to load")
try:
    from .timeline_retakes.router import router as timeline_retakes_router

    app.include_router(timeline_retakes_router, prefix="/api")
except Exception:
    logger.exception("Timeline retakes router failed to load")
try:
    from .provider_usage.router import router as provider_usage_router

    app.include_router(provider_usage_router, prefix="/api")
except Exception:
    logger.exception("Provider usage router failed to load")
try:
    from .production_control import ensure_production_control, router as production_control_router

    ensure_production_control()
    app.include_router(production_control_router, prefix="/api")
    # Wire Vision Validation engine with feature flag
    from .feature_flags import feature_flags
    from .codirector.vision.engine import set_engine_enabled
    set_engine_enabled(feature_flags.vision_validation_v1)
except Exception:
    logger.exception("Production Control Dock router failed to load")
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
try:
    from .source_manager.install_jobs.router import router as install_jobs_router

    app.include_router(install_jobs_router, prefix="/api")
except Exception:
    logger.exception("Install jobs router failed to load")
try:
    from .setup.lifecycle.router import router as setup_lifecycle_router

    app.include_router(setup_lifecycle_router, prefix="/api")
except Exception:
    logger.exception("Setup lifecycle router failed to load")

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
    from fastapi import HTTPException

    from .db import SessionLocal, Asset

    db = SessionLocal()
    try:
        asset = db.get(Asset, asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail={"error": "ASSET_NOT_FOUND", "assetId": asset_id})
        if not asset.path:
            raise HTTPException(status_code=404, detail={"error": "ASSET_FILE_MISSING", "assetId": asset_id, "reason": "Asset record exists but file path is not set."})
        p = Path(asset.path)
        if not p.exists() or not p.is_file():
            raise HTTPException(status_code=404, detail={"error": "ASSET_FILE_MISSING", "assetId": asset_id, "path": str(p), "reason": "Backing file does not exist on disk."})
        return FileResponse(p)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": "ASSET_STORAGE_ERROR", "assetId": asset_id, "type": type(exc).__name__, "message": str(exc)[:200]})
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

