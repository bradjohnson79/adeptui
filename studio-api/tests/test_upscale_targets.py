from app.magi.upscale_targets import (
    TARGET_NOT_ABOVE,
    TARGET_UNKNOWN,
    UpscaleTargetError,
    aspect_label,
    aspects_match,
    default_target,
    is_above_source,
    meaningful_targets,
    resolve_apply_target,
)
from app.magi.upscaling import scale_filter


def test_1080_to_1080_rejected():
    assert is_above_source(1920, 1080, 1920, 1080) is False
    assert [row["id"] for row in meaningful_targets(1920, 1080)] == ["1440p", "2K", "4K", "8K"]
    first = default_target(1920, 1080)
    assert first and first["id"] == "1440p"
    try:
        resolve_apply_target(1920, 1080, "1920x1080")
        raise AssertionError("1080→1080 must be refused")
    except UpscaleTargetError as exc:
        assert exc.code == TARGET_NOT_ABOVE


def test_1080_to_1440_ok():
    width, height, label = resolve_apply_target(1920, 1080, "1440p")
    assert (width, height) == (2560, 1440)
    assert label == "1440p"
    assert aspect_label(width, height) == "16:9"


def test_empty_target_never_defaults_to_same_1080():
    width, height, label = resolve_apply_target(1920, 1080, "")
    assert (width, height) == (2560, 1440)
    assert label == "1440p"


def test_720_offers_1080_first():
    first = default_target(1280, 720)
    assert first and first["id"] == "1080p"
    assert [row["id"] for row in meaningful_targets(1280, 720)] == ["1080p", "1440p", "2K", "4K", "8K"]


def test_portrait_keeps_source_ratio():
    """Tall masters stay tall. They are not snapped to a swapped 16:9 canvas."""
    rows = meaningful_targets(704, 1248)
    assert rows, "portrait 720p-class must have higher MAGI targets"
    assert all(row["height"] > row["width"] for row in rows)
    assert rows[0]["id"] == "1080p"
    assert (rows[0]["width"], rows[0]["height"]) != (1080, 1920)
    assert aspects_match(704, 1248, rows[0]["width"], rows[0]["height"])
    width, height, label = resolve_apply_target(704, 1248, "1080p")
    assert (width, height) == (rows[0]["width"], rows[0]["height"])
    assert label == "1080p"
    assert is_above_source(704, 1248, 1920, 1080) is False


def test_exact_9_16_stays_9_16():
    width, height, label = resolve_apply_target(1080, 1920, "1440p")
    assert (width, height) == (1440, 2560)
    assert label == "1440p"
    assert aspect_label(width, height) == "9:16"
    assert aspects_match(1080, 1920, width, height)


def test_21_9_classes_do_not_become_16_9():
    source_w, source_h = 1568, 672
    old = resolve_apply_target(source_w, source_h, "2560x1440")
    assert old[0] != 2560 or old[1] != 1440
    preview = {}
    for label in ("1440p", "2K", "4K"):
        width, height, resolved = resolve_apply_target(source_w, source_h, label)
        again = resolve_apply_target(source_w, source_h, f"{width}x{height}")
        assert (again[0], again[1]) == (width, height)
        assert resolved == label
        assert aspects_match(source_w, source_h, width, height)
        assert aspect_label(width, height) == "21:9"
        preview[label] = (width, height)
    assert preview["1440p"] == (3360, 1440)
    assert preview["2K"][1] == 2048
    assert preview["4K"] == (5040, 2160)
    assert preview["1440p"] != (2560, 1440)


def test_nonstandard_ratio_is_preserved():
    width, height, label = resolve_apply_target(1000, 777, "1440p")
    assert label == "1440p"
    assert aspects_match(1000, 777, width, height)
    assert aspect_label(width, height) != "16:9"
    same = resolve_apply_target(1000, 777, f"{width}x{height}")
    assert (same[0], same[1]) == (width, height)


def test_unknown_target_does_not_fall_back_to_16_9():
    try:
        resolve_apply_target(1568, 672, "not-a-size")
        raise AssertionError("unknown targets must not become 1920x1080")
    except UpscaleTargetError as exc:
        assert exc.code == TARGET_UNKNOWN


def test_scale_filter_does_not_crop_or_pad():
    filt = scale_filter(3360, 1440, "lanczos")
    assert filt.startswith("scale=3360:1440:")
    assert "pad" not in filt
    assert "crop" not in filt
    assert "setsar=1" in filt


def test_production_aspects_include_9_16():
    from app.aspect_fps import PRODUCTION_ASPECTS, normalize_production_aspect

    assert list(PRODUCTION_ASPECTS) == ["1:1", "4:3", "16:9", "9:16", "21:9"]
    assert normalize_production_aspect("9:16") == "9:16"
    assert normalize_production_aspect("weird") == "16:9"
