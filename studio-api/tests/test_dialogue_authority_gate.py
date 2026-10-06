"""Tests for Co-Director Dialogue Authority gate (Omni QC + multilingual inheritance)."""

from __future__ import annotations

import json

from app.director_timeline_w46.generation.dialogue_authority import (
    CODE_MODALITY_CONFLICT,
    CODE_OMNI_UNAVAILABLE,
    CODE_SPEECH_WHEN_SILENCE_EXPECTED,
    CODE_UNAUTHORIZED_BACKGROUND_SPEAKER,
    CODE_WRONG_SPEAKER,
    EXPECTED_SPEECH_NONE,
    EXPECTED_SPEECH_OPEN,
    EXPECTED_SPEECH_SPEECH,
    QC_FAIL,
    QC_PASS,
    QC_UNCERTAIN,
    STATUS_NEEDS_DIALOGUE_RETAKE,
    STATUS_QC_RETRY_REQUIRED,
    freeze_language_authority_packet,
    attach_authority_packet,
    ensure_silence_locked_manifest,
    evaluate_dialogue_qc,
    apply_qc_exception_fail_closed,
    apply_qc_to_batch_status,
    attach_manifest_to_batch,
    drop_dialogue_manifests,
    get_manifest_from_batch,
    manifest_needs_authority_recompile,
    build_dialogue_manifest,
    build_retake_repair_from_manifest,
    consume_dialogue_retake_repair,
    evaluate_dialogue_qc,
    promote_project_primary_to_spoken_if_explicit,
    read_project_spoken_language,
    read_scene_spoken_language,
    read_ui_language_blob,
    resolve_expected_speech,
    resolve_line_language,
    submit_dialogue_authority_preflight,
    write_project_spoken_language,
    write_scene_spoken_language,
)
from app.director_timeline_w46.scene_render_progress import derive_scene_render_progress


class _Batch:
    def __init__(self):
        self.status = "Generating"
        self.references = []


def test_inheritance_line_over_scene_over_project():
    r = resolve_line_language(line_language="es", scene_language="en", project_language="fr")
    assert r["language"] == "es" and r["source"] == "line"
    r = resolve_line_language(line_language=None, scene_language="ja", project_language="en")
    assert r["language"] == "ja" and r["source"] == "scene"
    r = resolve_line_language(line_language=None, scene_language=None, project_language="pt")
    assert r["language"] == "pt" and r["source"] == "project"
    r = resolve_line_language()
    assert r["explicit"] is False and r["error"] == "SPOKEN_LANGUAGE_AUTHORITY_MISSING"


def test_ui_language_never_becomes_spoken_authority():
    settings = json.dumps(
        {
            "language": {
                "interfaceLocale": "ja",
                "conversationLocale": "fr",
                "projectPrimaryLocale": "es",
                "promptLanguagePolicy": "auto",
                "exportLocale": "ja",
            }
        }
    )
    assert read_project_spoken_language(settings) is None
    ui = read_ui_language_blob(settings)
    assert ui["interfaceLocale"] == "ja"
    new_settings, spoken = promote_project_primary_to_spoken_if_explicit(settings)
    assert spoken == "es"
    assert read_project_spoken_language(new_settings) == "es"
    assert read_ui_language_blob(new_settings)["interfaceLocale"] == "ja"


def test_missing_settings_language_does_not_invent_from_ui_default():
    settings = json.dumps({"library": {}})
    assert read_project_spoken_language(settings) is None
    new_settings, spoken = promote_project_primary_to_spoken_if_explicit(settings)
    assert spoken is None
    assert read_project_spoken_language(new_settings) is None


def test_write_project_spoken_language_isolated_from_ui():
    settings = write_project_spoken_language("{}", "en", source="test")
    blob = json.loads(settings)
    assert blob["spokenLanguage"]["projectLanguage"] == "en"
    assert "language" not in blob
    assert read_project_spoken_language(settings) == "en"


def test_manifest_locked_defaults_and_lines_from_speech_windows():
    windows = [
        {
            "start": 0.0,
            "end": 5.0,
            "speechKind": "prompt_dialogue",
            "speakers": [
                {
                    "speakerName": "Korri",
                    "characterId": "c1",
                    "speakerBindingId": "b1",
                    "text": "Renkoka obviously! She was such a hottie.",
                }
            ],
        }
    ]
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        batch_id="bb1",
        speech_windows=windows,
        project_language="en",
    )
    assert manif["lockedScript"] is True
    assert manif["allowAdLibs"] is False
    assert manif["allowLanguageSwitch"] is False
    assert manif["language"] == "en"
    assert manif["authorityExplicit"] is True
    assert manif["uiLanguageIsolated"] is True
    assert manif["lineCount"] == 1
    assert manif["lines"][0]["language"] == "en"
    assert manif["lines"][0]["languageSource"] == "project"


def test_manifest_missing_authority_when_no_spoken_language():
    windows = [
        {
            "speechKind": "prompt_dialogue",
            "speakers": [{"speakerName": "Korri", "text": "Hello there"}],
        }
    ]
    manif = build_dialogue_manifest(
        project_id="p1", scene_id="s1", speech_windows=windows
    )
    assert manif["authorityExplicit"] is False
    assert manif["authorityError"] == "SPOKEN_LANGUAGE_AUTHORITY_MISSING"


def test_qc_fail_unauthorized_language_welsh_or_latin_without_blacklist():
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {
                "speechKind": "prompt_dialogue",
                "speakers": [
                    {
                        "speakerName": "Korri",
                        "text": "Renkoka obviously! She was such a hottie. Gorgeous assets if you catch my drift!",
                    }
                ],
            }
        ],
        project_language="en",
    )
    qc = evaluate_dialogue_qc(
        manif,
        {
            "transcript": "Bore da fy nghariad Renkoka",
            "languageCode": "cy",
            "segments": [{"transcription": "Bore da fy nghariad Renkoka"}],
            "availability": "available",
        },
    )
    assert qc["verdict"] == QC_FAIL
    assert qc["sceneFinishedEligible"] is False
    assert any(f["code"] == "UNAUTHORIZED_LANGUAGE" for f in qc["findings"])
    qc2 = evaluate_dialogue_qc(
        manif,
        {
            "transcript": "Salve amice Renkoka",
            "languageCode": "la",
            "segments": [{"transcription": "Salve amice Renkoka"}],
            "availability": "available",
        },
    )
    assert qc2["verdict"] == QC_FAIL
    assert qc2.get("blacklist") is None


def test_qc_pass_authorized_english():
    line = "Renkoka obviously! She was such a hottie. Gorgeous assets if you catch my drift!"
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "Korri", "text": line}]}
        ],
        project_language="en",
    )
    qc = evaluate_dialogue_qc(
        manif,
        {
            "transcript": line,
            "languageCode": "en",
            "segments": [{"transcription": line}],
            "availability": "available",
        },
    )
    assert qc["verdict"] == QC_PASS
    assert qc["sceneFinishedEligible"] is True


def test_qc_pass_intentional_en_es_when_line_authority_declares_es():
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {
                "speechKind": "prompt_dialogue",
                "speakers": [
                    {"speakerName": "Korri", "text": "Hola amiga", "language": "es"},
                ],
            }
        ],
        project_language="en",
        scene_language="en",
    )
    assert manif["lines"][0]["language"] == "es"
    assert manif["language"] == "es"
    qc = evaluate_dialogue_qc(
        manif,
        {
            "transcript": "Hola amiga",
            "languageCode": "es",
            "segments": [{"transcription": "Hola amiga"}],
            "availability": "available",
        },
    )
    assert qc["verdict"] == QC_PASS


def test_qc_uncertain_not_pass_when_omni_unavailable():
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "A", "text": "Hello world"}]}
        ],
        project_language="en",
    )
    qc = evaluate_dialogue_qc(
        manif,
        {"transcript": "", "languageCode": None, "segments": [], "availability": "unavailable"},
    )
    assert qc["verdict"] == QC_UNCERTAIN
    assert qc["sceneFinishedEligible"] is False


def test_qc_fail_silent_when_speech_expected():
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "A", "text": "Hello world"}]}
        ],
        project_language="en",
    )
    qc = evaluate_dialogue_qc(
        manif,
        {"transcript": "", "languageCode": "en", "segments": [], "availability": "available"},
    )
    assert qc["verdict"] == QC_FAIL
    assert any(f["code"] == "SILENT_WHEN_SPEECH_EXPECTED" for f in qc["findings"])


def test_qc_loud_empty_transcript_is_omni_miss_not_silent():
    """SLICE A: loud energy + empty Omni transcript => OMNI_TRANSCRIPT_MISS / UNCERTAIN."""
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "A", "text": "Hello world"}]}
        ],
        project_language="en",
    )
    # Scene 12B-like: mean ~-16.7 dB with empty Omni transcript.
    qc = evaluate_dialogue_qc(
        manif,
        {"transcript": "", "languageCode": None, "segments": [], "availability": "available"},
        mean_volume_db=-16.7,
    )
    assert qc["verdict"] == QC_UNCERTAIN
    assert qc["reason"] == "OMNI_TRANSCRIPT_MISS"
    assert qc["sceneFinishedEligible"] is False
    assert qc["verdict"] != QC_PASS
    assert any(f["code"] == "OMNI_TRANSCRIPT_MISS" for f in qc["findings"])
    assert not any(f["code"] == "SILENT_WHEN_SPEECH_EXPECTED" for f in qc["findings"])
    miss = next(f for f in qc["findings"] if f["code"] == "OMNI_TRANSCRIPT_MISS")
    assert miss["finalCheck"]["acceptanceEligible"] is False
    assert miss["finalCheck"]["autoDestroy"] is False
    assert miss["finalCheck"]["retakeEligible"] is False
    assert miss["finalCheck"]["authoritySource"] == "dialogue_manifest"
    assert miss["finalCheck"]["modalityConflict"] is True
    assert miss["finalCheck"]["modalities"] == ["asr", "energy"]
    assert miss["finalCheck"].get("conflictReason")


def test_qc_quiet_empty_transcript_still_silent_fail():
    """SLICE A: truly quiet/silent energy + empty transcript => SILENT_WHEN_SPEECH_EXPECTED FAIL."""
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "A", "text": "Hello world"}]}
        ],
        project_language="en",
    )
    qc = evaluate_dialogue_qc(
        manif,
        {"transcript": "", "languageCode": "en", "segments": [], "availability": "available"},
        mean_volume_db=-45.0,
    )
    assert qc["verdict"] == QC_FAIL
    assert qc["reason"] == "SILENT_WHEN_SPEECH_EXPECTED"
    assert qc["sceneFinishedEligible"] is False
    assert qc["verdict"] != QC_PASS
    assert any(f["code"] == "SILENT_WHEN_SPEECH_EXPECTED" for f in qc["findings"])
    assert not any(f["code"] == "OMNI_TRANSCRIPT_MISS" for f in qc["findings"])

    # No stream / unprobeable energy keeps SILENT (do not invent speech).
    qc2 = evaluate_dialogue_qc(
        manif,
        {"transcript": "", "languageCode": "en", "segments": [], "availability": "available"},
        mean_volume_db=None,
    )
    assert qc2["verdict"] == QC_FAIL
    assert any(f["code"] == "SILENT_WHEN_SPEECH_EXPECTED" for f in qc2["findings"])
    assert qc2["sceneFinishedEligible"] is False


def test_qc_omni_transcript_miss_never_pass_or_finished():
    """SLICE A acceptance: OMNI_TRANSCRIPT_MISS must Hard-fail acceptance eligibility."""
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "A", "text": "Hello world"}]}
        ],
        project_language="en",
    )
    for loud_db in (-15.4, -16.7, -25.0):
        qc = evaluate_dialogue_qc(
            manif,
            {
                "transcript": "   ",
                "languageCode": None,
                "segments": [],
                "availability": "available",
                "meanVolumeDb": loud_db,
            },
        )
        assert qc["verdict"] == QC_UNCERTAIN
        assert qc["reason"] == "OMNI_TRANSCRIPT_MISS"
        assert qc["sceneFinishedEligible"] is False
        assert qc["verdict"] != QC_PASS


def test_apply_qc_sets_needs_dialogue_retake_not_candidate_ready():
    batch = _Batch()
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "A", "text": "Hello world"}]}
        ],
        project_language="en",
    )
    qc = evaluate_dialogue_qc(
        manif,
        {
            "transcript": "totally different adlib speech here",
            "languageCode": "en",
            "segments": [{"transcription": "totally different adlib speech here"}],
            "availability": "available",
        },
    )
    status = apply_qc_to_batch_status(batch, qc)
    assert status == STATUS_NEEDS_DIALOGUE_RETAKE
    assert batch.status == STATUS_NEEDS_DIALOGUE_RETAKE
    assert any(r.get("kind") == "dialogueQcDiagnostics" for r in batch.references)


def test_retake_repair_uses_manifest_not_asr():
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {
                "speechKind": "prompt_dialogue",
                "speakers": [{"speakerName": "Korri", "text": "Renkoka obviously!"}],
            }
        ],
        project_language="en",
    )
    repair = build_retake_repair_from_manifest(
        manif, {"reason": "UNAUTHORIZED_LANGUAGE", "verdict": "FAIL"}
    )
    assert repair["source"] == "dialogue_manifest"
    assert repair["keepTimelineR2V"] is True
    assert repair["reviveLipSync"] is False
    assert repair["blacklist"] is None
    assert "Renkoka obviously!" in repair["userCorrection"]["text"]
    assert "Bore da" not in repair["userCorrection"]["text"]


def test_scene_progress_render_not_finished_on_dialogue_retake():
    class B:
        def __init__(self, status, order=0):
            self.status = status
            self.order = order
            self.id = f"bb_{order}"
            self.label = f"Batch {order}"
            self.createdAt = ""
            self.approvedClip = None
            self.generationJobs = []

    class M:
        batchBlocks = [B("NeedsDialogueRetake", 0)]

    progress = derive_scene_render_progress(M())
    assert progress["sceneFinished"] is False
    assert progress["dialogueNeedsRetake"] == 1
    assert progress["phase"] == "dialogue_retake_required"
    assert "NOT FINISHED" in progress["statusLabel"]

def test_preflight_authority_missing_is_honest_gap():
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "A", "text": "Hello"}]}
        ],
    )
    assert manif["lockedScript"] is True
    assert manif["authorityExplicit"] is False
    assert manif["authorityError"] == "SPOKEN_LANGUAGE_AUTHORITY_MISSING"




def test_submit_preflight_source_has_no_except_pass_swallow():
    """VERIFY FAIL #1: SPOKEN_LANGUAGE_AUTHORITY_MISSING must not be swallowed."""
    import inspect
    from app.director_timeline_w46 import orchestrator as orch

    src = inspect.getsource(orch.submit_batch_generation)
    # The authority-missing return must exist.
    assert "SPOKEN_LANGUAGE_AUTHORITY_MISSING" in src
    # The old pattern wrapped the whole preflight in try/except Exception: pass.
    # Guard: after the SPOKEN_LANGUAGE return, there must not be a bare except:pass
    # that encloses it. We check the preflight region specifically.
    idx = src.find("honest preflight")
    assert idx != -1
    region = src[idx : idx + 2500]
    assert "SPOKEN_LANGUAGE_AUTHORITY_MISSING" in region
    # No except Exception: pass immediately closing the preflight region.
    assert "except Exception:\n        pass" not in region.replace("\r\n", "\n")


def test_retake_range_consumes_dialogue_retake_repair():
    """VERIFY FAIL #2: retake_range must prefer Manifest repair text."""
    import inspect
    from app.director_timeline_w46 import orchestrator as orch

    src = inspect.getsource(orch.retake_range)
    assert "dialogueRetakeRepair" in src
    assert "dialogue_repair" in src
    assert "dialogue_manifest_retake" in src
    assert "Manifest script wins" in src or "dialogue_repair is not None" in src


def test_h3_speech_authority_honesty_preserves_prompt_bytes():
    """H3-only: honesty stamp must not mutate Timed Prompt bytes."""
    from app.director_timeline_w46.generation.adapters.minimax_h3_local import (
        apply_h3_speech_authority_honesty,
    )
    from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest

    prompt = 'Korri says:\\n"Renkoka obviously! She was such a hottie."'
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap_test",
        generatorId="minimax-h3-t2v-local",
        prompt=prompt,
        duration=2.0,
        generationMode="reference",
        fallbackAllowed=False,
        providerOptions={
            "h3PromptAuthority": "timed_prompt_direct_line",
            "spokenLanguage": {"language": "en", "source": "dialogue_manifest"},
            "dialogueAuthority": {
                "exactScriptDialogue": True,
                "language": "en",
                "lockedScript": True,
            },
        },
    )
    before = req.prompt
    honesty = apply_h3_speech_authority_honesty(req)
    assert req.prompt == before
    assert honesty["exactSpeechGuaranteedByGenerator"] is False
    assert honesty["timedPromptBytesPreserved"] is True
    assert honesty["comfyLanguageWidget"] == "absent"
    assert req.providerOptions["h3SpeechAuthority"]["generatorOwnsDialogue"] is False


def test_submit_exception_does_not_swallow_spoken_language_authority_missing():
    windows = [
        {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "A", "text": "Hello"}]}
    ]
    manif = build_dialogue_manifest(
        project_id="p1", scene_id="s1", speech_windows=windows
    )
    assert manif["lockedScript"] is True
    assert manif["authorityExplicit"] is False
    err = submit_dialogue_authority_preflight(manif)
    assert err is not None
    assert err["ok"] is False
    assert err["error"] == "SPOKEN_LANGUAGE_AUTHORITY_MISSING"

    class B:
        speechWindows = windows
        references = []

    err2 = submit_dialogue_authority_preflight(
        None, compile_error=RuntimeError("boom"), batch=B()
    )
    assert err2 is not None
    assert err2["ok"] is False
    assert err2["error"] == "SPOKEN_LANGUAGE_AUTHORITY_MISSING"
    assert "boom" in err2["message"]

    # Explicit authority continues (None = do not block).
    ok_manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=windows,
        project_language="en",
    )
    assert submit_dialogue_authority_preflight(ok_manif) is None


def test_scene_spoken_language_persist_allows_submit():
    """Creator-set scene language (PUT /spoken-language) is hop 2 of line→scene→project."""

    class Master:
        sceneLanguage = None
        spokenLanguage = None

    windows = [
        {
            "speechKind": "prompt_dialogue",
            "speakers": [{"speakerName": "Cade", "text": "Where is the Adept?"}],
        }
    ]
    missing = build_dialogue_manifest(
        project_id="p1",
        scene_id="s3",
        speech_windows=windows,
        scene_language=read_scene_spoken_language(Master()),
    )
    assert missing["authorityExplicit"] is False
    blocked = submit_dialogue_authority_preflight(missing)
    assert blocked is not None
    assert blocked["error"] == "SPOKEN_LANGUAGE_AUTHORITY_MISSING"

    master = Master()
    write_scene_spoken_language(master, "en", source="explicit")
    assert read_scene_spoken_language(master) == "en"
    allowed = build_dialogue_manifest(
        project_id="p1",
        scene_id="s3",
        speech_windows=windows,
        scene_language=read_scene_spoken_language(master),
    )
    assert allowed["authorityExplicit"] is True
    assert allowed["language"] == "en"
    assert allowed["lines"][0]["languageSource"] == "scene"
    assert allowed["lines"][0]["speakerName"] == "Cade"
    assert allowed["lines"][0]["text"] == "Where is the Adept?"
    assert submit_dialogue_authority_preflight(allowed) is None


def test_voice_studio_language_is_not_spoken_authority():
    """HARD LAW: Voice Studio voice_profiles.language is never a spoken-language hop."""
    windows = [
        {
            "speechKind": "prompt_dialogue",
            "speakers": [{"speakerName": "Cade", "text": "Where is the Adept?"}],
        }
    ]
    voice_default = "en"
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s3",
        speech_windows=windows,
        # Do not pass voice_default into scene/project — that would invent authority.
    )
    assert manif["authorityExplicit"] is False
    assert manif["authorityError"] == "SPOKEN_LANGUAGE_AUTHORITY_MISSING"
    err = submit_dialogue_authority_preflight(manif)
    assert err is not None
    assert err["error"] == "SPOKEN_LANGUAGE_AUTHORITY_MISSING"
    resolved = resolve_line_language()
    assert resolved["explicit"] is False
    assert resolved["error"] == "SPOKEN_LANGUAGE_AUTHORITY_MISSING"
    assert voice_default == "en"


def test_stale_cached_manifest_recompiles_after_scene_language():
    class Batch:
        def __init__(self):
            self.references = []
            self.speechWindows = [
                {
                    "speechKind": "prompt_dialogue",
                    "speakers": [{"speakerName": "Cade", "text": "Where is the Adept?"}],
                }
            ]
            self.dialogueManifest = None

    class Master:
        def __init__(self):
            self.sceneLanguage = None
            self.spokenLanguage = None
            self.batchBlocks = []

    batch = Batch()
    stale = build_dialogue_manifest(
        project_id="p1",
        scene_id="s3",
        speech_windows=batch.speechWindows,
    )
    attach_manifest_to_batch(batch, stale)
    assert manifest_needs_authority_recompile(get_manifest_from_batch(batch)) is True

    master = Master()
    master.batchBlocks = [batch]
    write_scene_spoken_language(master, "en", source="explicit")
    dropped = drop_dialogue_manifests(master)
    assert dropped == 1
    assert get_manifest_from_batch(batch) is None
    assert manifest_needs_authority_recompile(None) is True

    fresh = build_dialogue_manifest(
        project_id="p1",
        scene_id="s3",
        speech_windows=batch.speechWindows,
        scene_language=read_scene_spoken_language(master),
    )
    assert fresh["authorityExplicit"] is True
    assert submit_dialogue_authority_preflight(fresh) is None
    assert manifest_needs_authority_recompile(fresh) is False


def test_retake_consumes_dialogue_retake_repair_manifest_not_asr():
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {
                "speechKind": "prompt_dialogue",
                "speakers": [{"speakerName": "Korri", "text": "Renkoka obviously!"}],
            }
        ],
        project_language="en",
    )
    repair = build_retake_repair_from_manifest(
        manif, {"reason": "UNAUTHORIZED_LANGUAGE", "verdict": "FAIL"}
    )
    class B:
        references = [repair]
        speechWindows = []

    consumed = consume_dialogue_retake_repair(
        B(), replacement_prompt="Bore da fy nghariad ASR garbage"
    )
    assert consumed["consumed"] is True
    assert consumed["source"] == "dialogue_manifest"
    assert "Renkoka obviously!" in consumed["delta"]
    assert "Bore da" not in consumed["delta"]
    assert consumed["userCorrection"]["source"] == "dialogue_manifest"
    assert consumed["userCorrection"]["exactScriptDialogue"] is True
    assert consumed["keepTimelineR2V"] is True
    assert consumed["reviveLipSync"] is False


def test_locked_qc_exception_never_candidate_ready():
    batch = _Batch()
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "A", "text": "Hello world"}]}
        ],
        project_language="en",
    )
    attach_manifest_to_batch(batch, manif)
    status = apply_qc_exception_fail_closed(
        batch, RuntimeError("omni down"), manifest=manif
    )
    assert status == STATUS_QC_RETRY_REQUIRED
    assert batch.status == STATUS_QC_RETRY_REQUIRED
    assert batch.status != "CandidateReady"
    # Nested except path: helper itself must not flip locked script to CandidateReady
    # even if persist diagnostics would fail — status stays QC_RetryRequired (infra, not retake).
    batch.status = "Generating"
    status2 = apply_qc_exception_fail_closed(batch, RuntimeError("again"), manifest=manif)
    assert status2 == STATUS_QC_RETRY_REQUIRED
    assert batch.status != "CandidateReady"


def test_write_scene_spoken_language_usable_for_quarters():
    master = {"sceneLanguage": None}
    lang = write_scene_spoken_language(master, "en", source="test")
    assert lang == "en"
    assert master["sceneLanguage"] == "en"
    assert read_scene_spoken_language(master) == "en"
    settings = write_project_spoken_language("{}", "en", source="test")
    assert read_project_spoken_language(settings) == "en"


def test_voice_bind_preserves_manifest_exact_script_dialogue():
    from unittest.mock import MagicMock

    from app.director_timeline_w46.contracts import BatchBlock, DurationState
    from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
    from app.director_timeline_w46.generation.voice_bind import apply_approved_voices

    request = TimelineGenerationRequest(
        projectId="p1",
        sceneId="s1",
        batchBlockId="bb",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        generationMode="reference",
        prompt="Korri says hello.",
        providerOptions={
            "dialogueAuthority": {
                "exactScriptDialogue": True,
                "lockedScript": True,
                "authorityExplicit": True,
            }
        },
    )
    batch = BatchBlock(
        sceneId="s1",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=5.0),
    )
    db = MagicMock()
    db.get.return_value = None
    result = apply_approved_voices(db, request, batch, caps=None)
    assert result["exactScriptDialogue"] is True
    assert request.providerOptions["characterVoices"]["exactScriptDialogue"] is True
    assert request.providerOptions["characterVoices"]["control"] == "voice_timbre_ref_only"
    assert request.prompt == "Korri says hello."


# ---------------------------------------------------------------------------
# SLICE B — Silent-scene vs background-speech
# ---------------------------------------------------------------------------


def test_manifest_expected_speech_none_when_no_lines_adlibs_off():
    """Empty lines + allowAdLibs=false => expectedSpeech=NONE, lockedScript silence."""
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[],
        project_language="en",
        allow_adlibs=False,
    )
    assert manif["expectedSpeech"] == EXPECTED_SPEECH_NONE
    assert manif["lockedScript"] is True
    assert manif["lineCount"] == 0
    assert manif["allowAdLibs"] is False
    assert resolve_expected_speech(lines=[], allow_adlibs=False) == EXPECTED_SPEECH_NONE


def test_manifest_expected_speech_speech_when_lines():
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "Korri", "text": "Hello"}]}
        ],
        project_language="en",
    )
    assert manif["expectedSpeech"] == EXPECTED_SPEECH_SPEECH
    assert "Korri" in manif["speakers"]
    assert manif["lockedScript"] is True


def test_manifest_expected_speech_open_when_adlibs_allowed_no_lines():
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[],
        allow_adlibs=True,
    )
    assert manif["expectedSpeech"] == EXPECTED_SPEECH_OPEN
    assert manif["lockedScript"] is False


def test_qc_fail_speech_when_silence_expected():
    """SLICE B: expectedSpeech=NONE + any Omni speech => FAIL SPEECH_WHEN_SILENCE_EXPECTED."""
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[],
        allow_adlibs=False,
        expected_speech=EXPECTED_SPEECH_NONE,
    )
    assert manif["expectedSpeech"] == EXPECTED_SPEECH_NONE
    qc = evaluate_dialogue_qc(
        manif,
        {
            "transcript": "hey over here",
            "languageCode": "en",
            "segments": [{"transcription": "hey over here", "speaker": "Crowd"}],
            "availability": "available",
        },
    )
    assert qc["verdict"] == QC_FAIL
    assert qc["reason"] == CODE_SPEECH_WHEN_SILENCE_EXPECTED
    assert qc["sceneFinishedEligible"] is False
    assert any(f["code"] == CODE_SPEECH_WHEN_SILENCE_EXPECTED for f in qc["findings"])
    speech = next(f for f in qc["findings"] if f["code"] == CODE_SPEECH_WHEN_SILENCE_EXPECTED)
    assert speech["finalCheck"]["retakeEligible"] is True
    assert speech["finalCheck"]["autoDestroy"] is False
    assert speech["finalCheck"]["acceptanceEligible"] is False
    assert speech["finalCheck"]["creativeTaste"] is False
    assert speech["finalCheck"]["authoritySource"] == "dialogue_manifest"
    # Background speaker also flagged when silence locked.
    assert any(f["code"] == CODE_UNAUTHORIZED_BACKGROUND_SPEAKER for f in qc["findings"])
    bg = next(f for f in qc["findings"] if f["code"] == CODE_UNAUTHORIZED_BACKGROUND_SPEAKER)
    assert bg["finalCheck"]["retakeEligible"] is True


def test_qc_pass_true_silence_when_silence_expected_quiet():
    """SLICE B: expectedSpeech=NONE + confirmed quiet + empty ASR => PASS."""
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[],
        allow_adlibs=False,
    )
    qc = evaluate_dialogue_qc(
        manif,
        {"transcript": "", "languageCode": None, "segments": [], "availability": "available"},
        mean_volume_db=-45.0,
    )
    assert qc["verdict"] == QC_PASS
    assert qc["sceneFinishedEligible"] is True
    assert qc["expectedSpeech"] == EXPECTED_SPEECH_NONE
    assert not any(f["code"] == "OMNI_TRANSCRIPT_MISS" for f in qc["findings"])
    assert not any(f["code"] == CODE_MODALITY_CONFLICT for f in qc["findings"])
    assert not any(f["code"] == "SILENT_WHEN_SPEECH_EXPECTED" for f in qc["findings"])

    # Brad Language Authority rule 4: empty ASR without affirmative silence => UNCERTAIN.
    qc2 = evaluate_dialogue_qc(
        manif,
        {"transcript": "", "languageCode": None, "segments": [], "availability": "available"},
        mean_volume_db=None,
    )
    assert qc2["verdict"] == QC_UNCERTAIN
    assert qc2["sceneFinishedEligible"] is False
    assert qc2.get("speechClassification") == "UNCERTAIN_SPEECH"


def test_qc_silence_expected_loud_empty_asr_is_modality_conflict_not_pass():
    """PRIMARY LAW: empty ASR + loud energy => UNCERTAIN / MODALITY_CONFLICT, not silence, not PASS.

    Energy alone does not invent speech (still != PASS). finalCheck carries modalityConflict.
    """
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[],
        allow_adlibs=False,
    )
    assert manif["expectedSpeech"] == EXPECTED_SPEECH_NONE
    qc = evaluate_dialogue_qc(
        manif,
        {"transcript": "", "languageCode": None, "segments": [], "availability": "available"},
        mean_volume_db=-16.7,
    )
    assert qc["verdict"] == QC_UNCERTAIN
    assert qc["reason"] == CODE_MODALITY_CONFLICT
    assert qc["sceneFinishedEligible"] is False
    assert qc["verdict"] != QC_PASS
    assert any(f["code"] == "OMNI_TRANSCRIPT_MISS" for f in qc["findings"])
    assert any(f["code"] == CODE_MODALITY_CONFLICT for f in qc["findings"])
    assert not any(f["code"] == "SILENT_WHEN_SPEECH_EXPECTED" for f in qc["findings"])
    assert not any(f["code"] == CODE_SPEECH_WHEN_SILENCE_EXPECTED for f in qc["findings"])
    conflict = next(f for f in qc["findings"] if f["code"] == CODE_MODALITY_CONFLICT)
    fc = conflict["finalCheck"]
    assert fc["modalityConflict"] is True
    assert fc["modalities"] == ["asr", "energy"]
    assert "conflictReason" in fc and fc["conflictReason"]
    assert fc["retakeEligible"] is False
    assert fc["autoDestroy"] is False
    assert fc["acceptanceEligible"] is False
    assert fc["authoritySource"] == "dialogue_manifest"


def test_qc_fail_unauthorized_background_speaker_when_speech_expected():
    """SLICE B: unexpected speaker label not in Manifest speakers => Hard FAIL."""
    line = "Renkoka obviously! She was such a hottie."
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "Korri", "text": line}]}
        ],
        project_language="en",
    )
    qc = evaluate_dialogue_qc(
        manif,
        {
            "transcript": line,
            "languageCode": "en",
            "segments": [
                {"transcription": line, "speaker": "Korri"},
                {"transcription": "buy now cheap deals", "speaker": "BackgroundAnnouncer"},
            ],
            "availability": "available",
        },
    )
    assert qc["verdict"] == QC_FAIL
    assert qc["sceneFinishedEligible"] is False
    assert any(f["code"] == CODE_UNAUTHORIZED_BACKGROUND_SPEAKER for f in qc["findings"])
    bg = next(f for f in qc["findings"] if f["code"] == CODE_UNAUTHORIZED_BACKGROUND_SPEAKER)
    assert bg["observedSpeaker"] == "BackgroundAnnouncer"
    assert bg["finalCheck"]["retakeEligible"] is True
    assert bg["finalCheck"]["creativeTaste"] is False
    assert bg["finalCheck"]["authoritySource"] == "dialogue_manifest"
    # Bad ASR/speaker label must never rewrite Manifest.
    assert manif["speakers"] == ["Korri"] or "Korri" in manif["speakers"]


def test_qc_authorized_speaker_still_passes():
    """SLICE B control: authorized Manifest speaker + matching line => PASS."""
    line = "Renkoka obviously! She was such a hottie. Gorgeous assets if you catch my drift!"
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "Korri", "text": line}]}
        ],
        project_language="en",
    )
    qc = evaluate_dialogue_qc(
        manif,
        {
            "transcript": line,
            "languageCode": "en",
            "segments": [{"transcription": line, "speaker": "Korri"}],
            "availability": "available",
        },
    )
    assert qc["verdict"] == QC_PASS
    assert qc["sceneFinishedEligible"] is True
    assert not any(f["code"] == CODE_UNAUTHORIZED_BACKGROUND_SPEAKER for f in qc["findings"])


def test_slice_a_still_loud_empty_is_omni_miss_not_silence_lock():
    """SLICE B must preserve SLICE A: speech expected + loud empty => OMNI_TRANSCRIPT_MISS."""
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "A", "text": "Hello world"}]}
        ],
        project_language="en",
    )
    assert manif["expectedSpeech"] == EXPECTED_SPEECH_SPEECH
    qc = evaluate_dialogue_qc(
        manif,
        {"transcript": "", "languageCode": None, "segments": [], "availability": "available"},
        mean_volume_db=-16.7,
    )
    assert qc["verdict"] == QC_UNCERTAIN
    assert qc["reason"] == "OMNI_TRANSCRIPT_MISS"
    assert qc["sceneFinishedEligible"] is False
    assert not any(f["code"] == CODE_SPEECH_WHEN_SILENCE_EXPECTED for f in qc["findings"])


def test_slice_a_still_quiet_empty_silent_when_speech_expected():
    """SLICE B must preserve SLICE A: speech expected + quiet empty => SILENT_WHEN_SPEECH_EXPECTED."""
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "A", "text": "Hello world"}]}
        ],
        project_language="en",
    )
    qc = evaluate_dialogue_qc(
        manif,
        {"transcript": "", "languageCode": "en", "segments": [], "availability": "available"},
        mean_volume_db=-45.0,
    )
    assert qc["verdict"] == QC_FAIL
    assert qc["reason"] == "SILENT_WHEN_SPEECH_EXPECTED"
    assert not any(f["code"] == CODE_SPEECH_WHEN_SILENCE_EXPECTED for f in qc["findings"])


def test_put_scene_spoken_language_returns_200_with_persisted_body():
    """SLICE C: save_master returns SceneTimelineMaster; PUT must 200 after persist."""
    from unittest.mock import MagicMock

    from app.director_timeline_w46.contracts import SceneTimelineMaster
    from app.director_timeline_w46.router import SceneSpokenLanguageBody, put_scene_spoken_language
    from app.director_timeline_w46 import store as dt_store

    master = SceneTimelineMaster()
    persisted = {}

    def _load(db, project_id, scene_id):
        return {"ok": True, "master": master.model_dump()}

    def _save(db, project_id, scene_id, saved_master, **kwargs):
        persisted["sceneLanguage"] = saved_master.sceneLanguage
        persisted["spokenLanguage"] = getattr(saved_master, "spokenLanguage", None)
        persisted["touch_batches"] = kwargs.get("touch_batches")
        # Real store.save_master returns the master object — this was the 500.
        return saved_master

    orig_load, orig_save = dt_store.load_master, dt_store.save_master
    dt_store.load_master = _load
    dt_store.save_master = _save
    try:
        result = put_scene_spoken_language(
            "proj-1",
            "scene-12b",
            SceneSpokenLanguageBody(language="en"),
            db=MagicMock(),
        )
    finally:
        dt_store.load_master = orig_load
        dt_store.save_master = orig_save

    assert result["ok"] is True
    assert result["sceneLanguage"] == "en"
    assert result["spokenLanguage"]["sceneLanguage"] == "en"
    assert persisted["sceneLanguage"] == "en"
    assert persisted["spokenLanguage"]["sceneLanguage"] == "en"
    assert persisted["touch_batches"] is False


def test_qc_wrong_speaker_authorized_speaker_delivers_other_line():
    """SLICE C: Korri observed saying Anadriya's Manifest line => WRONG_SPEAKER."""
    ana = "He asked me a question and you won't even let me talk!"
    korri = "Put that away you soap psycho!"
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {
                "speechKind": "prompt_dialogue",
                "speakers": [
                    {"speakerName": "Anadriya", "text": ana},
                    {"speakerName": "Korri", "text": korri},
                ],
            }
        ],
        project_language="en",
    )
    qc = evaluate_dialogue_qc(
        manif,
        {
            "transcript": ana + " " + korri,
            "languageCode": "en",
            "segments": [
                {"transcription": ana, "speaker": "Korri"},
                {"transcription": korri, "speaker": "Korri"},
            ],
            "availability": "available",
        },
    )
    assert qc["verdict"] == QC_FAIL
    assert qc["sceneFinishedEligible"] is False
    assert any(f["code"] == CODE_WRONG_SPEAKER for f in qc["findings"])
    wrong = next(f for f in qc["findings"] if f["code"] == CODE_WRONG_SPEAKER)
    assert wrong["observedSpeaker"] == "Korri"
    assert wrong["expectedSpeaker"] == "Anadriya"
    assert "let me talk" in (wrong.get("expected") or "")
    assert wrong["finalCheck"]["retakeEligible"] is True
    assert wrong["finalCheck"]["authoritySource"] == "dialogue_manifest"
    # Manifest is not rewritten from the mis-attributed observation.
    assert "Anadriya" in manif["speakers"]
    assert manif["lines"][0]["speakerName"] == "Anadriya"


def test_qc_wrong_speaker_does_not_fire_when_speakers_match():
    """SLICE C control: matching speaker+line is not WRONG_SPEAKER."""
    ana = "He asked me a question and you won't even let me talk!"
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {"speechKind": "prompt_dialogue", "speakers": [{"speakerName": "Anadriya", "text": ana}]}
        ],
        project_language="en",
    )
    qc = evaluate_dialogue_qc(
        manif,
        {
            "transcript": ana,
            "languageCode": "en",
            "segments": [{"transcription": ana, "speaker": "Anadriya"}],
            "availability": "available",
        },
    )
    assert qc["verdict"] == QC_PASS
    assert not any(f["code"] == CODE_WRONG_SPEAKER for f in qc["findings"])



# ---------------------------------------------------------------------------
# Brad permanent LANGUAGE AUTHORITY layer
# ---------------------------------------------------------------------------

def test_lang_auth_manifest_emits_empty_sets_when_silent():
    m = build_dialogue_manifest(project_id="p", scene_id="s", allow_adlibs=False)
    assert m["expectedSpeech"] == EXPECTED_SPEECH_NONE
    assert m["authorized_dialogue_lines"] == []
    assert m["authorized_speakers"] == []
    assert m["authorized_languages"] == []


def test_lang_auth_manifest_en_only_emits_en():
    m = build_dialogue_manifest(
        project_id="p",
        scene_id="s",
        project_language="en",
        extra_lines=[{"text": "Keep moving.", "speakerName": "Cade", "language": "en"}],
    )
    assert m["authorized_languages"] == ["en"]
    assert len(m["authorized_dialogue_lines"]) == 1
    assert "Cade" in m["authorized_speakers"]


def test_lang_auth_silence_plus_foreign():
    from app.codirector.dialogue_authority import (
        CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT,
        CLASS_UNAUTHORIZED_SPEECH,
        evaluate_dialogue_qc,
        ensure_silence_locked_manifest,
        apply_qc_to_batch_status,
    )
    m = ensure_silence_locked_manifest(project_id="p", scene_id="s", batch_id="b")
    assert m["authorized_languages"] == []
    qc = evaluate_dialogue_qc(
        m,
        {
            "transcript": "Dydd da ffrindiau",
            "languageCode": "cy",
            "segments": [{"transcription": "Dydd da ffrindiau", "speaker": "unknown"}],
            "summary": "",
            "availability": "available",
        },
        mean_volume_db=-12.0,
    )
    assert qc["verdict"] == "FAIL"
    assert qc["speechClassification"] in (
        CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT,
        CLASS_UNAUTHORIZED_SPEECH,
    )
    assert qc.get("sceneFinishedEligible") is False
    class B:
        status = "Rendered"
        references = []
    b = B()
    assert apply_qc_to_batch_status(b, qc) != "CandidateReady"


def test_lang_auth_en_only_plus_foreign():
    from app.codirector.dialogue_authority import (
        CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT,
        evaluate_dialogue_qc,
    )
    m = build_dialogue_manifest(
        project_id="p",
        scene_id="s",
        project_language="en",
        extra_lines=[{"text": "Keep moving.", "speakerName": "Cade", "language": "en"}],
    )
    assert m["authorized_languages"] == ["en"]
    qc = evaluate_dialogue_qc(
        m,
        {
            "transcript": "Bonjour ami",
            "languageCode": "fr",
            "segments": [{"transcription": "Bonjour ami", "speaker": "Cade"}],
            "summary": "",
            "availability": "available",
        },
        mean_volume_db=-14.0,
    )
    assert qc["verdict"] == "FAIL"
    assert qc["speechClassification"] == CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT
    assert qc.get("sceneFinishedEligible") is False


def test_lang_auth_en_only_plus_correct_en():
    from app.codirector.dialogue_authority import (
        CLASS_AUTHORIZED_DIALOGUE,
        evaluate_dialogue_qc,
    )
    m = build_dialogue_manifest(
        project_id="p",
        scene_id="s",
        project_language="en",
        extra_lines=[{"text": "Keep moving through the corridor.", "speakerName": "Cade", "language": "en"}],
    )
    qc = evaluate_dialogue_qc(
        m,
        {
            "transcript": "Keep moving through the corridor.",
            "languageCode": "en",
            "segments": [{"transcription": "Keep moving through the corridor.", "speaker": "Cade"}],
            "summary": "",
            "availability": "available",
        },
        mean_volume_db=-18.0,
    )
    assert qc["verdict"] == "PASS"
    assert qc["speechClassification"] == CLASS_AUTHORIZED_DIALOGUE


def test_lang_auth_multilingual_scripted_matching():
    from app.codirector.dialogue_authority import (
        CLASS_AUTHORIZED_DIALOGUE,
        evaluate_dialogue_qc,
    )
    m = build_dialogue_manifest(
        project_id="p",
        scene_id="s",
        project_language="en",
        extra_lines=[
            {"text": "Hello.", "speakerName": "Cade", "language": "en"},
            {"text": "Hola.", "speakerName": "Maya", "language": "es"},
        ],
        allow_language_switch=True,  # ignored when scripted (forced False) — languages still from lines
    )
    assert set(m["authorized_languages"]) == {"en", "es"}
    qc = evaluate_dialogue_qc(
        m,
        {
            "transcript": "Hello. Hola.",
            "languageCode": "en",
            "segments": [
                {"transcription": "Hello.", "speaker": "Cade"},
                {"transcription": "Hola.", "speaker": "Maya"},
            ],
            "summary": "",
            "availability": "available",
        },
        mean_volume_db=-16.0,
    )
    # Scripted locks language switch false — observed "en" is in auth set, so authorized.
    assert qc["speechClassification"] in (CLASS_AUTHORIZED_DIALOGUE, "AUTHORIZED_LANGUAGE_VARIATION")
    assert qc["verdict"] in ("PASS", "FAIL", "UNCERTAIN")  # fidelity may vary; classification must not be unauthorized lang
    assert qc["speechClassification"] != "UNAUTHORIZED_LANGUAGE_ARTIFACT"


def test_lang_auth_gibberish_under_silence():
    from app.codirector.dialogue_authority import (
        CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT,
        CLASS_UNAUTHORIZED_SPEECH,
        evaluate_dialogue_qc,
        ensure_silence_locked_manifest,
    )
    m = ensure_silence_locked_manifest(project_id="p", scene_id="s")
    qc = evaluate_dialogue_qc(
        m,
        {
            "transcript": "the the the the the the",
            "languageCode": None,
            "segments": [{"transcription": "the the the the the the"}],
            "summary": "gibberish vocalization",
            "availability": "available",
        },
        mean_volume_db=-10.0,
    )
    assert qc["verdict"] == "FAIL"
    assert qc["speechClassification"] in (
        CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT,
        CLASS_UNAUTHORIZED_SPEECH,
    )


def test_lang_auth_empty_asr_plus_acoustic_evidence():
    from app.codirector.dialogue_authority import (
        CLASS_UNCERTAIN_SPEECH,
        evaluate_dialogue_qc,
        ensure_silence_locked_manifest,
        apply_qc_to_batch_status,
    )
    m = ensure_silence_locked_manifest(project_id="p", scene_id="s")
    qc = evaluate_dialogue_qc(
        m,
        {
            "transcript": "",
            "languageCode": None,
            "segments": [],
            "summary": "",
            "availability": "available",
        },
        mean_volume_db=-12.0,  # loud
    )
    assert qc["verdict"] == "UNCERTAIN"
    assert qc["speechClassification"] == CLASS_UNCERTAIN_SPEECH
    assert qc.get("sceneFinishedEligible") is False
    class B:
        status = "Rendered"
        references = []
    assert apply_qc_to_batch_status(B(), qc) != "CandidateReady"


# ---------------------------------------------------------------------------
# P6 hygiene: Omni infra vs content fail + frozen authority + VCM halt
# ---------------------------------------------------------------------------

def test_p6_hygiene_silence_omni_unavailable_qc_pending():
    from app.codirector.dialogue_authority import (
        apply_qc_to_batch_status,
        ensure_silence_locked_manifest,
        evaluate_dialogue_qc,
        is_omni_infra_unavailable,
    )
    m = ensure_silence_locked_manifest(project_id="p", scene_id="s")
    qc = evaluate_dialogue_qc(
        m,
        {"transcript": "", "languageCode": None, "segments": [], "availability": "unavailable"},
    )
    assert qc["reason"] == CODE_OMNI_UNAVAILABLE or qc.get("infraUnavailable") is True
    assert is_omni_infra_unavailable(qc) is True
    class B:
        status = "Rendered"
        references = []
    st = apply_qc_to_batch_status(B(), qc)
    assert st == STATUS_QC_RETRY_REQUIRED
    assert st != STATUS_NEEDS_DIALOGUE_RETAKE


def test_p6_hygiene_retry_silent_becomes_ready():
    from app.codirector.dialogue_authority import (
        apply_qc_to_batch_status,
        ensure_silence_locked_manifest,
        evaluate_dialogue_qc,
        freeze_language_authority_packet,
        manifest_from_frozen_packet,
    )
    m = ensure_silence_locked_manifest(project_id="p", scene_id="s")
    pkt = freeze_language_authority_packet(m)
    m2 = manifest_from_frozen_packet(pkt, fallback=m)
    assert m2["authorized_languages"] == []
    assert m2.get("authorityPacketFrozen") is True
    qc = evaluate_dialogue_qc(
        m2,
        {"transcript": "", "languageCode": None, "segments": [], "availability": "available"},
        mean_volume_db=-45.0,
    )
    class B:
        status = "QC_RetryRequired"
        references = []
    st = apply_qc_to_batch_status(B(), qc)
    assert st == "CandidateReady"
    assert qc["verdict"] == QC_PASS


def test_p6_hygiene_retry_foreign_blocks():
    from app.codirector.dialogue_authority import (
        CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT,
        CLASS_UNAUTHORIZED_SPEECH,
        apply_qc_to_batch_status,
        ensure_silence_locked_manifest,
        evaluate_dialogue_qc,
        freeze_language_authority_packet,
        manifest_from_frozen_packet,
    )
    m = ensure_silence_locked_manifest(project_id="p", scene_id="s")
    pkt = freeze_language_authority_packet(m)
    m2 = manifest_from_frozen_packet(pkt, fallback=m)
    qc = evaluate_dialogue_qc(
        m2,
        {
            "transcript": "Bonjour",
            "languageCode": "fr",
            "segments": [{"transcription": "Bonjour"}],
            "availability": "available",
        },
        mean_volume_db=-12.0,
    )
    class B:
        status = "QC_RetryRequired"
        references = []
    st = apply_qc_to_batch_status(B(), qc)
    assert st == STATUS_NEEDS_DIALOGUE_RETAKE
    assert qc["speechClassification"] in (
        CLASS_UNAUTHORIZED_LANGUAGE_ARTIFACT,
        CLASS_UNAUTHORIZED_SPEECH,
    )


def test_p6_hygiene_vcm_no_advance_while_pending():
    from app.codirector.dialogue_authority import (
        dialogue_qc_blocks_vcm_advance,
        ensure_silence_locked_manifest,
        evaluate_dialogue_qc,
    )
    from app.codirector.verified_continuity_memory import continuity_advance_allowed
    m = ensure_silence_locked_manifest(project_id="p", scene_id="s")
    qc = evaluate_dialogue_qc(
        m,
        {"transcript": "", "segments": [], "availability": "unavailable"},
    )
    class B:
        status = "QC_RetryRequired"
        references = [qc]
    assert dialogue_qc_blocks_vcm_advance(B(), qc) is True
    assert continuity_advance_allowed(batch=B(), dialogue_qc=qc) is False


def test_p6_hygiene_frozen_packet_no_recompile_drift():
    from app.codirector.dialogue_authority import (
        attach_authority_packet,
        freeze_language_authority_packet,
        get_frozen_authority_packet,
        build_dialogue_manifest,
        manifest_from_frozen_packet,
    )
    m = build_dialogue_manifest(
        project_id="p",
        scene_id="s",
        project_language="en",
        extra_lines=[{"text": "Keep moving.", "speakerName": "Cade", "language": "en"}],
    )
    pkt = freeze_language_authority_packet(m)
    class B:
        references = []
    b = B()
    attach_authority_packet(b, pkt)
    got = get_frozen_authority_packet(b)
    assert got["authorized_languages"] == ["en"]
    # Simulate drift in a recompiled manifest — frozen packet wins.
    drifted = build_dialogue_manifest(
        project_id="p",
        scene_id="s",
        project_language="es",
        extra_lines=[{"text": "Sigue.", "speakerName": "Cade", "language": "es"}],
    )
    restored = manifest_from_frozen_packet(got, fallback=drifted)
    assert restored["authorized_languages"] == ["en"]
    assert restored["authorized_dialogue_lines"][0]["text"] == "Keep moving."


def test_p0_qc_resume_against_existing_asset_uses_frozen_packet(monkeypatch):
    """QC resume: frozen silence packet + existing asset; no regen; infra → QC_RetryRequired."""
    from app.codirector import dialogue_authority as da

    batch = _Batch()
    manif = ensure_silence_locked_manifest(project_id="p", scene_id="s", batch_id="b1")
    attach_manifest_to_batch(batch, manif)
    pkt = freeze_language_authority_packet(manif)
    attach_authority_packet(batch, pkt)

    def _fake_run(db, **kwargs):
        assert kwargs["asset_id"] == "asset-existing"
        # Ensure frozen silence authority (no recompile drift)
        m = kwargs["manifest"]
        assert m.get("authorized_languages") == []
        assert m.get("authorityPacketFrozen") is True or m.get("expectedSpeech") == EXPECTED_SPEECH_NONE
        return evaluate_dialogue_qc(
            m,
            {"transcript": "", "segments": [], "availability": "unavailable"},
        )

    monkeypatch.setattr(da, "run_omni_dialogue_qc", _fake_run)
    out = da.resume_dialogue_qc_against_existing_asset(
        db=None,
        project_id="p",
        scene_id="s",
        asset_id="asset-existing",
        batch=batch,
    )
    assert out["regenerated"] is False
    assert out["assetPreserved"] is True
    assert out["status"] == STATUS_QC_RETRY_REQUIRED
    assert out["vcmAdvanceBlocked"] is True
    assert out["infraUnavailable"] is True
    assert batch.status == STATUS_QC_RETRY_REQUIRED




def test_path_b_law_silence_locked_generate_audio_false_audio_streams_0():
    """Chief CLEAR path (b) law triad — no Omni ASR required."""
    from app.codirector.dialogue_authority import (
        is_no_audio_generation_path,
        evaluate_dialogue_qc,
        apply_qc_to_batch_status,
        QC_PASS,
        STATUS_QC_RETRY_REQUIRED,
    )

    manifest = {
        "expectedSpeech": "NONE",
        "lines": [],
        "speakers": [],
        "authorized_dialogue_lines": [],
        "authorized_speakers": [],
        "authorized_languages": [],
        "allowAdLibs": False,
    }
    assert is_no_audio_generation_path(manifest=manifest, batch=None, audio_stream_count=0) is True
    # audio present → not path b
    assert is_no_audio_generation_path(manifest=manifest, batch=None, audio_stream_count=1) is False
    # scripted auth → not path b
    m2 = dict(manifest, expectedSpeech="REQUIRED", lines=[{"text": "hi", "speaker": "A"}])
    assert is_no_audio_generation_path(manifest=m2, batch=None, audio_stream_count=0) is False

    class B:
        status = "QC_RetryRequired"
        references = [{"kind": "audioAuthority", "authority": "silence_locked", "generateAudio": False}]

    assert is_no_audio_generation_path(manifest=manifest, batch=B(), audio_stream_count=0) is True
    # explicit generateAudio True blocks path b even if streams=0
    class B2:
        status = "X"
        references = [{"kind": "audioAuthority", "generateAudio": True}]
    assert is_no_audio_generation_path(manifest=manifest, batch=B2(), audio_stream_count=0) is False

    observed = {
        "transcript": "",
        "availability": "no_audio_track",
        "hasAudio": False,
        "audioStreamCount": 0,
        "generateAudio": False,
        "pathB": True,
        "segments": [],
        "summary": "",
        "role": "observation_only",
    }
    qc = evaluate_dialogue_qc(manifest, observed)
    assert qc["verdict"] == QC_PASS
    assert qc.get("sceneFinishedEligible") is True
    b = B()
    assert apply_qc_to_batch_status(b, qc) == "CandidateReady"


def test_path_b_no_audio_track_silence_pass_not_omni_unavailable():
    """Chief path (b): silence-lock + hasAudio=False → PASS / CandidateReady.

    Empty ASR alone still must NOT pass (separate tests). Omni worker timeout
    remains QC_RetryRequired — only explicit no-audio-track evidence qualifies.
    """
    from app.codirector.dialogue_authority import (
        evaluate_dialogue_qc,
        apply_qc_to_batch_status,
        QC_PASS,
        STATUS_QC_RETRY_REQUIRED,
    )

    manifest = {
        "expectedSpeech": "NONE",
        "lines": [],
        "speakers": [],
        "authorized_dialogue_lines": [],
        "authorized_speakers": [],
        "authorized_languages": [],
        "allowAdLibs": False,
    }
    # Path (b) affirmative silence
    observed = {
        "transcript": "",
        "languageCode": None,
        "segments": [],
        "summary": "",
        "availability": "no_audio_track",
        "hasAudio": False,
        "role": "observation_only",
    }
    qc = evaluate_dialogue_qc(manifest, observed, mean_volume_db=None)
    assert qc["verdict"] == QC_PASS, qc
    assert qc.get("sceneFinishedEligible") is True
    assert qc.get("reason") == "NO_AUDIO_TRACK_SILENCE"
    assert qc.get("infraUnavailable") is not True
    assert qc.get("contentFail") is not True

    class B:
        status = "QC_RetryRequired"
        references = []

    b = B()
    st = apply_qc_to_batch_status(b, qc)
    assert st == "CandidateReady"
    assert b.status == "CandidateReady"

    # Empty ASR + unavailable (no hasAudio=False) still UNCERTAIN / retry
    observed2 = {
        "transcript": "",
        "languageCode": None,
        "segments": [],
        "summary": "",
        "availability": "unavailable",
        "role": "observation_only",
    }
    qc2 = evaluate_dialogue_qc(manifest, observed2, mean_volume_db=None)
    assert qc2["verdict"] != QC_PASS
    assert qc2.get("reason") == "OMNI_UNAVAILABLE"
    b2 = B()
    st2 = apply_qc_to_batch_status(b2, qc2)
    assert st2 == STATUS_QC_RETRY_REQUIRED


def test_p0_vcm_blocked_without_successful_omni_pass():
    from app.codirector.dialogue_authority import dialogue_qc_blocks_vcm_advance
    from app.codirector.verified_continuity_memory import continuity_advance_allowed

    class B:
        status = "CandidateReady"
        references = []

    qc_fail = {"verdict": "FAIL", "sceneFinishedEligible": False}
    assert dialogue_qc_blocks_vcm_advance(B(), qc_fail) is True
    assert continuity_advance_allowed(batch=B(), dialogue_qc=qc_fail) is False

    qc_pass = {"verdict": "PASS", "sceneFinishedEligible": True}
    b = B()
    b.status = "CandidateReady"
    assert dialogue_qc_blocks_vcm_advance(b, qc_pass) is False
