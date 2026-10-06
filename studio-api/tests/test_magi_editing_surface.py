"""MAGI editing-surface owners: recipes, lighting params, boundary transitions."""

from app.magi.color_grading import compile_filter_string
from app.magi.lighting import LIGHTING_PRESETS, canonical_lighting_preset
from app.magi.recipes import apply_recipe
from app.magi.transitions import canonical_transition, xfade_chain_filter


def _sequence():
    return {
        "frameRate": 24,
        "snapEnabled": True,
        "recipeId": None,
        "tracks": [
            {"id": "v", "kind": "video", "label": "VIDEO"},
            {"id": "a", "kind": "audio", "label": "AUDIO"},
            {"id": "m", "kind": "music", "label": "MUSIC"},
            {"id": "s", "kind": "sfx", "label": "SFX"},
        ],
        "clips": [
            {"id": "video", "trackId": "v", "assetId": "pic", "startFrame": 0, "durationFrames": 100},
            {"id": "dialogue", "trackId": "a", "assetId": "pic", "startFrame": 0, "durationFrames": 100},
            {"id": "music", "trackId": "m", "assetId": "bed", "startFrame": 0, "durationFrames": 80},
            {"id": "sfx", "trackId": "s", "assetId": "vanish", "startFrame": 40, "durationFrames": 10},
        ],
    }


def test_interview_recipe_changes_sfx_posture_without_touching_clips():
    updated = apply_recipe(_sequence(), "Interview")
    assert updated["recipeId"] == "interview"
    assert updated["snapEnabled"] is True
    sfx = next(track for track in updated["tracks"] if track["kind"] == "sfx")
    video = next(track for track in updated["tracks"] if track["kind"] == "video")
    assert sfx["muted"] is True
    assert video["muted"] is False
    assert [(c["id"], c["assetId"], c["startFrame"], c["durationFrames"]) for c in updated["clips"]] == [
        ("video", "pic", 0, 100),
        ("dialogue", "pic", 0, 100),
        ("music", "bed", 0, 80),
        ("sfx", "vanish", 40, 10),
    ]


def test_lighting_presets_compile_into_the_existing_color_filters():
    assert canonical_lighting_preset("Soft Bright") == "soft_bright"
    warm = compile_filter_string(LIGHTING_PRESETS["warm"])
    assert "colorbalance=" not in warm
    assert "hue=h=-3.92" in warm
    bright = compile_filter_string({"brightness": 0.08, "highlights": 0.04, "shadows": 0.06, "temperature": 0.1})
    assert "lutrgb=" in bright
    assert "hue=h=-2.80" in bright
    assert "colorbalance=" not in bright


def test_boundary_transition_filter_is_xfade_not_a_full_sequence_effect():
    assert canonical_transition("Dissolve") == "dissolve"
    graph = xfade_chain_filter([10.0, 8.0], [{"kind": "dissolve", "xfade": 1.0}])
    assert "xfade=transition=fade:duration=1.000:offset=9.500" in graph
    assert "tpad=" in graph
    assert "acrossfade" not in graph
    assert "concat=n=2:v=0:a=1" in graph
    wipe = xfade_chain_filter([5.0, 5.0], [{"kind": "wipe", "xfade": 0.5}])
    assert "transition=wipeleft" in wipe
    fade = xfade_chain_filter([5.0, 5.0], [{"kind": "fade", "xfade": 0.4}])
    assert "transition=fadeblack" in fade
