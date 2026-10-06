"""ORDER 10B: no Lip Sync 1 mint on empty; Owner Lip Sync creator UX lock."""

from __future__ import annotations

import pytest

from app.director_timeline import DirectorTimeline, parse_director_timeline
from app.director_timeline_w46.creator_lipsync_surface import (
    CREATOR_LIPSYNC_MUTATION_DISABLED,
    OWNER_LIPSYNC_UX_REINTRODUCE_FORBIDDEN,
    TIMELINE_LIPSYNC_CREATOR_UI,
    creator_lipsync_mutation_blocked,
    empty_lipsync_tracks,
    forbid_creator_lipsync_mutation,
    owner_lipsync_ux_reintroduce_forbidden,
)
from app.lipsync_tracks import LipSyncTracks, parse_lipsync_tracks


def test_owner_law_aligned_with_fe_flag():
    assert TIMELINE_LIPSYNC_CREATOR_UI is False
    assert OWNER_LIPSYNC_UX_REINTRODUCE_FORBIDDEN is True
    assert owner_lipsync_ux_reintroduce_forbidden() is True


def test_empty_parse_returns_no_tracks_under_owner_law():
    for raw in (None, "", "   ", "{}", '{"tracks": []}', "not-json"):
        parsed = parse_lipsync_tracks(raw)
        assert parsed.tracks == [], f"raw={raw!r} minted {parsed.tracks!r}"
        assert not any(
            (t.label or "").startswith("Lip Sync") for t in parsed.tracks
        )


def test_legacy_default_method_still_mints_for_tests():
    legacy = LipSyncTracks.default()
    assert len(legacy.tracks) == 1
    assert legacy.tracks[0].label == "Lip Sync 1"


def test_empty_lipsync_tracks_helper():
    empty = empty_lipsync_tracks()
    assert empty.tracks == []


def test_creator_lipsync_mutation_blocked_code():
    blocked = creator_lipsync_mutation_blocked("PUT lipsync-tracks")
    assert blocked["ok"] is False
    assert blocked["error"] == CREATOR_LIPSYNC_MUTATION_DISABLED
    assert blocked["error"] == "CREATOR_LIPSYNC_MUTATION_DISABLED"
    assert "TIMELINE_LIPSYNC_CREATOR_UI=false" in blocked["ownerLaw"]
    blocked2 = creator_lipsync_mutation_blocked("POST lipsync-tracks/bake")
    assert blocked2["error"] == CREATOR_LIPSYNC_MUTATION_DISABLED


def test_forbid_creator_lipsync_mutation_raises():
    with pytest.raises(RuntimeError, match="OWNER_LIPSYNC_UX_REINTRODUCE_FORBIDDEN"):
        forbid_creator_lipsync_mutation("unit-test mint Lip Sync 1")


def test_director_timeline_default_has_no_lip_sync_1():
    tl = DirectorTimeline.default()
    assert tl.lipsync.tracks == []
    labels = [t.label for t in tl.lipsync.tracks]
    assert "Lip Sync 1" not in labels


def test_parse_director_timeline_none_has_empty_lipsync():
    tl = parse_director_timeline(None)
    assert tl.lipsync.tracks == []
    assert not any((t.label or "") == "Lip Sync 1" for t in tl.lipsync.tracks)


def test_parse_director_timeline_empty_json_has_empty_lipsync():
    tl = parse_director_timeline("{}")
    # empty/missing lipsync field uses model default factory → empty under Owner law
    assert tl.lipsync.tracks == [] or all(
        (t.label or "") != "Lip Sync 1" or False for t in []
    )
    assert tl.lipsync.tracks == []
