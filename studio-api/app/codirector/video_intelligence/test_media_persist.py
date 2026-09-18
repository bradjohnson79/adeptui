"""Tests for the Adept Media Intelligence Packet persistence + cache layer.

Pure DB-layer tests against an in-memory SQLite database (mirrors the
``test_four_view_sheet`` fixture pattern). No GPU, no runtime, no ComfyUI.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, Project, ProjectTraitRow  # noqa: F401  (register tables)
from app.codirector.video_intelligence.media_packet import (
    ANALYSIS_VERSION,
    AnalysisFingerprint,
    MediaIntelligencePacket,
)
from app.codirector.video_intelligence.media_persist import (
    CATEGORY,
    LATEST_KEY,
    get_or_invalidate,
    is_fresh,
    load_fingerprint,
    load_latest_packet,
    load_packet,
    packet_key,
    save_packet,
)


@pytest.fixture()
def db() -> Session:
    """Fresh in-memory SQLite session with all Base tables created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-media", name="Media Packet Persist Test"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _fingerprint(
    *,
    asset_id: str = "asset-1",
    asset_hash: str = "hash-1",
    analysis_version: str = ANALYSIS_VERSION,
    qwen: str = "qwen-omni-v1",
    videochat: str = "videochat3-v1",
    diagnostic: str = "diag-v1",
) -> AnalysisFingerprint:
    return AnalysisFingerprint(
        assetId=asset_id,
        assetHash=asset_hash,
        analysisVersion=analysis_version,
        qwenOmniModelVersion=qwen,
        videoChat3ModelVersion=videochat,
        diagnosticVersion=diagnostic,
    )


def _packet(
    *,
    asset_id: str = "asset-1",
    summary: str = "Atrium establishing shot at dawn.",
    fingerprint: AnalysisFingerprint | None = None,
) -> MediaIntelligencePacket:
    return MediaIntelligencePacket(
        projectId="proj-media",
        assetId=asset_id,
        availability="ready",
        mode="full",
        summary=summary,
        fingerprint=fingerprint or _fingerprint(asset_id=asset_id),
    )


# ---------------------------------------------------------------------------
# save / load round trip
# ---------------------------------------------------------------------------


def test_save_and_load_packet_round_trip(db: Session) -> None:
    packet = _packet(summary="Glass atrium, dawn light, slow dolly in.")
    save_packet(db, "proj-media", packet)

    loaded = load_packet(db, "proj-media", "asset-1")
    assert loaded is not None
    assert loaded == packet, "round-trip must preserve every field"
    assert loaded.assetId == "asset-1"
    assert loaded.summary == "Glass atrium, dawn light, slow dolly in."
    assert loaded.fingerprint == packet.fingerprint


def test_save_packet_writes_both_asset_key_and_latest(db: Session) -> None:
    packet = _packet()
    save_packet(db, "proj-media", packet)

    asset_row = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == "proj-media",
            ProjectTraitRow.category == CATEGORY,
            ProjectTraitRow.key == packet_key("asset-1"),
        )
        .first()
    )
    latest_row = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.project_id == "proj-media",
            ProjectTraitRow.category == CATEGORY,
            ProjectTraitRow.key == LATEST_KEY,
        )
        .first()
    )
    assert asset_row is not None, "asset-scoped key must be written"
    assert latest_row is not None, "latest alias must be written"
    assert asset_row.value == latest_row.value, "both keys hold the same payload"


def test_load_packet_missing_returns_none(db: Session) -> None:
    assert load_packet(db, "proj-media", "never-saved") is None


def test_load_packet_unparseable_returns_none(db: Session) -> None:
    """A corrupt trait value must not raise; it returns None (mirrors world_intelligence)."""
    from app.spatial_map.ers_persistence import _upsert_trait

    _upsert_trait(
        db,
        project_id="proj-media",
        category=CATEGORY,
        key=packet_key("corrupt"),
        value="{not valid json",
        provenance="adept_media_intelligence",
    )
    assert load_packet(db, "proj-media", "corrupt") is None


def test_asset_scoped_key_takes_priority_over_latest(db: Session) -> None:
    """Saving a second asset overwrites latest, but asset-1 still resolves to its own packet."""
    packet1 = _packet(asset_id="asset-1", summary="first asset summary")
    packet2 = _packet(asset_id="asset-2", summary="second asset summary")
    save_packet(db, "proj-media", packet1)
    save_packet(db, "proj-media", packet2)

    loaded1 = load_packet(db, "proj-media", "asset-1")
    loaded2 = load_packet(db, "proj-media", "asset-2")
    assert loaded1 is not None and loaded1.summary == "first asset summary"
    assert loaded2 is not None and loaded2.summary == "second asset summary"


def test_load_packet_is_asset_strict_for_unknown_asset(db: Session) -> None:
    """An asset that was never saved returns None — asset-strict (Ch 41 isolation).

    The 'latest' alias is written for project-level queries but must NOT be
    returned for a specific asset lookup, otherwise another asset's packet
    would be mislabeled as this asset's intelligence.
    """
    packet = _packet(asset_id="asset-1", summary="the only packet")
    save_packet(db, "proj-media", packet)

    loaded = load_packet(db, "proj-media", "asset-never-saved")
    assert loaded is None


def test_load_latest_packet_returns_most_recent(db: Session) -> None:
    """load_latest_packet returns the most recently saved packet (any asset)."""
    packet = _packet(asset_id="asset-1", summary="the only packet")
    save_packet(db, "proj-media", packet)

    latest = load_latest_packet(db, "proj-media")
    assert latest is not None
    assert latest.summary == "the only packet"
    assert latest.assetId == "asset-1"


# ---------------------------------------------------------------------------
# load_fingerprint
# ---------------------------------------------------------------------------


def test_load_fingerprint_returns_just_the_fingerprint(db: Session) -> None:
    fp = _fingerprint(asset_id="asset-1", asset_hash="hash-abc")
    packet = _packet(asset_id="asset-1", fingerprint=fp)
    save_packet(db, "proj-media", packet)

    loaded_fp = load_fingerprint(db, "proj-media", "asset-1")
    assert loaded_fp is not None
    assert loaded_fp == fp
    assert loaded_fp.assetHash == "hash-abc"


def test_load_fingerprint_missing_returns_none(db: Session) -> None:
    assert load_fingerprint(db, "proj-media", "never-saved") is None


# ---------------------------------------------------------------------------
# is_fresh (Ch 7 invalidation)
# ---------------------------------------------------------------------------


def test_is_fresh_true_when_all_six_fields_match() -> None:
    cached = _fingerprint()
    current = _fingerprint()
    assert is_fresh(cached, current) is True


@pytest.mark.parametrize(
    "field, value",
    [
        ("assetId", "asset-other"),
        ("assetHash", "hash-other"),
        ("analysisVersion", "media-intelligence-v9"),
        ("qwenOmniModelVersion", "qwen-omni-v9"),
        ("videoChat3ModelVersion", "videochat3-v9"),
        ("diagnosticVersion", "diag-v9"),
    ],
)
def test_is_fresh_false_when_any_field_differs(field: str, value: str) -> None:
    cached = _fingerprint()
    current = cached.model_copy(update={field: value})
    assert is_fresh(cached, current) is False, f"Ch 7 must invalidate on {field} change"


# ---------------------------------------------------------------------------
# get_or_invalidate
# ---------------------------------------------------------------------------


def test_get_or_invalidate_returns_packet_when_fresh(db: Session) -> None:
    fp = _fingerprint(asset_id="asset-1", asset_hash="hash-1")
    packet = _packet(asset_id="asset-1", fingerprint=fp)
    save_packet(db, "proj-media", packet)

    result = get_or_invalidate(db, "proj-media", "asset-1", fp)
    assert result is not None
    assert result == packet


def test_get_or_invalidate_returns_none_when_stale(db: Session) -> None:
    cached_fp = _fingerprint(asset_id="asset-1", asset_hash="hash-old")
    packet = _packet(asset_id="asset-1", fingerprint=cached_fp)
    save_packet(db, "proj-media", packet)

    current_fp = _fingerprint(asset_id="asset-1", asset_hash="hash-new")
    assert get_or_invalidate(db, "proj-media", "asset-1", current_fp) is None


def test_get_or_invalidate_returns_none_when_no_cache(db: Session) -> None:
    current_fp = _fingerprint(asset_id="asset-1")
    assert get_or_invalidate(db, "proj-media", "asset-1", current_fp) is None


def test_get_or_invalidate_returns_none_when_fingerprint_unparseable(db: Session) -> None:
    from app.spatial_map.ers_persistence import _upsert_trait

    _upsert_trait(
        db,
        project_id="proj-media",
        category=CATEGORY,
        key=packet_key("asset-1"),
        value="{}",
        provenance="adept_media_intelligence",
    )
    current_fp = _fingerprint(asset_id="asset-1")
    assert get_or_invalidate(db, "proj-media", "asset-1", current_fp) is None


# ---------------------------------------------------------------------------
# project isolation
# ---------------------------------------------------------------------------


def test_packet_is_project_scoped(db: Session) -> None:
    """A packet saved under proj-media must not leak into another project's trait rows."""
    packet = _packet(asset_id="asset-1")
    save_packet(db, "proj-media", packet)

    other_rows = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.category == CATEGORY,
            ProjectTraitRow.project_id != "proj-media",
        )
        .count()
    )
    assert other_rows == 0, "save_packet must only write to the given project_id"
