"""PoseCraft control package adapter for image pipeline planning.

Phase 5: the live PoseCraft scene is the canonical source for creator-driven
multi-subject blocking. The fixture remains available as a test-only fallback;
production planning hydrates from the project-scoped PoseCraft document via
`load_posecraft_control_package_for_project`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import PoseCraftControlPackage


def _fixture_path() -> Path:
    return Path(__file__).resolve().parents[3] / "fixtures" / "posecraft_control_fixture.json"


def load_posecraft_control_package(
    existing_payload: dict[str, Any] | None = None,
    *,
    creator_modified: bool = False,
) -> PoseCraftControlPackage:
    if existing_payload:
        payload = dict(existing_payload)
        payload["creatorModified"] = bool(payload.get("creatorModified") or creator_modified)
        return PoseCraftControlPackage.model_validate(payload)

    payload = json.loads(_fixture_path().read_text(encoding="utf-8"))
    package = PoseCraftControlPackage.model_validate(payload)
    package.creatorModified = creator_modified
    if not package.honestyNote:
        package.honestyNote = "Loaded from the foundation fixture until a creator edits the staging controls."
    return package


def load_posecraft_control_package_for_project(
    project_id: str,
    db: Any,
    *,
    creator_modified: bool = False,
) -> PoseCraftControlPackage:
    """Build a live PoseCraftControlPackage from the project's persisted scene.

    Honesty label: "PoseCraft visual staging reference". Falls back to the
    fixture only when the project has no PoseCraft scene yet (empty project).
    """
    from ..posecraft import service as posecraft_service  # local import to avoid cycles

    try:
        doc = posecraft_service.load_scene(project_id, db)
    except Exception:  # noqa: BLE001
        return load_posecraft_control_package(creator_modified=creator_modified)

    scene = doc.currentScene
    has_scene = bool(scene.figures) or scene.revision > 1 or bool(scene.name)
    if not has_scene:
        return load_posecraft_control_package(creator_modified=creator_modified)

    package = PoseCraftControlPackage(
        source="posecraft-scene",
        fixtureName="",
        creatorModified=bool(scene.creatorModified or creator_modified),
        figures=[f.model_dump() for f in scene.figures],
        camera=scene.camera.model_dump(),
        masks=[p.model_dump() for p in scene.primitives],
        honestyNote="PoseCraft visual staging reference",
    )
    package.provenance.source = "posecraft-scene"
    package.provenance.note = "Live PoseCraft scene staging reference"
    return package
