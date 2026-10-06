"""Lightweight Revision D smoke: contracts, pack, frozen exclusions."""

from app.codirector.perception.service import get_capability
from app.setup.catalog import BY_ID
from app.setup.essentials_pack import pack_status
from app.spatial_map.schemas import SpatialMapDocument


def test_capability_has_revision_d_flags():
    cap = get_capability()
    dumped = cap.model_dump()
    assert "select" in dumped
    assert "track" in dumped
    assert "removeBackground" in dumped
    assert dumped["chatRequired"] is False


def test_spatial_map_still_has_no_zones():
    assert "zones" not in SpatialMapDocument.model_fields


def test_exclusions_hold():
    assert "timelens" not in BY_ID
    assert "vggt" not in BY_ID
    assert "vggt_1b_commercial" in BY_ID


def test_essentials_pack_smoke():
    status = pack_status()
    assert status["essentialTotal"] == 5
    assert status["generationBlockedByPack"] is False
    labels = {group["label"] for group in status["groups"]}
    assert "Intelligent Selection" in labels
    assert "Video Intelligence" in labels
