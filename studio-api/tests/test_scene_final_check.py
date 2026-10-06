"""Unit tests for Co-Director Final Check lifecycle + local/API repair gates."""

from __future__ import annotations

from types import SimpleNamespace

from app.director_timeline_w46 import scene_final_check as sfc

def _fc(**kwargs):
    """Dialogue Authority findings[].finalCheck sidecar."""
    base = {
        "retakeEligible": False,
        "autoDestroy": False,
        "acceptanceEligible": False,
        "creativeTaste": False,
        "authoritySource": "dialogue_manifest",
    }
    base.update(kwargs)
    return base

from app.director_timeline_w46.scene_final_check import (
    DA_NO_AUTO_RETAKE_CODES,
    FINAL_CHECK_CATEGORIES,
    STUB_CATEGORIES,
    VERDICT_ACCEPTED,
    VERDICT_FOUND_ISSUES,
    VERDICT_PASSED,
    advance_after_repair,
    apply_api_repair_decision,
    apply_local_auto_repair,
    auto_repair_eligible_findings,
    build_category_shell,
    classify_runtime_kind,
    cross_modality_uncertainty,
    derive_scene_lifecycle_status,
    ingest_dialogue_qc,
    is_local_runtime,
    map_dialogue_finding,
    open_final_check_after_stitch,
    plan_local_auto_repair_from_final_check,
    qualify_retake,
    repair_gate_for_runtime,
)


def _batch(status: str, refs: list | None = None, *, bid: str = "b1", order: int = 0):
    return SimpleNamespace(
        id=bid,
        order=order,
        status=status,
        references=refs or [],
        approvedClip=SimpleNamespace(assetId=f"a-{bid}") if status in {
            "Approved",
            "CandidateReady",
            "ApprovedConfigurationChanged",
            "RegenerationRecommended",
            "NeedsDialogueRetake",
        } else None,
        createdAt="2026-01-01T00:00:00Z",
        generationJobs=[],
        label=bid,
    )


def _master(batches, *, stitch=None, scene_final_check=None):
    return SimpleNamespace(
        batchBlocks=batches,
        sceneStitch=stitch,
        sceneFinalCheck=scene_final_check,
        sceneGeneratorId="ltx-local",
    )


def test_lifecycle_states_include_final_check_cluster():
    for state in (
        "RENDERING",
        "BATCHES_COMPLETE",
        "STITCHING",
        "FINAL_CHECK",
        "REPAIRING",
        "REVERIFYING",
        "SCENE_FINISHED",
        "SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
        "SCENE_NOT_FINISHED",
    ):
        assert state in sfc.LIFECYCLE_STATES


def test_draft_idle_scene_is_not_rendering_lifecycle():
    """Brand-new Draft must NOT get RENDERING (no GENERATE SCENE overlay)."""
    master = _master([_batch("Draft", bid="b1", order=0)])
    status = derive_scene_lifecycle_status(master)
    assert status == "SCENE_NOT_FINISHED"
    assert status != "RENDERING"


def test_ready_idle_scene_is_not_rendering_lifecycle():
    master = _master([_batch("Ready", bid="b1", order=0)])
    status = derive_scene_lifecycle_status(master)
    assert status == "SCENE_NOT_FINISHED"
    assert status != "RENDERING"


def test_empty_batches_not_rendering_lifecycle():
    master = _master([])
    status = derive_scene_lifecycle_status(master)
    assert status == "SCENE_NOT_FINISHED"
    assert status != "RENDERING"


def test_generating_batch_is_rendering_lifecycle():
    master = _master([_batch("Generating", bid="b1", order=0)])
    status = derive_scene_lifecycle_status(master)
    assert status == "RENDERING"



def test_draft_idle_progress_has_empty_status_lines():
    """Idle Draft must not leak Render Batch N/M — idle into statusLines."""
    from app.director_timeline_w46.current_take import compute_generation_progress

    master = _master([_batch("Draft", bid="b1", order=0)])
    gp = compute_generation_progress(master)
    assert gp.get("sceneStatus") == "idle"
    assert gp.get("statusLines") == []
    assert gp.get("lifecycleStatus") == "SCENE_NOT_FINISHED"
    msg = str(gp.get("message") or "")
    assert "idle" not in msg.lower()
    assert "Render Batch" not in msg

def test_batches_complete_does_not_imply_scene_finished():
    master = _master(
        [
            _batch("Approved", bid="b1", order=0),
            _batch("CandidateReady", bid="b2", order=1),
        ]
    )
    status = derive_scene_lifecycle_status(master)
    assert status == "BATCHES_COMPLETE"
    assert status != "SCENE_FINISHED"


def test_nn_batches_complete_with_dialogue_retake_not_finished():
    qc = {
        "kind": "dialogueQcDiagnostics",
        "verdict": "FAIL",
        "sceneFinishedEligible": False,
        "findings": [
            {
                "code": "LINE_FIDELITY_FAIL",
                "severity": "error",
                "message": "script drift",
                "confidence": "high",
                "finalCheck": _fc(retakeEligible=True),
            }
        ],
    }
    master = _master([_batch("NeedsDialogueRetake", [qc])])
    status = derive_scene_lifecycle_status(master)
    assert status == "BATCHES_COMPLETE"
    assert status != "SCENE_FINISHED"


def test_stitch_opens_final_check():
    qc = {
        "kind": "dialogueQcDiagnostics",
        "verdict": "FAIL",
        "sceneFinishedEligible": False,
        "findings": [
            {
                "code": "UNAUTHORIZED_LANGUAGE",
                "severity": "error",
                "message": "Welsh",
                "confidence": "high",
                "finalCheck": _fc(retakeEligible=True),
            }
        ],
    }
    master = _master(
        [
            _batch("Approved", [qc], bid="b1", order=0),
            _batch("Approved", bid="b2", order=1),
        ],
        stitch=SimpleNamespace(assetId="stitch-1"),
    )
    state = open_final_check_after_stitch(master, runtime_kind="local")
    assert state["lifecycleStatus"] == "FINAL_CHECK"
    assert state["creatorVerdict"] == VERDICT_FOUND_ISSUES
    assert state["stitchAssetId"] == "stitch-1"
    cats = {c["category"]: c for c in state["categories"]}
    assert cats["language"]["status"] == "fail"
    assert cats["continuity"]["status"] == "not_run"
    assert cats["equipment"]["status"] == "not_run"
    assert cats["continuity"]["status"] != "pass"


def test_stub_categories_are_not_run_not_pass():
    shell = build_category_shell([])
    for cat in STUB_CATEGORIES:
        row = next(c for c in shell if c["category"] == cat)
        assert row["status"] == "not_run"
        assert row["status"] != "pass"


def test_all_final_check_categories_present():
    shell = build_category_shell([])
    assert [c["category"] for c in shell] == list(FINAL_CHECK_CATEGORIES)


def test_local_hard_auto_retake_permission_not_required():
    gate = repair_gate_for_runtime("local", has_auto_eligible=True)
    assert gate["permission"] == "not_required"
    assert gate["requiresApproval"] is False
    applied = apply_local_auto_repair(gate)
    assert applied["permission"] == "not_required"
    assert applied["lifecycleStatus"] == "REPAIRING"
    assert applied["apiCallsDelta"] == 0


def test_api_hard_requires_one_approval():
    gate = repair_gate_for_runtime("api", has_auto_eligible=True)
    assert gate["permission"] == "required"
    assert gate["requiresApproval"] is True
    assert gate["oneApprovalPerCycle"] is True
    assert "repair_automatically" in gate["actions"]
    assert "keep_current" in gate["actions"]


def test_api_decline_increments_api_call_count_by_zero():
    gate = repair_gate_for_runtime("api", has_auto_eligible=True)
    assert gate["apiCallCount"] == 0
    declined = apply_api_repair_decision(gate, "decline")
    assert declined["apiCallsDelta"] == 0
    assert declined["apiCallCount"] == 0
    assert declined["permission"] == "declined"
    assert declined["lifecycleStatus"] == "SCENE_NOT_FINISHED"
    dismissed = apply_api_repair_decision(gate, "dismiss")
    assert dismissed["apiCallsDelta"] == 0


def test_keep_current_to_scene_finished_with_accepted_issues():
    gate = repair_gate_for_runtime("api", has_auto_eligible=True)
    kept = apply_api_repair_decision(gate, "keep_current")
    assert kept["lifecycleStatus"] == "SCENE_FINISHED_WITH_ACCEPTED_ISSUES"
    assert kept["creatorVerdict"] == VERDICT_ACCEPTED
    assert kept["apiCallsDelta"] == 0


def test_creative_excluded_from_auto_repair():
    finding = map_dialogue_finding(
        {
            "code": "CREATIVE_PUSH_IN",
            "severity": "info",
            "taxonomy": "Creative",
            "creative": True,
            "message": "try a push-in",
            "confidence": "high",
        }
    )
    assert finding["taxonomy"] == "Creative"
    assert finding["retakeEligible"] is False
    q = qualify_retake(finding)
    assert q["qualifies"] is False
    assert q["autoRetake"] is False
    shell = build_category_shell([finding])
    assert auto_repair_eligible_findings(shell) == []


def test_omni_transcript_miss_blocks_finished_not_auto_retake():
    finding = map_dialogue_finding(
        {
            "code": "OMNI_TRANSCRIPT_MISS",
            "severity": "error",
            "message": "loud but empty transcript",
        },
        verdict="UNCERTAIN",
    )
    assert finding["code"] == "OMNI_TRANSCRIPT_MISS"
    assert finding["retakeEligible"] is False
    assert finding["confidence"] == "low"
    assert "OMNI_TRANSCRIPT_MISS" in DA_NO_AUTO_RETAKE_CODES
    q = qualify_retake(finding)
    assert q["autoRetake"] is False
    assert q.get("blocksFinished") is True


def test_is_local_runtime_via_capability_not_name():
    assert is_local_runtime(locality="local") is True
    assert is_local_runtime(locality="hosted") is False
    assert is_local_runtime(execution_type="api") is False
    cap_local = SimpleNamespace(locality="local", id="minimax-h3-timeline")
    cap_api = SimpleNamespace(locality="hosted", id="seedance-2.0")
    assert is_local_runtime(capability=cap_local) is True
    assert is_local_runtime(capability=cap_api) is False
    assert classify_runtime_kind(capability=cap_local) == "local"
    assert classify_runtime_kind(capability=cap_api) == "api"
    assert (
        classify_runtime_kind(
            generator_id="seedance-2.0",
            adapter_profile={"byGeneratorId": {"seedance-2.0": {"runtimeKind": "api"}}},
        )
        == "api"
    )
    assert (
        classify_runtime_kind(
            generator_id="ltx-2.5-full",
            adapter_profile={"byGeneratorId": {"ltx-2.5-full": {"runtimeKind": "local"}}},
        )
        == "local"
    )


def test_ingest_dialogue_qc_consumes_locked_shape():
    qc = {
        "kind": "dialogueQcDiagnostics",
        "verdict": "FAIL",
        "findings": [
            {"code": "WRONG_SPEAKER", "severity": "error", "confidence": "high", "finalCheck": _fc(retakeEligible=True)},
            {"code": "ADLIB_OR_NONLITERAL", "severity": "error", "confidence": "high", "finalCheck": _fc(retakeEligible=True)},
        ],
    }
    findings = ingest_dialogue_qc(qc)
    assert len(findings) == 2
    assert findings[0]["category"] == "speaker"
    assert findings[1]["category"] == "dialogue"
    assert all(f["source"] == "dialogueQcDiagnostics" for f in findings)


def test_reverify_pass_and_bounded_cleanup():
    ok = advance_after_repair(pass_reverify=True, loop_count=1)
    assert ok["lifecycleStatus"] == "SCENE_FINISHED"
    assert ok["creatorVerdict"] == VERDICT_PASSED
    fail = advance_after_repair(pass_reverify=False, loop_count=3, max_loops=3)
    assert fail["lifecycleStatus"] == "SCENE_NOT_FINISHED"
    assert fail["cleanupFailed"] is True
    assert "COULD NOT RESOLVE" in fail["message"]


def test_stored_final_check_status_wins():
    master = _master(
        [_batch("Approved")],
        stitch=SimpleNamespace(assetId="s1"),
        scene_final_check={"lifecycleStatus": "SCENE_FINISHED_WITH_ACCEPTED_ISSUES"},
    )
    assert derive_scene_lifecycle_status(master) == "SCENE_FINISHED_WITH_ACCEPTED_ISSUES"


def test_creator_verdicts_map():
    assert sfc.creator_verdict_to_lifecycle(VERDICT_PASSED) == "SCENE_FINISHED"
    assert sfc.creator_verdict_to_lifecycle(VERDICT_FOUND_ISSUES) == "SCENE_NOT_FINISHED"
    assert sfc.creator_verdict_to_lifecycle(VERDICT_ACCEPTED) == "SCENE_FINISHED_WITH_ACCEPTED_ISSUES"


def test_sidecar_is_eligibility_authority_not_code_rederive():
    """Consume findings[].finalCheck — do not re-derive retakeEligible from codes."""
    hard = map_dialogue_finding(
        {
            "code": "UNAUTHORIZED_LANGUAGE",
            "severity": "error",
            "finalCheck": _fc(retakeEligible=True, autoDestroy=False, acceptanceEligible=False),
        }
    )
    assert hard["retakeEligible"] is True
    assert hard["autoDestroy"] is False
    assert hard["acceptanceEligible"] is False
    assert hard["authoritySource"] == "dialogue_manifest"
    assert qualify_retake(hard)["autoRetake"] is True

    miss = map_dialogue_finding(
        {
            "code": "OMNI_TRANSCRIPT_MISS",
            "severity": "error",
            "finalCheck": _fc(retakeEligible=False, autoDestroy=False, acceptanceEligible=False),
        },
        verdict="UNCERTAIN",
    )
    assert miss["retakeEligible"] is False
    assert miss["autoDestroy"] is False
    assert miss["acceptanceEligible"] is False
    q = qualify_retake(miss)
    assert q["autoRetake"] is False
    assert q["blocksFinished"] is True

    # Sidecar false wins even if legacy top-level retakeEligible true (should not happen).
    overridden = map_dialogue_finding(
        {
            "code": "LINE_FIDELITY_FAIL",
            "severity": "error",
            "retakeEligible": True,
            "finalCheck": _fc(retakeEligible=False),
        }
    )
    assert overridden["retakeEligible"] is False


def test_silent_when_speech_expected_sidecar_retake_eligible():
    silent = map_dialogue_finding(
        {
            "code": "SILENT_WHEN_SPEECH_EXPECTED",
            "severity": "error",
            "finalCheck": _fc(retakeEligible=True),
        },
        verdict="FAIL",
    )
    assert silent["retakeEligible"] is True
    assert qualify_retake(silent)["autoRetake"] is True


def test_cross_modality_empty_asr_loud_energy():
    """Empty ASR + loud energy → UNCERTAIN / OMNI_TRANSCRIPT_MISS; not SILENT; not auto-retake."""
    xm = cross_modality_uncertainty(
        primary_miss=True, contradicting_modality=True, code="OMNI_TRANSCRIPT_MISS"
    )
    assert xm["uncertain"] is True
    assert xm["autoRetake"] is False
    assert xm["autoDestroy"] is False
    assert xm["blocksFinished"] is True
    assert xm["law"] == "ABSENCE_OF_EVIDENCE_NEQ_EVIDENCE_OF_ABSENCE"

    finding = map_dialogue_finding(
        {
            "code": "OMNI_TRANSCRIPT_MISS",
            "severity": "error",
            "loudEnergyWithEmptyTranscript": True,
            "crossModalityContradiction": True,
            "finalCheck": _fc(retakeEligible=False, autoDestroy=False, acceptanceEligible=False),
        },
        verdict="UNCERTAIN",
    )
    q = qualify_retake(finding)
    assert q["autoRetake"] is False
    assert q.get("autoDestroy") is False
    assert q["blocksFinished"] is True
    assert finding["retakeEligible"] is False


def test_cross_modality_weak_visual_identity_escalates_not_auto_regen():
    """Uncertain visual identity + CRS/temporal conflict → creator review; never auto-destroy."""
    finding = {
        "category": "identity",
        "taxonomy": "Hard",
        "code": "IDENTITY_UNCERTAIN_CRS_CONFLICT",
        "severity": "error",
        "confidence": "low",
        "retakeEligible": False,
        "autoDestroy": False,
        "acceptanceEligible": False,
        "crossModality": {"primaryMiss": True, "contradictingModality": True},
        "finalCheck": {
            "retakeEligible": False,
            "autoDestroy": False,
            "acceptanceEligible": False,
            "creativeTaste": False,
            "authoritySource": "crs_temporal",
        },
    }
    q = qualify_retake(finding)
    assert q["qualifies"] is False
    assert q["autoRetake"] is False
    assert q["needsCreatorReview"] is True
    assert q.get("autoDestroy") is False
    assert q["blocksFinished"] is True


def test_high_confidence_hard_still_auto_retakes_locally():
    """Cross-modality law does not block objective Hard Manifest violations."""
    finding = map_dialogue_finding(
        {
            "code": "UNAUTHORIZED_LANGUAGE",
            "severity": "error",
            "confidence": "high",
            "finalCheck": _fc(retakeEligible=True),
        }
    )
    q = qualify_retake(finding)
    assert q["qualifies"] is True
    assert q["autoRetake"] is True


# ---------------------------------------------------------------------------
# Slice B taxonomy + Continuity/Equipment pipelines + PRESERVE + repair loop
# ---------------------------------------------------------------------------


def test_slice_b_speech_when_silence_expected_hard_dialogue():
    finding = map_dialogue_finding(
        {
            "code": "SPEECH_WHEN_SILENCE_EXPECTED",
            "severity": "error",
            "message": "speech under silence lock",
            "finalCheck": _fc(retakeEligible=True),
        },
        verdict="FAIL",
    )
    assert finding["category"] == "dialogue"
    assert finding["taxonomy"] == "Hard"
    assert finding["retakeEligible"] is True
    assert qualify_retake(finding)["autoRetake"] is True
    shell = build_category_shell([finding])
    by = {c["category"]: c for c in shell}
    assert by["dialogue"]["status"] == "fail"


def test_slice_b_unauthorized_background_speaker_hard_speaker_and_dialogue():
    finding = map_dialogue_finding(
        {
            "code": "UNAUTHORIZED_BACKGROUND_SPEAKER",
            "severity": "error",
            "message": "unexpected speaker",
            "finalCheck": _fc(retakeEligible=True),
        },
        verdict="FAIL",
    )
    assert finding["category"] == "speaker"
    assert finding["taxonomy"] == "Hard"
    assert "dialogue" in (finding.get("alsoCategories") or [])
    assert finding["retakeEligible"] is True
    shell = build_category_shell([finding])
    by = {c["category"]: c for c in shell}
    assert by["speaker"]["status"] == "fail"
    assert by["dialogue"]["status"] == "fail"  # mirrored


def test_slice_b_modality_conflict_uncertain_audio_not_pass_not_auto():
    finding = map_dialogue_finding(
        {
            "code": "MODALITY_CONFLICT",
            "severity": "error",
            "message": "empty ASR + loud energy",
            "finalCheck": {
                **_fc(retakeEligible=False, autoDestroy=False, acceptanceEligible=False),
                "modalityConflict": True,
                "modalities": ["asr", "energy"],
                "conflictReason": "empty ASR + loud energy",
            },
        },
        verdict="UNCERTAIN",
    )
    assert finding["category"] == "dialogue"
    assert finding["retakeEligible"] is False
    assert finding["confidence"] == "low"
    assert finding.get("modalityConflict") is True
    assert "audio" in (finding.get("alsoCategories") or [])
    assert "MODALITY_CONFLICT" in sfc.DA_NO_AUTO_RETAKE_CODES
    q = qualify_retake(finding)
    assert q["autoRetake"] is False
    assert q.get("autoDestroy") is False
    shell = build_category_shell([finding])
    by = {c["category"]: c for c in shell}
    assert by["dialogue"]["status"] == "uncertain"
    assert by["audio"]["status"] == "uncertain"
    assert by["audio"]["status"] != "pass"


def test_slice_b_omni_transcript_miss_stays_uncertain():
    finding = map_dialogue_finding(
        {
            "code": "OMNI_TRANSCRIPT_MISS",
            "severity": "error",
            "finalCheck": _fc(retakeEligible=False),
        },
        verdict="UNCERTAIN",
    )
    assert finding["retakeEligible"] is False
    assert finding["confidence"] == "low"
    assert qualify_retake(finding)["autoRetake"] is False


def test_slice_b_silence_expected_quiet_empty_does_not_block_finished():
    """expectedSpeech NONE + quiet empty is DA PASS — no findings → do not block SCENE_FINISHED."""
    master = _master(
        [_batch("Approved", bid="b1"), _batch("Approved", bid="b2")],
        stitch=SimpleNamespace(assetId="stitch-ok"),
    )
    state = open_final_check_after_stitch(master, runtime_kind="local")
    assert state["lifecycleStatus"] == "SCENE_FINISHED"
    assert state["creatorVerdict"] == VERDICT_PASSED


def test_continuity_pipeline_hard_high_conf_established_retake_eligible():
    from app.director_timeline_w46.scene_final_check import map_continuity_finding

    finding = map_continuity_finding(
        {
            "code": "CONTINUITY_TELEPORT",
            "severity": "error",
            "confidence": "high",
            "establishedAuthority": True,
            "message": "teleport vs canon",
            "finalCheck": {
                "retakeEligible": True,
                "autoDestroy": False,
                "acceptanceEligible": False,
                "creativeTaste": False,
                "authoritySource": "continuity_canon",
            },
        },
        verdict="FAIL",
    )
    assert finding["category"] == "continuity"
    assert finding["taxonomy"] == "Hard"
    assert finding["retakeEligible"] is True
    assert qualify_retake(finding)["autoRetake"] is True
    shell = build_category_shell([], continuity_findings=[finding])
    by = {c["category"]: c for c in shell}
    assert by["continuity"]["status"] == "fail"
    assert by["continuity"]["source"] != "stub"


def test_continuity_uncertain_weak_visual_no_auto_regen():
    from app.director_timeline_w46.scene_final_check import map_continuity_finding

    finding = map_continuity_finding(
        {
            "code": "CONTINUITY_CRS_TEMPORAL_CONFLICT",
            "severity": "error",
            "confidence": "low",
            "weakVisual": True,
            "crsTemporalConflict": True,
            "message": "weak visual + CRS conflict",
        },
        verdict="UNCERTAIN",
    )
    assert finding["retakeEligible"] is False
    assert finding["confidence"] == "low"
    q = qualify_retake(finding)
    assert q["autoRetake"] is False
    assert q["needsCreatorReview"] is True


def test_continuity_never_invent_from_bad_frame():
    from app.director_timeline_w46.scene_final_check import map_continuity_finding

    finding = map_continuity_finding(
        {
            "code": "CONTINUITY_BREAK",
            "severity": "error",
            "confidence": "high",
            "establishedAuthority": True,
            "inventedFromBadFrame": True,
            "message": "invented from bad frame",
        }
    )
    assert finding["retakeEligible"] is False
    assert qualify_retake(finding)["autoRetake"] is False


def test_continuity_pipeline_not_run_without_omni_packet():
    shell = build_category_shell([])
    by = {c["category"]: c for c in shell}
    assert by["continuity"]["status"] == "not_run"
    assert by["continuity"]["status"] != "pass"
    assert by["continuity"]["source"] == "pipeline_ready"


def test_equipment_hard_crew_boom_local_auto_uses_rcp_authority():
    from app.director_timeline_w46.scene_final_check import (
        equipment_authority_packet,
        map_equipment_finding,
    )

    auth = equipment_authority_packet()
    assert "retake_context_package" in str(auth.get("authoritySource"))
    finding = map_equipment_finding(
        {
            "code": "UNAUTHORIZED_PRODUCTION_EQUIPMENT",
            "severity": "error",
            "confidence": "high",
            "message": "boom mic operator visible in frame",
            "finalCheck": {
                "retakeEligible": True,
                "autoDestroy": False,
                "acceptanceEligible": False,
                "creativeTaste": False,
                "authoritySource": auth["authoritySource"],
            },
        },
        verdict="FAIL",
    )
    assert finding["category"] == "equipment"
    assert finding["taxonomy"] == "Hard"
    assert finding["retakeEligible"] is True
    assert "camera" in (finding.get("alsoCategories") or [])
    assert qualify_retake(finding)["autoRetake"] is True
    shell = build_category_shell([], equipment_findings=[finding])
    by = {c["category"]: c for c in shell}
    assert by["equipment"]["status"] == "fail"
    assert by["camera"]["status"] == "fail"
    eligible = auto_repair_eligible_findings(shell)
    assert any(f["code"] == "UNAUTHORIZED_PRODUCTION_EQUIPMENT" for f in eligible)
    gate = repair_gate_for_runtime("local", has_auto_eligible=True)
    assert gate["permission"] == "not_required"
    api_gate = repair_gate_for_runtime("api", has_auto_eligible=True)
    assert api_gate["permission"] == "required"


def test_creative_camera_taste_never_auto():
    from app.director_timeline_w46.scene_final_check import map_equipment_finding

    finding = map_equipment_finding(
        {
            "code": "CREATIVE_PUSH_IN",
            "creative": True,
            "message": "try a push-in",
            "confidence": "high",
        }
    )
    assert finding["taxonomy"] == "Creative"
    assert finding["retakeEligible"] is False
    assert qualify_retake(finding)["autoRetake"] is False


def test_retake_pack_preserve_fields():
    finding = map_dialogue_finding(
        {
            "code": "SPEECH_WHEN_SILENCE_EXPECTED",
            "severity": "error",
            "finalCheck": _fc(retakeEligible=True),
            "confidence": "high",
        }
    )
    pack = sfc.build_retake_pack([finding])
    assert "WHAT_WRONG" in pack
    assert "WHAT_CHANGE" in pack
    assert "WHAT_PRESERVE" in pack
    assert "WINDOW" in pack
    assert "AUTHORITIES" in pack
    assert "METHOD" in pack
    assert pack["neverInventAuthorityFromBadOutput"] is True
    assert pack["oneIntervalForCompatibleDefects"] is True


def test_bounded_local_repair_loop_cleanup_could_not_resolve():
    result = sfc.run_bounded_local_repair_loop(reverify_results=[False, False, False], max_loops=3)
    assert result["cleanupFailed"] is True
    assert result["message"] == "AUTOMATIC CLEANUP COULD NOT RESOLVE"
    assert result["lifecycleStatus"] == "SCENE_NOT_FINISHED"
    ok = sfc.run_bounded_local_repair_loop(reverify_results=[False, True], max_loops=3)
    assert ok["lifecycleStatus"] == "SCENE_FINISHED"
    assert ok["cleanupFailed"] is False


def test_wrong_speaker_sidecar_hard_speaker_and_dialogue():
    """Slice C: WRONG_SPEAKER + sidecar retakeEligible -> speaker (+ dialogue) Hard."""
    finding = map_dialogue_finding(
        {
            "code": "WRONG_SPEAKER",
            "severity": "error",
            "message": "cue attributed to wrong speaker",
            "finalCheck": _fc(retakeEligible=True),
        },
        verdict="FAIL",
    )
    assert finding["category"] == "speaker"
    assert finding["taxonomy"] == "Hard"
    assert finding["retakeEligible"] is True
    assert "dialogue" in (finding.get("alsoCategories") or [])
    assert qualify_retake(finding)["autoRetake"] is True
    shell = build_category_shell([finding])
    by = {c["category"]: c for c in shell}
    assert by["speaker"]["status"] == "fail"
    assert by["dialogue"]["status"] == "fail"


def test_attach_retake_repair_from_pack_reuses_dialogue_retake_kind():
    from types import SimpleNamespace
    from app.director_timeline_w46.scene_final_check import attach_retake_repair_from_pack

    batch = SimpleNamespace(id="bb1", references=[], promptSegments=[])
    pack = {
        "WHAT_WRONG": ["CAMERA_CREW_IN_FRAME"],
        "WHAT_CHANGE": "Remove diegetic crew — keep cast/location; crew OUT OF FRAME",
        "WHAT_PRESERVE": "Anadriya/Korri/dialogue/quarters",
        "WINDOW": {"start": 0.0, "length": 15.0},
        "AUTHORITIES": ["retake_context_package.prompt_law_crew_out"],
        "METHOD": "equipment",
    }
    finding = {
        "code": "CAMERA_CREW_IN_FRAME",
        "category": "equipment",
        "taxonomy": "Hard",
        "retakeEligible": True,
        "confidence": "high",
        "authoritySource": "retake_context_package.prompt_law_crew_out",
    }
    repair = attach_retake_repair_from_pack(batch, pack, [finding])
    assert repair["kind"] == "dialogueRetakeRepair"
    assert "OUT OF FRAME" in repair["userCorrection"]["delta"]
    assert "PRESERVE" in repair["userCorrection"]["delta"]
    assert any(r.get("kind") == "dialogueRetakeRepair" for r in batch.references)


def test_open_final_check_ingests_omni_continuity_and_equipment_packets():
    from types import SimpleNamespace
    from app.director_timeline_w46.scene_final_check import open_final_check_after_stitch

    batch = SimpleNamespace(
        id="bb1",
        status="CandidateReady",
        references=[
            {
                "kind": "omniContinuityDiagnostics",
                "verdict": "PASS",
                "findings": [],
                "continuityFindings": [],
            },
            {
                "kind": "omniEquipmentDiagnostics",
                "verdict": "FAIL",
                "findings": [
                    {
                        "code": "CAMERA_CREW_IN_FRAME",
                        "severity": "error",
                        "confidence": "high",
                        "message": "camera crew in frame",
                        "finalCheck": {
                            "retakeEligible": True,
                            "autoDestroy": False,
                            "acceptanceEligible": False,
                            "creativeTaste": False,
                            "authoritySource": "retake_context_package.prompt_law_crew_out",
                        },
                    }
                ],
                "equipmentFindings": [
                    {
                        "code": "CAMERA_CREW_IN_FRAME",
                        "severity": "error",
                        "confidence": "high",
                        "message": "camera crew in frame",
                        "finalCheck": {
                            "retakeEligible": True,
                            "autoDestroy": False,
                            "acceptanceEligible": False,
                            "creativeTaste": False,
                            "authoritySource": "retake_context_package.prompt_law_crew_out",
                        },
                    }
                ],
            },
        ],
        duration=SimpleNamespace(plannedDuration=15.0, generatedDuration=15.0),
    )
    master = SimpleNamespace(
        batchBlocks=[batch],
        sceneGeneratorId="minimax-h3-t2v-local",
        sceneStitch=None,
        sceneFinalCheck=None,
    )
    state = open_final_check_after_stitch(master, runtime_kind="local")
    by = {c["category"]: c for c in state["categories"]}
    assert by["continuity"]["status"] in ("pass", "not_run") or by["continuity"]["status"] == "pass"
    # Gate seen + empty findings => pass note path
    assert by["equipment"]["status"] == "fail"
    assert state["autoRepairEligibleCount"] >= 1
    assert state["retakePack"] is not None
    assert state["repairGate"]["runtimeKind"] == "local"
    assert "auto_retake" in state["repairGate"]["actions"]


def test_h3_local_generator_id_classifies_local_via_registry():
    """Regression: minimax-h3 / minimax-h3-t2v-local must not default to api ask-once."""
    assert classify_runtime_kind(generator_id="minimax-h3") == "local"
    assert classify_runtime_kind(generator_id="minimax-h3-t2v-local") == "local"
    assert classify_runtime_kind(generator_id="minimax-h3-local") == "local"
    assert classify_runtime_kind(generator_id="ltx-2.5-full") == "local"
    assert classify_runtime_kind(generator_id="seedance-2.0") == "api"


def test_h3_local_boom_in_frame_should_auto_retake_no_approval():
    """minimax-h3-t2v-local + BOOM_IN_FRAME Hard high-conf → auto retake, no permission."""
    batch = SimpleNamespace(
        id="bb1",
        status="CandidateReady",
        references=[
            {
                "kind": "omniEquipmentDiagnostics",
                "verdict": "FAIL",
                "findings": [
                    {
                        "code": "BOOM_IN_FRAME",
                        "severity": "error",
                        "confidence": "high",
                        "message": "boom mic in frame",
                        "finalCheck": {
                            "retakeEligible": True,
                            "autoDestroy": False,
                            "acceptanceEligible": False,
                            "creativeTaste": False,
                            "authoritySource": "retake_context_package.prompt_law_crew_out",
                        },
                    }
                ],
                "equipmentFindings": [
                    {
                        "code": "BOOM_IN_FRAME",
                        "severity": "error",
                        "confidence": "high",
                        "message": "boom mic in frame",
                        "finalCheck": {
                            "retakeEligible": True,
                            "autoDestroy": False,
                            "acceptanceEligible": False,
                            "creativeTaste": False,
                            "authoritySource": "retake_context_package.prompt_law_crew_out",
                        },
                    }
                ],
            }
        ],
        duration=SimpleNamespace(plannedDuration=15.0, generatedDuration=15.0),
        generatorId="minimax-h3-t2v-local",
    )
    master = SimpleNamespace(
        batchBlocks=[batch],
        sceneGeneratorId="minimax-h3-t2v-local",
        sceneStitch=None,
        sceneFinalCheck=None,
    )
    # Do NOT pass runtime_kind — classifier must resolve local from registry.
    state = open_final_check_after_stitch(master)
    gate = state["repairGate"]
    assert gate["runtimeKind"] == "local"
    assert gate["requiresApproval"] is False
    assert gate["permission"] == "not_required"
    assert state["autoRepairEligibleCount"] >= 1
    assert state["retakePack"] is not None

    master.sceneFinalCheck = state
    plan = plan_local_auto_repair_from_final_check(master)
    assert plan.get("shouldAutoRetake") is True
    assert plan.get("reason") == "LOCAL_HIGH_CONF_HARD"
    assert plan.get("needsApiAsk") is not True


def test_seedance_api_still_ask_once_with_hard_finding():
    batch = SimpleNamespace(
        id="bb1",
        status="CandidateReady",
        references=[
            {
                "kind": "omniEquipmentDiagnostics",
                "verdict": "FAIL",
                "findings": [
                    {
                        "code": "BOOM_IN_FRAME",
                        "severity": "error",
                        "confidence": "high",
                        "message": "boom mic in frame",
                        "finalCheck": {
                            "retakeEligible": True,
                            "autoDestroy": False,
                            "acceptanceEligible": False,
                            "creativeTaste": False,
                            "authoritySource": "retake_context_package.prompt_law_crew_out",
                        },
                    }
                ],
                "equipmentFindings": [
                    {
                        "code": "BOOM_IN_FRAME",
                        "severity": "error",
                        "confidence": "high",
                        "message": "boom mic in frame",
                        "finalCheck": {
                            "retakeEligible": True,
                            "autoDestroy": False,
                            "acceptanceEligible": False,
                            "creativeTaste": False,
                            "authoritySource": "retake_context_package.prompt_law_crew_out",
                        },
                    }
                ],
            }
        ],
        duration=SimpleNamespace(plannedDuration=15.0, generatedDuration=15.0),
        generatorId="seedance-2.0",
    )
    master = SimpleNamespace(
        batchBlocks=[batch],
        sceneGeneratorId="seedance-2.0",
        sceneStitch=None,
        sceneFinalCheck=None,
    )
    state = open_final_check_after_stitch(master)
    gate = state["repairGate"]
    assert gate["runtimeKind"] == "api"
    assert gate["requiresApproval"] is True
    assert gate["permission"] == "required"
    master.sceneFinalCheck = state
    plan = plan_local_auto_repair_from_final_check(master)
    assert plan.get("shouldAutoRetake") is False
    assert plan.get("needsApiAsk") is True
