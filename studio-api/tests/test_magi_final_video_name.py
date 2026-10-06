"""Final Render title is one name for the library and the file."""

from app.magi.final_video_name import (
    FINAL_VIDEO_NAME_CONFLICT,
    name_conflicts,
    parse_final_video_name,
)


def test_parse_keeps_spaces_and_strips_a_typed_extension():
    named = parse_final_video_name("  Renkoka Final Scene.mp4  ")
    assert named.title == "Renkoka Final Scene"
    assert named.filename == "Renkoka Final Scene.mp4"
    doubled = parse_final_video_name("scene.mp4.mp4")
    assert doubled.title == "scene"
    assert doubled.filename == "scene.mp4"


def test_parse_rejects_empty_and_invalid_characters():
    for raw in ("", "   ", "scene.mp4.mp4".replace("scene", ""), "Renkoka/Final", "CON"):
        try:
            parse_final_video_name(raw)
        except ValueError:
            continue
        raise AssertionError(raw)


def test_conflict_matches_library_title_or_file_and_not_a_generic_tag():
    named = parse_final_video_name("Renkoka Final Scene")
    assert name_conflicts(named, [("Renkoka Final Scene", "magi_final_render_old.mp4")], path_exists=False)
    other = parse_final_video_name("Other Cut")
    assert name_conflicts(other, [("magi_final", "Other Cut.mp4")], path_exists=False)
    assert name_conflicts(other, [], path_exists=True)
    assert not name_conflicts(other, [("magi_final", "magi_final_render_old.mp4")], path_exists=False)
    assert FINAL_VIDEO_NAME_CONFLICT.startswith("A file with this name")
