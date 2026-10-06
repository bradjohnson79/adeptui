from app.timeline_media_labels import (
    apply_resolved_media_clip_labels,
    extract_quoted_dialogue_from_prompt,
    resolve_media_clip_labels,
    truncate_clip_face_label,
)

BATCH1 = (
    'They speak these lines, each in their own voice, lips matching speech: '
    'Anadriya says, "That\'s it — Cade\'s down. Corridor\'s ours." '
    'Korri says, "Told you we\'d walk this one out."'
)


def test_truncate_and_no_fabricate():
    assert truncate_clip_face_label("short") == "short"
    assert truncate_clip_face_label("A" * 40, 36).endswith("…")
    empty = resolve_media_clip_labels({"kind": "audio", "clip": {}})
    assert empty["title"] is None
    assert empty["description"] is None
    assert empty["label"] == ""
    assert empty["sources"]["title"] == "none"


def test_prompt_extract_scene10():
    hits = extract_quoted_dialogue_from_prompt(BATCH1, "Anadriya")
    assert hits == [
        {"speaker": "Anadriya", "line": "That's it — Cade's down. Corridor's ours."}
    ]


def test_lipsync_prompt_fallback():
    r = resolve_media_clip_labels(
        {
            "kind": "lipsync",
            "clip": {
                "id": "4a3dccebe3",
                "label": "Anadriya line",
                "line": "",
                "character_name": "Anadriya",
                "audio_asset_id": "a37cb212-c49b-46cf-9d5f-dc4a17f4d927",
            },
            "promptContext": {"prompts": [BATCH1], "clipStart": 0.1, "clipLength": 2.8},
        }
    )
    assert r["sources"]["title"] == "prompt"
    assert r["title"] == "Anadriya: That's it — Cade's down. Corridor's ours."
    assert "audio_asset_id=" in (r["description"] or "")


def test_audio_metadata_then_filename():
    r = resolve_media_clip_labels(
        {
            "kind": "sfx",
            "clip": {"label": "SFX corridor boots Omni — Batch1_VictoryA"},
        }
    )
    assert r["sources"]["title"] == "metadata"
    r2 = resolve_media_clip_labels(
        {"kind": "audio", "clip": {"label": "Audio"}, "asset": {"filename": "bed.wav"}}
    )
    assert r2["sources"]["title"] == "filename"
    assert r2["title"] == "bed"


def test_apply_backfill_line():
    resolved = resolve_media_clip_labels(
        {
            "kind": "lipsync",
            "clip": {"character_name": "Korri", "line": "", "label": "Korri line"},
            "promptContext": {"prompts": [BATCH1]},
        }
    )
    clip = {"character_name": "Korri", "line": "", "label": "Korri line"}
    apply_resolved_media_clip_labels(
        clip, resolved, set_line_from_title=True, speaker="Korri"
    )
    assert clip["line"] == "Told you we'd walk this one out."
