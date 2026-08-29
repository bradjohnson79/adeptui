from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.cinematography import (
    LENS_VALUES,
    LIGHTING_MOODS,
    SHOT_SIZES,
    camera_nl_instruction,
    compile_canonical_camera,
)
from app.director_timeline import CameraClip
from app.director_timeline_w46.camera_catalog import LENS_VALUES as CAT_LENS
from app.director_timeline_w46.camera_catalog import LIGHTING_MOODS as CAT_LIGHT
from app.director_timeline_w46.camera_catalog import SHOT_SIZES as CAT_SHOT
from app.director_timeline_w46.contracts import BatchBlock, BatchClip, DurationState


def test_catalog_reexport_matches_cinematography():
    assert CAT_LENS == LENS_VALUES
    assert CAT_LIGHT == LIGHTING_MOODS
    assert CAT_SHOT == SHOT_SIZES
    assert "fisheye" in LENS_VALUES
    assert "golden_hour" in LIGHTING_MOODS
    assert "close_up" in SHOT_SIZES


def test_compile_canonical_camera_from_legacy_and_batch():
    from app.director_timeline import DirectorTimeline

    tl = DirectorTimeline(
        duration_sec=5,
        camera_clips=[
            CameraClip(
                id="cam1",
                start=0,
                length=5,
                motion_type="dolly_in",
                rig="dolly",
                shot_id="close_up",
                lens_id="35",
                lighting_id="golden_hour",
                text="slow push",
            )
        ],
    )
    batch = BatchBlock(
        sceneId="s",
        duration=DurationState(plannedDuration=5.0),
        cameraInstructions=[BatchClip(kind="camera", motion_type="push", rig="tripod")],
    )
    camera = compile_canonical_camera(batch=batch, director_timeline=tl, window_start=0.0, window_length=5.0)
    assert camera is not None
    assert camera["motion"] == "dolly_in"
    assert camera["rig"] == "dolly"
    assert camera["shot_id"] == "close_up"
    assert camera["lens_id"] == "35"
    assert camera["lighting_id"] == "golden_hour"
    assert camera["text"] == "slow push"
    nl = camera_nl_instruction(camera)
    assert "close up" in nl.lower()
    assert "35mm" in nl
    assert "dolly" in nl.lower()
    assert "slow push" in nl
    assert nl.startswith("Camera:")


def test_camera_clip_rejects_invalid_catalog_ids():
    with pytest.raises(ValidationError):
        CameraClip(shot_id="not-a-shot")
    with pytest.raises(ValidationError):
        CameraClip(lens_id="200")
    with pytest.raises(ValidationError):
        CameraClip(lighting_id="disco")
    clip = CameraClip(shot_id="wide", lens_id="auto", lighting_id=None)
    assert clip.shot_id == "wide"
    assert clip.lens_id == "auto"
    assert clip.lighting_id is None

def test_camera_clip_one_vocabulary_serializes_fe_names_only():
    # Old names are not schema aliases (extra=ignore). One vocabulary.
    ignored = CameraClip.model_validate(
        {
            "shot_size": "wide",
            "lens": "50",
            "focus_subject": "char_hero",
            "lighting": "night",
            "text": "hold",
        }
    )
    assert ignored.shot_id is None
    assert ignored.lens_id is None
    assert ignored.focus_id is None
    assert ignored.lighting_id is None
    assert ignored.text == "hold"

    clip = CameraClip(
        shot_id="wide",
        lens_id="50",
        focus_id="char_hero",
        focus_name="Hero",
        lighting_id="night",
        text="hold",
    )
    dumped = clip.model_dump()
    for banned in ("shot_size", "lens", "focus_subject", "lighting", "shotSize", "focusSubject", "lightingMood"):
        assert banned not in dumped
    assert dumped["shot_id"] == "wide"
    assert dumped["lens_id"] == "50"
    assert dumped["focus_id"] == "char_hero"
    assert dumped["focus_name"] == "Hero"
    assert dumped["lighting_id"] == "night"


def test_label_helpers_twin_fe():
    from app.cinematography import (
        CAMERA_FOCUS_ENVIRONMENT_ID,
        camera_focus_label,
        camera_lens_label,
        camera_shot_label,
        format_camera_clip_label,
        hydrate_camera_lens,
        hydrate_camera_shot,
        lighting_preset_label,
    )
    from app.director_timeline_w46.camera_catalog import (
        camera_shot_label as cat_shot,
        format_camera_clip_label as cat_fmt,
    )

    assert camera_shot_label("close_up") == "Close Up"
    assert camera_lens_label("35") == "35mm"
    assert lighting_preset_label("golden_hour") == "Golden Hour"
    assert camera_focus_label(CAMERA_FOCUS_ENVIRONMENT_ID) == "Environment"
    assert camera_focus_label("char_1", "Vana") == "@Vana"
    assert hydrate_camera_shot("Medium Close") == "medium_close"
    assert hydrate_camera_lens("35mm") == "35"
    assert cat_shot("wide") == "Wide"
    label = format_camera_clip_label(shot_id="close_up", lens_id="50", focus_id="c1", focus_name="Vana", motionLabel="Dolly In")
    assert "Close Up" in label
    assert "50mm" in label
    assert "@Vana" in label
    assert "Dolly In" in label
    assert cat_fmt(shot_id="wide", motionLabel="Static") == "Wide · Static"

