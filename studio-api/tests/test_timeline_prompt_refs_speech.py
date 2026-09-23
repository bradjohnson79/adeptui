"""Prompt-clip reference hydration, Lip Sync speakers, and speech hierarchy."""

from __future__ import annotations

import json

from app.db import Asset, Base, Project
from app.director_timeline import (
    DirectorTimeline,
    PromptSegment,
    TimelineClip,
    dumps_director_timeline,
    hydrate_prompt_refs,
    parse_director_timeline,
)
from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    ExecutionSnapshot,
    SceneTimelineMaster,
    TimelinePromptSegment,
)
from app.director_timeline_w46.generation.adapter import validate_against_capabilities
from app.director_timeline_w46.generation.reference_compile import apply_compiled_references
from app.director_timeline_w46.generation.registry import get_registry
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request
from app.director_timeline_w46.generation.speech_compile import (
    LIPSYNC_SPEAKER_REQUIRED,
    compile_speech_windows,
    extract_dialogue_cues,
    extract_dialogue_cues_from_text,
    lipsync_speaker_errors,
)
from app.lipsync_tracks import LipSyncClip, LipSyncTrack, LipSyncTracks
from app.scene_references import models as _sr_models  # noqa: F401
from app.scene_references import service
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-ref", name="Ref Test"))
    session.add(
        Asset(id="img-1", project_id="proj-ref", tag="Bar", kind="image", filename="bar.png", path="bar.png")
    )
    session.add(
        Asset(id="img-2", project_id="proj-ref", tag="Cup", kind="image", filename="cup.png", path="cup.png")
    )
    session.add(
        Asset(id="vid-1", project_id="proj-ref", tag="Pose", kind="video", filename="pose.mp4", path="pose.mp4")
    )
    session.add(
        Asset(id="aud-k", project_id="proj-ref", tag="KorriLine", kind="audio", filename="korri.wav", path="korri.wav")
    )
    session.add(
        Asset(id="aud-a", project_id="proj-ref", tag="AnaLine", kind="audio", filename="ana.wav", path="ana.wav")
    )
    session.commit()
    return session


def test_hydrate_overlaps_prompt_without_losing_timing():
    tl = DirectorTimeline(
        duration_sec=5,
        prompt_segments=[PromptSegment(id="p1", start=0, length=5, text="@Korri at the bar")],
        image_reference_clips=[
            TimelineClip(id="ir1", start=1, length=2, reference_binding_id="bind-img", asset_id="img-1")
        ],
        video_reference_clips=[
            TimelineClip(id="vr1", start=0, length=5, reference_binding_id="bind-vid", asset_id="vid-1")
        ],
    )
    hydrate_prompt_refs(tl)
    assert tl.prompt_refs_migrated is True
    assert len(tl.prompt_segments) == 1
    assert tl.prompt_segments[0].start == 0
    assert tl.prompt_segments[0].length == 5
    assert tl.prompt_segments[0].text == "@Korri at the bar"
    assert tl.prompt_segments[0].reference_binding_ids == ["bind-img", "bind-vid"]
    assert tl.image_reference_clips[0].start == 1
    assert tl.image_reference_clips[0].length == 2
    hydrate_prompt_refs(tl)
    assert len(tl.prompt_segments) == 1


def test_hydrate_creates_empty_prompt_when_no_overlap():
    tl = DirectorTimeline(
        duration_sec=8,
        prompt_segments=[PromptSegment(id="p1", start=0, length=2, text="intro")],
        image_reference_clips=[
            TimelineClip(id="ir1", start=4, length=3, reference_binding_id="bind-img", asset_id="img-1")
        ],
    )
    hydrate_prompt_refs(tl)
    assert len(tl.prompt_segments) == 2
    created = next(s for s in tl.prompt_segments if s.id != "p1")
    assert created.start == 4
    assert created.length == 3
    assert created.text == ""
    assert created.reference_binding_ids == ["bind-img"]
    hydrate_prompt_refs(tl)
    assert len(tl.prompt_segments) == 2


def test_parse_round_trip_is_idempotent():
    raw = dumps_director_timeline(
        DirectorTimeline(
            duration_sec=5,
            image_reference_clips=[
                TimelineClip(id="ir1", start=0, length=5, reference_binding_id="bind-a", asset_id="img-1")
            ],
        )
    )
    first = parse_director_timeline(raw)
    second = parse_director_timeline(dumps_director_timeline(first))
    assert len(first.prompt_segments) == 1
    assert len(second.prompt_segments) == 1
    assert first.prompt_segments[0].reference_binding_ids == ["bind-a"]
    assert second.prompt_segments[0].reference_binding_ids == ["bind-a"]


def test_minimax_caps_are_real_not_invented():
    registry = get_registry()
    t2v = registry.capabilities("minimax-h3-t2v-local")
    i2v = registry.capabilities("minimax-h3-i2v-local")
    assert t2v.supportsReferenceToVideo is True
    assert i2v.supportsReferenceToVideo is True
    assert t2v.maximumReferenceImages == 9
    assert i2v.maximumReferenceImages == 9


def test_request_builder_does_not_silent_drop_refs():
    batch = BatchBlock(
        sceneId="scene-1",
        generatorId="minimax-h3-t2v-local",
        duration=DurationState(plannedDuration=5),
        promptSegments=[TimelinePromptSegment(text="Korri stands in frame.", start=0, length=5)],
        references=[{"kind": "image", "role": "image_reference", "assetId": "img-1", "consumed": True}],
    )
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3-t2v-local")
    req = build_timeline_generation_request(
        project_id="proj-ref",
        scene_id="scene-1",
        batch=batch,
        snapshot=snap,
        fallback_allowed=False,
    )
    assert req.referenceAssetIds == ["img-1"]
    assert req.generationMode == "reference"
    slots = (req.providerOptions.get("r2v") or {}).get("slots") or []
    assert any(slot.get("assetId") == "img-1" for slot in slots)
    registry = get_registry()
    result = validate_against_capabilities(registry.capabilities("minimax-h3-t2v-local"), req)
    assert result.ok is True


def test_over_limit_keeps_ids_and_refuses(db=None):
    session = db or _db()
    b1 = service.attach(
        session,
        "proj-ref",
        {
            "asset_id": "img-1",
            "scope_type": "project",
            "scope_id": "proj-ref",
            "reference_type": "image",
            "media_kind": "image",
            "alias": "Bar",
        },
    )
    b2 = service.attach(
        session,
        "proj-ref",
        {
            "asset_id": "img-2",
            "scope_type": "project",
            "scope_id": "proj-ref",
            "reference_type": "image",
            "media_kind": "image",
            "alias": "Cup",
        },
    )
    timeline = DirectorTimeline(
        duration_sec=5,
        prompt_segments=[
            PromptSegment(
                start=0,
                length=5,
                text="Korri holds the cup at the bar.",
                reference_binding_ids=[b1["id"], b2["id"]],
            )
        ],
    )
    batch = BatchBlock(
        sceneId="scene-1",
        generatorId="minimax-h3-i2v-local",
        duration=DurationState(plannedDuration=5),
    )
    warnings = apply_compiled_references(batch, timeline, db=session, project_id="proj-ref")
    stored = [r["bindingId"] for r in batch.references if r.get("bindingId")]
    assert b1["id"] in stored and b2["id"] in stored
    assert not any(w["code"] == "IMAGE_REFERENCE_OVER_LIMIT" for w in warnings)
    # Phase A: H3 delivery uses Timed Prompt; ensure batch carries creator text.
    if not batch.promptSegments:
        batch.promptSegments = [
            TimelinePromptSegment(text="Korri holds the cup at the bar.", start=0, length=5)
        ]
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3-i2v-local")
    req = build_timeline_generation_request(
        project_id="proj-ref",
        scene_id="scene-1",
        batch=batch,
        snapshot=snap,
        fallback_allowed=False,
    )
    assert "img-1" in req.referenceAssetIds
    assert "img-2" in req.referenceAssetIds
    assert req.prompt
    result = validate_against_capabilities(get_registry().capabilities("minimax-h3-i2v-local"), req)
    assert result.ok is True
    session.close()


def test_lipsync_without_speaker_blocks():
    timeline = DirectorTimeline(
        duration_sec=5,
        lipsync=LipSyncTracks(
            tracks=[
                LipSyncTrack(
                    slot=1,
                    clips=[
                        LipSyncClip(start=0, length=2.5, audio_asset_id="aud-k", speaker_binding_id=None)
                    ],
                )
            ]
        ),
    )
    errors = lipsync_speaker_errors(timeline)
    assert errors
    assert errors[0]["message"] == LIPSYNC_SPEAKER_REQUIRED


def test_prompt_dialogue_requires_bound_token():
    prompt = PromptSegment(
        start=0,
        length=5,
        text='@Korri says "The usual." then someone else talks.',
        reference_binding_ids=["bind-korri"],
    )
    cues = extract_dialogue_cues(prompt, db=None, project_id=None)
    # Without db the alias cannot resolve — do not guess from display text.
    assert cues == []


def test_one_prompt_spanning_sequential_lipsync():
    timeline = DirectorTimeline(
        duration_sec=5,
        prompt_segments=[
            PromptSegment(
                id="p-shared",
                start=0,
                length=5,
                text="@Korri and @Anadriya work the bar.",
                reference_binding_ids=["bind-korri", "bind-ana"],
            )
        ],
        lipsync=LipSyncTracks(
            tracks=[
                LipSyncTrack(
                    slot=1,
                    clips=[
                        LipSyncClip(
                            id="ls-k",
                            start=0,
                            length=2.5,
                            audio_asset_id="aud-k",
                            speaker_binding_id="bind-korri",
                            character_id="char-korri",
                            character_name="Korri",
                        ),
                        LipSyncClip(
                            id="ls-a",
                            start=2.5,
                            length=2.5,
                            audio_asset_id="aud-a",
                            speaker_binding_id="bind-ana",
                            character_id="char-ana",
                            character_name="Anadriya",
                        ),
                    ],
                )
            ]
        ),
    )
    master = SceneTimelineMaster(
        sceneId="scene-1",
        batchBlocks=[
            BatchBlock(
                sceneId="scene-1",
                order=0,
                duration=DurationState(plannedDuration=5),
                promptSegments=[
                    TimelinePromptSegment(
                        start=0,
                        length=5,
                        text="@Korri and @Anadriya work the bar.",
                        referenceBindingIds=["bind-korri", "bind-ana"],
                    )
                ],
            )
        ],
    )
    windows, errors = compile_speech_windows(timeline, master=master)
    assert errors == []
    assert len(windows) == 2
    first, second = windows
    assert first["start"] == 0.0
    assert first["end"] == 2.5
    assert second["start"] == 2.5
    assert second["end"] == 5.0
    assert first["promptText"] == second["promptText"] == "@Korri and @Anadriya work the bar."
    assert first["referenceBindingIds"] == ["bind-korri", "bind-ana"]
    assert second["referenceBindingIds"] == ["bind-korri", "bind-ana"]
    assert first["speechKind"] == "lipsync_audio"
    assert second["speechKind"] == "lipsync_audio"
    assert first["speakers"][0]["speakerBindingId"] == "bind-korri"
    assert first["speakers"][0]["audioAssetId"] == "aud-k"
    assert second["speakers"][0]["speakerBindingId"] == "bind-ana"
    assert second["speakers"][0]["audioAssetId"] == "aud-a"
    assert first["speechKind"] != "prompt_dialogue"
    assert second["speechKind"] != "prompt_dialogue"


def test_lipsync_audio_beats_prompt_dialogue():
    timeline = DirectorTimeline(
        duration_sec=5,
        prompt_segments=[
            PromptSegment(
                start=0,
                length=5,
                text='@Korri says "hello from prompt tts"',
                reference_binding_ids=["bind-korri"],
            )
        ],
        lipsync=LipSyncTracks(
            tracks=[
                LipSyncTrack(
                    slot=1,
                    clips=[
                        LipSyncClip(
                            start=0,
                            length=5,
                            audio_asset_id="aud-k",
                            speaker_binding_id="bind-korri",
                        )
                    ],
                )
            ]
        ),
    )
    windows, errors = compile_speech_windows(timeline)
    assert errors == []
    assert len(windows) == 1
    assert windows[0]["speechKind"] == "lipsync_audio"
    assert windows[0]["speakers"][0]["audioAssetId"] == "aud-k"
    assert "hello from prompt tts" not in json.dumps(windows[0]["speakers"])


SCENE_12B_BATCH2 = """
[SHOT 6: Full Close Up on Anadriya]

Anadriya looks toward Korri with an annoyed expression and says:
"He asked me a question and you won't even let me talk!"

[SHOT 7: Medium Close Up on Korri]

Korri speaks fast and is very to the point as she says:
"Cuz what I say is what they're here for. Spit out a roast while there's still a decade, then you'll get some schnickin' air time, sis."

[SHOT 8: Over the Shoulder on Anadriya]

Anadriya grows more irritated and gives a stern like to Korri saying:
"Korri... language! And don't talk about Renkoka like the way you have."

[SHOT 9: Close Up on Korri]

Korri just smiles and remains confident as she says:
"Sorry sis, but Renkoka had you beat. She's my hero... with an ass that won't quit!"

[SHOT 10: Medium 2 Shot]

Anadriya tells her:
"Do I have to be the 'good' sister?"

[SHOT 11: Full Close Up on Korri]

Korri's eyes bulge and she hisses like a cat at Anadriya. Korri says nearly intimidated out of her mind:
"Put that away you soap psycho!"
"""


def _12b_bindings():
    return [
        {"bindingId": "bind-ana", "promptName": "Anadriya"},
        {"bindingId": "bind-korri", "promptName": "Korri"},
    ]


def test_cue_12b_let_me_talk_binds_anadriya_not_korri():
    """SLICE C: object name (toward Korri) must not steal Anadriya's line."""
    cues = extract_dialogue_cues_from_text(
        SCENE_12B_BATCH2,
        reference_name_bindings=_12b_bindings(),
    )
    let_me = [c for c in cues if "let me talk" in (c.get("text") or "")]
    assert let_me, "Anadriya let-me-talk line must be extracted"
    assert let_me[0]["speakerName"] == "Anadriya"
    assert let_me[0]["speakerBindingId"] == "bind-ana"
    assert let_me[0]["exactText"] == let_me[0]["text"]
    assert all(c["speakerName"] != "Korri" for c in let_me)


def test_cue_12b_batch2_speaker_exact_text_pairs():
    """SLICE C: each 12B batch-2 quoted line binds the speaking subject."""
    cues = extract_dialogue_cues_from_text(
        SCENE_12B_BATCH2,
        reference_name_bindings=_12b_bindings(),
    )
    by_text = {c["text"]: c["speakerName"] for c in cues}
    assert by_text["He asked me a question and you won't even let me talk!"] == "Anadriya"
    assert by_text["Put that away you soap psycho!"] == "Korri"
    assert "Cuz what I say is what they're here for. Spit out a roast while there's still a decade, then you'll get some schnickin' air time, sis." in by_text
    assert by_text["Cuz what I say is what they're here for. Spit out a roast while there's still a decade, then you'll get some schnickin' air time, sis."] == "Korri"
    assert by_text.get("Do I have to be the 'good' sister?") == "Anadriya"
    # Korri mentioned as object of "to Korri saying" is not the speaker.
    lang = [c for c in cues if "language" in (c.get("text") or "").lower()]
    assert lang and lang[0]["speakerName"] == "Anadriya"


def test_cue_whispers_to_korri_stays_anadriya():
    """SLICE C: 'whispers to Korri saying' subject is Anadriya."""
    text = (
        'Anadriya is embarrassed and whispers to Korri saying\n'
        '"You\'re so rude."'
    )
    cues = extract_dialogue_cues_from_text(
        text,
        reference_name_bindings=_12b_bindings(),
    )
    assert len(cues) == 1
    assert cues[0]["speakerName"] == "Anadriya"
    assert cues[0]["text"] == "You're so rude."


def test_cue_canonical_at_token_still_binds():
    cues = extract_dialogue_cues_from_text(
        '@Korri says "Renkoka obviously!"',
        reference_name_bindings=_12b_bindings(),
    )
    assert len(cues) == 1
    assert cues[0]["speakerName"] == "Korri"
    assert cues[0]["text"] == "Renkoka obviously!"


def test_scene_level_timed_prompt_defers_speech_to_extension_window():
    """30s Timed Prompt: Batch 1 (0-15) is setup; Batch 2 (15-30) owns the spoken line."""
    timeline = DirectorTimeline(
        duration_sec=30,
        prompt_segments=[
            PromptSegment(
                id="ps-scene",
                start=0,
                length=30,
                text='Cade O\'Connor says in a deep voice: "Where is the Adept?"',
                reference_name_bindings=[
                    {"bindingId": "bind-cade", "promptName": "Cade O'Connor"},
                    {"bindingId": "bind-cade", "promptName": "Cade"},
                ],
            )
        ],
    )
    master = SceneTimelineMaster(
        sceneId="scene-1",
        batchBlocks=[
            BatchBlock(
                sceneId="scene-1",
                order=0,
                duration=DurationState(plannedDuration=30),
                promptSegments=[
                    TimelinePromptSegment(
                        start=0,
                        length=30,
                        text='Cade O\'Connor says in a deep voice: "Where is the Adept?"',
                        referenceNameBindings=[
                            {"bindingId": "bind-cade", "promptName": "Cade O'Connor"},
                            {"bindingId": "bind-cade", "promptName": "Cade"},
                        ],
                    )
                ],
            )
        ],
    )
    first, err1 = compile_speech_windows(timeline, window_start=0.0, window_end=15.0, master=master)
    second, err2 = compile_speech_windows(timeline, window_start=15.0, window_end=30.0, master=master)
    assert err1 == [] and err2 == []
    assert first
    assert all(w["speechKind"] != "prompt_dialogue" for w in first)
    assert any(w["speechKind"] == "prompt_dialogue" for w in second)
    spoken = [s.get("text") or "" for w in second for s in (w.get("speakers") or [])]
    assert any("Adept" in line for line in spoken)





def test_cue_screenplay_korri_name_then_line():
    """Screenplay NAME + spoken line (no quotes) must bind dialogue."""
    text = (
        "Morning light in Schnick Coffee.\n"
        "KORRI\n"
        "Hello, welcome to Schnick Coffee.\n"
        "She smiles at the camera.\n"
    )
    cues = extract_dialogue_cues_from_text(
        text,
        reference_name_bindings=[{"bindingId": "bind-korri", "promptName": "Korri"}],
    )
    assert cues, "screenplay KORRI cue must extract spoken line"
    assert cues[0]["speakerName"].lower() == "korri"
    assert "welcome to Schnick Coffee" in cues[0]["text"]
    assert cues[0].get("exactText") == cues[0]["text"] or cues[0].get("exactText") == cues[0].get("text")


def test_cue_screenplay_two_speakers():
    text = (
        "KORRI\n"
        "What can I get you?\n"
        "\n"
        "ANADRIYA\n"
        "(dry)\n"
        "Anything but schnickin' silence.\n"
    )
    cues = extract_dialogue_cues_from_text(
        text,
        reference_name_bindings=[
            {"bindingId": "bind-korri", "promptName": "Korri"},
            {"bindingId": "bind-ana", "promptName": "Anadriya"},
        ],
    )
    by = {c["speakerName"].lower(): c["text"] for c in cues}
    assert "korri" in by and "What can I get you?" in by["korri"]
    assert "anadriya" in by and "silence" in by["anadriya"].lower()
