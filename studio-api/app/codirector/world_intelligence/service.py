"""Co-Director World Intelligence Service.

Orchestrates JEPA world-state comparisons, integrates with Co-Director,
and provides creator-facing advisories.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from .compare import build_world_state_packet
from .contracts import (
    WORLD_INTELLIGENCE_MODEL_ID,
    CoDirectorWorldIntelligencePolicy,
    IntentionalChangeRecord,
    WorldStatePacket,
    WorldStateRecommendation,
    WorldStateSource,
)
from .hardware_profile import can_run_model, estimate_vram_gb
from .index import WorldStateIndex
from .persist import load_advisory, load_policy, save_advisory, save_policy
from .worker_client import cached_cuda_probe, compare_images, encode_image, health as worker_health

logger = logging.getLogger(__name__)

# ── Singleton state ───────────────────────────────────────────────────────

_index: Optional[WorldStateIndex] = None
_policy_cache: dict[str, CoDirectorWorldIntelligencePolicy] = {}


def _get_index() -> WorldStateIndex:
    global _index
    if _index is None:
        _index = WorldStateIndex()
    return _index


# ── Service API ───────────────────────────────────────────────────────────


def is_available(*, probe: bool = True) -> dict:
    """Check if world intelligence is ready for live inference.

    File presence alone is not live-ready. CUDA worker health must pass.
    Advisory reads use probe=False so Scene Creator never blocks on torch import.
    """
    try:
        from .paths import any_model_present

        installed = any_model_present()
        if not probe:
            cached = cached_cuda_probe()
            live = bool(cached and cached.get("ok") and installed)
            return {
                "available": live,
                "installed": installed,
                "modelId": None,
                "reason": None if live else (cached or {}).get("reason") or "NOT_PROBED",
            }
        h = worker_health()
        installed = bool(h.get("installed") or installed)
        live = bool(h.get("ok"))
        return {
            "available": live,
            "installed": installed,
            "modelId": h.get("modelId"),
            "reason": None if live else h.get("reason", "UNAVAILABLE"),
        }
    except Exception as exc:
        return {"available": False, "installed": False, "reason": str(exc)[:80]}


def get_policy(project_id: str, db: Optional[Session] = None) -> CoDirectorWorldIntelligencePolicy:
    """Load persisted policy when a DB session is provided. Cache is a warm hint only."""
    if db is not None:
        policy = load_policy(db, project_id)
        _policy_cache[project_id] = policy
        return policy
    if project_id in _policy_cache:
        return _policy_cache[project_id]
    _policy_cache[project_id] = CoDirectorWorldIntelligencePolicy()
    return _policy_cache[project_id]


def set_policy(
    project_id: str, policy: CoDirectorWorldIntelligencePolicy, db: Optional[Session] = None
) -> None:
    """Set the world intelligence policy for a project."""
    _policy_cache[project_id] = policy
    if db is not None:
        save_policy(db, project_id, policy)


def evaluate_generated_image(
    image_path: str,
    asset_id: str,
    reference_asset_ids: list[str],
    reference_image_paths: list[str],
    project_id: str = "",
    scene_id: str = "",
    intentional_change: bool = False,
    db: Optional[Session] = None,
) -> WorldStatePacket:
    """Evaluate a generated image against approved world references.

    This is the primary entry point for post-generation world-state review.
    """
    if not reference_asset_ids or not reference_image_paths:
        return WorldStatePacket(
            availability="insufficient_reference",
            reason="No approved world references available for comparison.",
        )

    # Persisted intentional marks must survive recycle — always load via db when present.
    policy = get_policy(project_id, db)
    if not intentional_change:
        for from_id, to_id in zip(reference_asset_ids, [asset_id] * len(reference_asset_ids)):
            if policy.is_change_intentional(from_id, to_id):
                intentional_change = True
                break

    # Compare against first reference (primary anchor)
    primary_ref_path = reference_image_paths[0]
    primary_ref_id = reference_asset_ids[0]

    try:
        packet = compare_images(
            image_a_path=primary_ref_path,
            image_b_path=image_path,
            asset_id_a=primary_ref_id,
            asset_id_b=asset_id,
            project_id=project_id,
            use_cache=True,
        )
    except RuntimeError as exc:
        reason = str(exc)
        if "MODEL_NOT_INSTALLED" in reason:
            return WorldStatePacket(
                availability="unavailable",
                reason="World intelligence model not installed.",
            )
        raise

    if intentional_change:
        packet.recommendation.consistent = True
        packet.recommendation.caution = ["Intended change — world revision accepted."]
        packet.recommendation.review_ = []
        packet.intentionalChange = IntentionalChangeRecord(
            fromAssetId=primary_ref_id,
            toAssetId=asset_id,
            projectId=project_id,
            sceneId=scene_id,
            label="Intended world change",
        )

    return packet


def compare_world_state(
    image_a_path: str,
    image_b_path: str,
    asset_id_a: Optional[str] = None,
    asset_id_b: Optional[str] = None,
) -> WorldStatePacket:
    """Compare two images and return a world-state packet."""
    return compare_images(
        image_a_path=image_a_path,
        image_b_path=image_b_path,
        asset_id_a=asset_id_a,
        asset_id_b=asset_id_b,
        use_cache=True,
    )


def mark_intentional_change(
    from_asset_id: str,
    to_asset_id: str,
    project_id: str,
    scene_id: str = "",
    label: str = "",
    creator_note: str = "",
    db: Optional[Session] = None,
) -> None:
    """Record an intentional world-state change to suppress false alarms."""
    policy = get_policy(project_id, db)
    record = IntentionalChangeRecord(
        fromAssetId=from_asset_id,
        toAssetId=to_asset_id,
        projectId=project_id,
        sceneId=scene_id,
        label=label,
        creatorNote=creator_note,
    )
    policy.intentionalChanges.append(record)
    set_policy(project_id, policy, db)


def get_supported_advisories() -> list[dict]:
    """Return the supported advisory templates for CD."""
    return [
        {
            "type": "world_consistent",
            "text": "Scene remains consistent with the approved environment.",
            "severity": "positive",
        },
        {
            "type": "minor_drift",
            "text": "Possible world continuity issue: the scene structure differs somewhat from the approved state.",
            "severity": "info",
        },
        {
            "type": "major_drift",
            "text": "Possible world continuity issue: the environment structure differs substantially from the approved scene state.",
            "severity": "warning",
        },
        {
            "type": "local_change_preserved",
            "text": "The edit preserved the environment well.",
            "severity": "positive",
        },
        {
            "type": "intentional_change_accepted",
            "text": "World revision accepted as intentional change.",
            "severity": "info",
        },
    ]


def world_consistency_text(packet: WorldStatePacket) -> Optional[str]:
    """Generate creator-safe text from a world-state packet."""
    if not packet.is_actionable():
        if packet.availability == "insufficient_reference":
            return None  # No signal to show
        return None

    if packet.intentionalChange:
        return "World revision accepted."

    rec = packet.recommendation
    if rec.consistent and not rec.caution and not rec.review_:
        return "World consistency looks strong."

    if rec.consistent and rec.caution:
        return "The scene remains in the established world with minor changes."

    if not rec.consistent and rec.review_:
        return rec.review_[0] if rec.review_ else "World-state review suggested."

    return None


def _attach_production_extras(
    packet: WorldStatePacket,
    db: Optional[Session],
    project_id: str,
    scene_id: str,
) -> WorldStatePacket:
    """Complement JEPA scores with Revision B spatial facts. Does not replace world-state-v1."""
    extras = dict(packet.extras or {})
    extras["complements"] = ["videochat3", "creation_perception"]
    extras["layer"] = "jepa"
    if db is None or not project_id:
        packet.extras = extras
        return packet
    try:
        from ...spatial_map.service import list_documents
        from ..perception.spatial_draft import load_spatial_draft

        docs = list_documents(db, project_id)
        map_id = str(getattr(docs[0], "id", "") or "") if docs else ""
        draft = load_spatial_draft(db, project_id, map_id) if map_id else None
        if draft is not None:
            extras["spatialState"] = {
                "characters": [fill.label for fill in draft.proposedFills if fill.kind == "character"],
                "props": [fill.label for fill in draft.proposedFills if fill.kind == "prop"],
                "relationships": [
                    f"{rel.subjectLabel} {rel.relation} {rel.objectLabel}" for rel in draft.relationships[:8]
                ],
                "zonePhrases": [item.phrase for item in draft.zonePhrases[:8]],
            }
            extras["identityState"] = [
                {"label": fill.label, "characterId": fill.characterId, "approved": fill.characterApproved}
                for fill in draft.proposedFills
                if fill.kind == "character"
            ]
    except Exception:
        logger.debug("Spatial extras unavailable for world packet")
    packet.extras = extras
    if project_id:
        packet.source.projectId = project_id
    if scene_id:
        packet.source.sceneId = scene_id
    return packet


def evaluate_project_assets(
    db: Session,
    *,
    project_id: str,
    asset_id: str,
    reference_asset_ids: list[str],
    scene_id: str = "",
    intentional_change: bool = False,
    image_path: str = "",
) -> WorldStatePacket:
    """Evaluate by project-owned asset ids. Rejects cross-project paths."""
    from ...db import Asset

    def _owned_path(aid: str) -> Optional[str]:
        row = db.get(Asset, aid)
        if row is None or str(row.project_id) != project_id:
            return None
        path = str(row.path or "")
        return path if path else None

    owned = _owned_path(asset_id)
    if owned is None:
        return WorldStatePacket(
            availability="unavailable",
            reason="Generated image is not in this project.",
            source=WorldStateSource(projectId=project_id, sceneId=scene_id, assetId=asset_id),
        )
    observed = image_path if image_path else owned
    refs: list[str] = []
    ref_paths: list[str] = []
    for ref_id in reference_asset_ids:
        path = _owned_path(ref_id)
        if path:
            refs.append(ref_id)
            ref_paths.append(path)
    packet = evaluate_generated_image(
        image_path=observed,
        asset_id=asset_id,
        reference_asset_ids=refs,
        reference_image_paths=ref_paths,
        project_id=project_id,
        scene_id=scene_id,
        intentional_change=intentional_change,
        db=db,
    )
    return _attach_production_extras(packet, db, project_id, scene_id)


def latest_advisory(db: Session, project_id: str, scene_id: str = "", asset_id: str = "") -> dict[str, Any]:
    stored = load_advisory(db, project_id, scene_id=scene_id, asset_id=asset_id)
    policy = get_policy(project_id, db)
    available = is_available(probe=False)
    if not stored:
        return {
            "available": bool(available.get("available")),
            "installed": bool(available.get("installed", available.get("available"))),
            "advisoryText": None,
            "packet": None,
            "policy": policy.model_dump(),
            "canMarkIntentional": False,
        }
    packet_raw = stored.get("packet") if isinstance(stored.get("packet"), dict) else {}
    try:
        packet = WorldStatePacket.model_validate(packet_raw)
        text = stored.get("advisoryText") or world_consistency_text(packet)
    except Exception:
        packet = None
        text = stored.get("advisoryText")
    return {
        "available": bool(available.get("available")),
        "installed": bool(available.get("installed", available.get("available"))),
        "advisoryText": text,
        "packet": packet.model_dump(mode="json") if packet else packet_raw,
        "policy": policy.model_dump(),
        "canMarkIntentional": bool(text and packet and packet.requires_review()),
        "sceneId": stored.get("sceneId") or scene_id,
        "assetId": stored.get("assetId") or asset_id,
    }
