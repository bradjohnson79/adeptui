"""Same-track no-overlap law — Python twin tests. No mocks."""

from app.director_timeline_w46.same_track_no_overlap import (
    SAME_TRACK_EPS,
    SameTrackOverlapError,
    assert_no_same_track_overlap,
    assert_prompt_segments_no_overlap,
    assert_track_array_no_overlap,
    audio_lane_kind,
    audit_master_same_track_overlaps,
    CD_LAYMAN_TRACK_OCCUPIED,
    find_same_track_intersection,
    find_same_track_overlap_pair,
    flatten_master_prompts,
    ranges_intersect,
    same_track_overlap_error,
    USER_FACING_TRACK_OCCUPIED,
)


def test_ranges_intersect_adjacent_ok():
    assert ranges_intersect(0, 10, 10, 10) is False
    assert ranges_intersect(10, 10, 0, 10) is False


def test_ranges_intersect_open_overlap():
    assert ranges_intersect(0, 10, 0, 10) is True
    assert ranges_intersect(0, 10, 5, 5) is True
    assert ranges_intersect(0, 9.938, 0, 10) is True


def test_ranges_intersect_separated():
    assert ranges_intersect(0, 5, 6, 2) is False


def test_ranges_intersect_epsilon():
    assert ranges_intersect(0, 10, 10 - SAME_TRACK_EPS / 2, 4) is False
    assert ranges_intersect(0, 10, 10 - 1e-6, 4) is True


def test_find_intersection_excludes_same_id():
    clips = [{"id": "keep", "start": 0, "length": 10}, {"id": "later", "start": 10, "length": 10}]
    assert find_same_track_intersection(clips, {"id": "keep", "start": 0, "length": 10}) is None
    hit = find_same_track_intersection(clips, {"id": "new", "start": 0, "length": 2})
    assert hit["id"] == "keep"


def test_scene10_illegal_stack_detected():
    stacked = [
        {"id": "clip_omni_music_bd13b3", "start": 0, "length": 9.938},
        {"id": "clip_omni_sfx_bd13b3", "start": 0, "length": 0.15},
        {"id": "clip_430c79f36a18", "start": 0, "length": 10},
    ]
    pair = find_same_track_overlap_pair(stacked)
    assert pair is not None
    assert pair[0]["id"] == "clip_omni_music_bd13b3"


def test_assert_throws_and_returns_error():
    assert same_track_overlap_error([], {"id": "n", "start": 0, "length": 2}) is None
    assert_no_same_track_overlap([], {"id": "n", "start": 0, "length": 2})
    try:
        assert_no_same_track_overlap(
            [{"id": "keep", "start": 0, "length": 10}],
            {"id": "n", "start": 0, "length": 2},
            "audio",
        )
        raise AssertionError("expected SameTrackOverlapError")
    except SameTrackOverlapError as exc:
        assert "SAME_TRACK_OVERLAP" in str(exc)
        assert "audio" in str(exc)
    try:
        assert_track_array_no_overlap(
            [{"id": "a", "start": 0, "length": 10}, {"id": "b", "start": 0, "length": 8}],
            "audio",
        )
        raise AssertionError("expected SameTrackOverlapError")
    except SameTrackOverlapError as exc:
        assert exc.code == "SAME_TRACK_OVERLAP"


def test_music_aliased_to_audio_lane():
    assert audio_lane_kind("music") == "audio"
    assert audio_lane_kind("ambience") == "audio"
    assert audio_lane_kind("audio") == "audio"
    assert audio_lane_kind("sfx") == "sfx"


def test_edge_touch_prompt_segments_ok():
    assert_prompt_segments_no_overlap(
        [{"id": "a", "start": 0, "length": 5}, {"id": "b", "start": 5, "length": 5}],
    )


def test_open_overlap_prompt_segments_rejected():
    try:
        assert_prompt_segments_no_overlap(
            [{"id": "a", "start": 0, "length": 5}, {"id": "b", "start": 4.9, "length": 5}],
        )
        raise AssertionError("expected SameTrackOverlapError")
    except SameTrackOverlapError as exc:
        assert exc.code == "SAME_TRACK_OVERLAP"


def test_cross_batch_other_segments_rejected():
    try:
        assert_prompt_segments_no_overlap(
            [{"id": "new", "start": 0, "length": 2}],
            other_segments=[{"id": "keep", "start": 0, "length": 10}],
        )
        raise AssertionError("expected SameTrackOverlapError")
    except SameTrackOverlapError:
        pass


def test_audit_master_same_track_overlaps():
    class Seg:
        def __init__(self, id, start, length):
            self.id = id
            self.start = start
            self.length = length

    class Batch:
        def __init__(self, id, prompts=None, audio=None):
            self.id = id
            self.order = 0
            self.promptSegments = prompts or []
            self.visualClips = []
            self.audioClips = audio or []
            self.sfxClips = []
            self.cameraInstructions = []

    class Master:
        def __init__(self, blocks):
            self.batchBlocks = blocks

    clean = Master([Batch("b1", prompts=[Seg("a", 0, 5), Seg("b", 5, 5)])])
    assert audit_master_same_track_overlaps(clean) == []
    assert len(flatten_master_prompts(clean)) == 2

    dirty = Master(
        [
            Batch("b1", prompts=[Seg("a", 0, 5), Seg("b", 4, 5)]),
            Batch("b2", audio=[Seg("x", 0, 3), Seg("y", 1, 3)]),
        ]
    )
    findings = audit_master_same_track_overlaps(dirty)
    tracks = {f["track"] for f in findings}
    assert "prompt" in tracks
    assert "audioClips" in tracks


def test_layman_constants():
    assert "already occupied" in USER_FACING_TRACK_OCCUPIED.lower()
    assert "already in use" in CD_LAYMAN_TRACK_OCCUPIED.lower()
    assert "SAME_TRACK" not in CD_LAYMAN_TRACK_OCCUPIED
