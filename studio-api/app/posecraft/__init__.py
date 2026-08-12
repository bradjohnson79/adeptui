"""PoseCraft production persistence — project-scoped scene API.

Contracts mirror the TypeScript PoseCraft v1.1 types so the UI and API agree
on one schema. No production PoseCraft state lives only in localStorage once
this API is wired; the UI hydrates from and persists to the project.
"""

from .schemas import (
    PoseCraftDocument,
    PoseCraftScene,
    PoseCraftRevision,
    PoseCraftRevisionRecord,
    PoseCraftExportPreview,
    POSECRAFT_SCHEMA_VERSION,
)
from .service import (
    PoseCraftError,
    load_scene,
    save_scene,
    list_revisions,
    save_revision,
    restore_revision,
    build_export_preview,
)

__all__ = [
    "PoseCraftDocument",
    "PoseCraftScene",
    "PoseCraftRevision",
    "PoseCraftRevisionRecord",
    "PoseCraftExportPreview",
    "POSECRAFT_SCHEMA_VERSION",
    "PoseCraftError",
    "load_scene",
    "save_scene",
    "list_revisions",
    "save_revision",
    "restore_revision",
    "build_export_preview",
]
