"""Project-scoped persistence + cache layer for the Adept Media Intelligence Packet.

Mirrors the world_intelligence persistence pattern (persist.py): stores the
``MediaIntelligencePacket`` as a JSON value on ``ProjectTraitRow``
(category=media_intelligence_packet) so reload/reopen returns the same
creator-facing state (Ch 41-42). Asset-scoped (projectId+assetId) with a
``"latest"`` alias, exactly like world_intelligence advisories.

The cache fingerprint (Ch 7) invalidates on asset/hash/model/version change.

Pure DB-layer code. No GPU, no runtime, no ComfyUI, no Studio API recycle.
"""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from .media_packet import (
    AnalysisFingerprint,
    MediaIntelligencePacket,
)

CATEGORY = "media_intelligence_packet"
PROVENANCE = "adept_media_intelligence"
LATEST_KEY = "latest"


def packet_key(asset_id: str) -> str:
    """Stable per-asset trait key. Mirrors world_intelligence.advisory_key."""
    return f"asset:{asset_id}"


def _load_raw(db: Session, project_id: str, asset_id: str) -> Optional[str]:
    """Return the stored raw JSON for THIS asset only (asset-strict, Ch 41 isolation).

    Never falls back to ``"latest"`` — that would mislabel another asset's packet
    as this asset's. The ``"latest"`` alias is still written by ``save_packet`` for
    project-level "most recent" queries (see ``load_latest_packet``), but a specific
    asset lookup must be strict so the cache and Timeline never consume the wrong
    asset's intelligence.
    """
    from ...spatial_map.ers_persistence import _load_trait_value

    return _load_trait_value(db, project_id=project_id, category=CATEGORY, key=packet_key(asset_id))


def _load_latest_raw(db: Session, project_id: str) -> Optional[str]:
    """Return the most recently saved packet raw JSON for the project (any asset)."""
    from ...spatial_map.ers_persistence import _load_trait_value

    return _load_trait_value(db, project_id=project_id, category=CATEGORY, key=LATEST_KEY)


def save_packet(db: Session, project_id: str, packet: MediaIntelligencePacket) -> None:
    """Upsert the packet under asset:{assetId} and the latest alias.

    Mirrors world_intelligence.save_advisory, which writes both the scoped
    key and "latest" so the most recent packet is always recoverable.
    """
    from ...spatial_map.ers_persistence import _upsert_trait

    raw = packet.model_dump_json()
    for key in {packet_key(packet.assetId), LATEST_KEY}:
        _upsert_trait(
            db,
            project_id=project_id,
            category=CATEGORY,
            key=key,
            value=raw,
            provenance=PROVENANCE,
        )


def load_packet(
    db: Session, project_id: str, asset_id: str
) -> Optional[MediaIntelligencePacket]:
    """Load the packet for THIS asset only (asset-strict). None if missing/unparseable."""
    raw = _load_raw(db, project_id, asset_id)
    if not raw:
        return None
    try:
        return MediaIntelligencePacket.model_validate_json(raw)
    except Exception:
        return None


def load_latest_packet(
    db: Session, project_id: str
) -> Optional[MediaIntelligencePacket]:
    """Load the most recently saved packet for the project (any asset).

    Use for project-level 'most recent analysis' queries. Do NOT use as a
    substitute for a specific asset lookup — that must go through ``load_packet``.
    """
    raw = _load_latest_raw(db, project_id)
    if not raw:
        return None
    try:
        return MediaIntelligencePacket.model_validate_json(raw)
    except Exception:
        return None


def load_fingerprint(
    db: Session, project_id: str, asset_id: str
) -> Optional[AnalysisFingerprint]:
    """Read just the cache fingerprint for a cache-check without full deserialize."""
    raw = _load_raw(db, project_id, asset_id)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    fp_data = data.get("fingerprint")
    if not isinstance(fp_data, dict):
        return None
    try:
        return AnalysisFingerprint.model_validate(fp_data)
    except Exception:
        return None


def is_fresh(cached: AnalysisFingerprint, current: AnalysisFingerprint) -> bool:
    """Ch 7 invalidation: fresh iff asset + hash + analysis + model versions all match."""
    return (
        cached.assetId == current.assetId
        and cached.assetHash == current.assetHash
        and cached.analysisVersion == current.analysisVersion
        and cached.qwenOmniModelVersion == current.qwenOmniModelVersion
        and cached.videoChat3ModelVersion == current.videoChat3ModelVersion
        and cached.diagnosticVersion == current.diagnosticVersion
    )


def get_or_invalidate(
    db: Session,
    project_id: str,
    asset_id: str,
    current_fingerprint: AnalysisFingerprint,
) -> Optional[MediaIntelligencePacket]:
    """Return the cached packet if its fingerprint is fresh, else None (caller reanalyzes)."""
    cached_fp = load_fingerprint(db, project_id, asset_id)
    if cached_fp is None:
        return None
    if not is_fresh(cached_fp, current_fingerprint):
        return None
    return load_packet(db, project_id, asset_id)
