"""Start DBOS once per process. The system database is not project truth."""

from __future__ import annotations

import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ...config import settings

_LOCK = threading.Lock()
_STARTED = False
_BOOT = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cd-dbos-boot")


def system_database_url() -> str:
    override = os.environ.get("ADEPT_DBOS_SYSTEM_DATABASE_URL", "").strip()
    if override:
        if override.startswith("sqlite:///"):
            Path(override.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        return override
    path = settings.data_dir / "dbos" / "codirector.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + path.resolve().as_posix()


def _boot_sync() -> None:
    global _STARTED
    with _LOCK:
        if _STARTED:
            return
        from dbos import DBOS

        DBOS(
            config={
                "name": "adept_codirector",
                "system_database_url": system_database_url(),
            }
        )
        # Import after DBOS() so workflow and tool steps register on this instance.
        from . import workflow as _workflow
        from .approval import register_approval_workflow

        _ = _workflow.agent
        register_approval_workflow()
        # launch() opens the system database and starts the queue listener.
        # register_queue persists the queue; the listener picks it up after launch.
        DBOS.launch()
        DBOS.register_queue(
            "adept_cd_mutations",
            partition_concurrency=1,
            polling_interval_sec=0.2,
        )
        _STARTED = True


def ensure_started() -> None:
    if _STARTED:
        return
    try:
        asyncio.get_running_loop()
        running = True
    except RuntimeError:
        running = False
    if running:
        # DBOS queue registration is synchronous and refuses a running loop.
        _BOOT.submit(_boot_sync).result()
        return
    _boot_sync()
