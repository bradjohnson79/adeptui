"""Project-scoped persistence for world-intelligence policy and advisories.

Uses ProjectTraitRow so reload/reopen returns the same creator-facing state.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from .contracts import CoDirectorWorldIntelligencePolicy, WorldStatePacket

POLICY_CATEGORY = "world_intelligence_policy"
ADVISORY_CATEGORY = "world_intelligence_advisory"
POLICY_KEY = "default"


def load_policy(db: Session, project_id: str) -> CoDirectorWorldIntelligencePolicy:
    from ...spatial_map.ers_persistence import _load_trait_value

    raw = _load_trait_value(db, project_id=project_id, category=POLICY_CATEGORY, key=POLICY_KEY)
    if not raw:
        return CoDirectorWorldIntelligencePolicy()
    try:
        return CoDirectorWorldIntelligencePolicy.model_validate_json(raw)
    except Exception:
        return CoDirectorWorldIntelligencePolicy()


def save_policy(db: Session, project_id: str, policy: CoDirectorWorldIntelligencePolicy) -> None:
    from ...spatial_map.ers_persistence import _upsert_trait

    _upsert_trait(
        db,
        project_id=project_id,
        category=POLICY_CATEGORY,
        key=POLICY_KEY,
        value=policy.model_dump_json(),
        provenance="co_director_world_intelligence",
    )


def advisory_key(scene_id: str = "", asset_id: str = "") -> str:
    if scene_id:
        return f"scene:{scene_id}"
    if asset_id:
        return f"asset:{asset_id}"
    return "latest"


def save_advisory(
    db: Session,
    project_id: str,
    packet: WorldStatePacket,
    advisory_text: Optional[str],
    *,
    scene_id: str = "",
    asset_id: str = "",
) -> None:
    from ...spatial_map.ers_persistence import _upsert_trait

    payload = {
        "packet": packet.model_dump(mode="json"),
        "advisoryText": advisory_text,
        "sceneId": scene_id,
        "assetId": asset_id,
    }
    import json

    raw = json.dumps(payload, ensure_ascii=False)
    for key in {advisory_key(scene_id, asset_id), "latest"}:
        _upsert_trait(
            db,
            project_id=project_id,
            category=ADVISORY_CATEGORY,
            key=key,
            value=raw,
            provenance="co_director_world_intelligence",
        )


def load_advisory(
    db: Session,
    project_id: str,
    *,
    scene_id: str = "",
    asset_id: str = "",
) -> dict[str, Any] | None:
    from ...spatial_map.ers_persistence import _load_trait_value
    import json

    for key in (advisory_key(scene_id, asset_id), "latest"):
        raw = _load_trait_value(db, project_id=project_id, category=ADVISORY_CATEGORY, key=key)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None
