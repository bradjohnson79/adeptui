from app.spatial_map.camera_optics import (
    apply_reconcile_to_camera,
    fisheye_prompt_lines,
    fov_degrees_from_lens_mm,
    hydrate_lens,
    hydrate_lighting_mood,
    is_api_mini_generator,
    is_fisheye_lens,
    is_local_mini_generator,
    lighting_mood_prompt_line,
    mini_api_max_concurrent,
    reconcile_lens_fov,
    snap_fov_preset,
    subject_distance_meters,
    validate_camera_for_mini,
    LIGHTING_MOODS,
    LENS_VALUES,
)


def test_missing_lens_and_mood_hydrate_auto() -> None:
    assert hydrate_lens(None) == "auto"
    assert hydrate_lens("") == "auto"
    assert hydrate_lighting_mood(None) == "auto"
    assert hydrate_lighting_mood("Sci-Fi") == "sci_fi"
    assert "sci_fi" in LIGHTING_MOODS
    assert "fantasy" in LIGHTING_MOODS


def test_manual_lens_snaps_fov_preset() -> None:
    wide = reconcile_lens_fov(lens="18", fov_preset="narrow")
    assert wide["fovPreset"] == "wide"
    assert wide["lensMm"] == 18.0
    assert wide["fovDegrees"] and wide["fovDegrees"] > 80
    tele = reconcile_lens_fov(lens="85", fov_preset="wide")
    assert tele["fovPreset"] == "narrow"
    auto = reconcile_lens_fov(lens="35", fov_preset="medium", last_control="fov")
    assert auto["lens"] == "auto"


def test_full_frame_fov_math() -> None:
    assert snap_fov_preset(fov_degrees_from_lens_mm(18)) == "wide"
    assert snap_fov_preset(fov_degrees_from_lens_mm(50)) == "medium"
    assert snap_fov_preset(fov_degrees_from_lens_mm(100)) == "narrow"


def test_distance_only_when_subject_exists() -> None:
    cam = {"x": 0.0, "z": 0.0}
    subj = {"x": 3.0, "z": 4.0}
    assert subject_distance_meters(cam, subj) == 5.0
    assert subject_distance_meters(cam, None) is None
    assert subject_distance_meters(cam, {"label": "no coords"}) is None


def test_validate_camera_isolates_bad_position() -> None:
    err = validate_camera_for_mini({"visible": True, "yawDegrees": 0}, distance=None, has_subject=False)
    assert err and "position" in err.lower()


def test_auto_mood_does_not_force_daylight() -> None:
    line = lighting_mood_prompt_line("auto", env_identity="Night hangar")
    assert "Night hangar" in line
    assert "Do not force generic daylight" in line
    sci = lighting_mood_prompt_line("sci_fi")
    assert "Sci-Fi" in sci
    assert "cyberpunk" in sci.lower()


def test_generator_classes() -> None:
    assert is_local_mini_generator("qwen2512")
    assert not is_local_mini_generator("gpt-image-2")
    assert is_api_mini_generator("gpt-image-2")
    assert mini_api_max_concurrent() >= 1


def test_fisheye_is_not_rectilinear_18mm() -> None:
    assert "fisheye" in LENS_VALUES
    assert hydrate_lens("fisheye") == "fisheye"
    assert hydrate_lens("fish-eye") == "fisheye"
    assert is_fisheye_lens("fisheye")
    optics = reconcile_lens_fov(lens="fisheye", fov_preset="narrow", lens_mm=35.0)
    assert optics["lens"] == "fisheye"
    assert optics["fovDegrees"] is None
    assert optics["lensMm"] == 35.0
    assert optics["fovPreset"] == "wide"
    lines = "\n".join(fisheye_prompt_lines())
    assert "cinematic fisheye lens" in lines
    assert "18mm" in lines  # honesty: not 18mm
    assert "not a rectilinear" in lines


def test_apply_reconcile_on_object() -> None:
    class Cam:
        lens = "18"
        lensMm = 35.0
        fovPreset = "narrow"
        lightingMood = None

    cam = Cam()
    apply_reconcile_to_camera(cam, {"lens": "18"})
    assert cam.fovPreset == "wide"
    assert cam.lightingMood == "auto"
