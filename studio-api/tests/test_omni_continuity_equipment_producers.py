"""Unit tests for Omni Continuity + Equipment QC producers (Final Check #4-5)."""

from __future__ import annotations

from types import SimpleNamespace

from app.director_timeline_w46.generation import omni_continuity_qc as cont
from app.director_timeline_w46.generation import omni_equipment_qc as equip
from app.director_timeline_w46.scene_final_check import (
    attach_retake_repair_from_pack,
    build_category_shell,
    build_retake_pack,
    collect_batch_qc_packets,
    map_continuity_finding,
    map_equipment_finding,
    plan_local_auto_repair_from_final_check,
    qualify_retake,
)


def _batch(**kwargs):
    defaults = {
        "id": "bb_test",
        "order": 1,
        "promptSegments": [SimpleNamespace(text="Anadriya and Korri in Quarters. No crew.")],
        "references": [],
        "status": "CandidateReady",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_continuity_authority_never_overwrites_canon():
    batch = _batch()
    auth = cont.narrative_continuity_authority(batch)
    assert auth["authoritySource"] == "continuity_canon"
    assert auth["neverOverwriteCanonFromObservation"] is True
    assert "Quarters" in auth["canonText"]


def test_continuity_evaluate_high_conf_teleport_hard_retake_eligible():
    auth = {
        "authoritySource": "continuity_canon",
        "establishedAuthority": True,
        "vsCanon": True,
    }
    observed = {
        "summary": "Character teleports across the room",
        "continuityFlags": ["teleport"],
        "availability": "ready",
        "confidence": 0.9,
        "role": "observation_only",
    }
    qc = cont.evaluate_continuity_qc(auth, observed)
    assert qc["kind"] == cont.CONTINUITY_QC_KIND
    assert qc["verdict"] == "FAIL"
    assert qc["findings"]
    assert qc["findings"][0]["code"] == "CONTINUITY_TELEPORT"
    assert qc["findings"][0]["finalCheck"]["retakeEligible"] is True
    mapped = map_continuity_finding(qc["findings"][0], verdict=qc["verdict"])
    assert mapped["retakeEligible"] is True
    assert qualify_retake(mapped)["autoRetake"] is True


def test_continuity_weak_visual_crs_conflict_uncertain_no_auto():
    auth = {"authoritySource": "continuity_canon", "establishedAuthority": True}
    observed = {
        "summary": "blurry",
        "continuityFlags": [],
        "availability": "ready",
        "confidence": 0.2,
        "role": "observation_only",
    }
    temporal = {
        "assessment": {"differences": ["Action remained unfinished"], "confidence": 0.8},
        "availability": "ready",
    }
    qc = cont.evaluate_continuity_qc(auth, observed, temporal_packet=temporal)
    assert qc["verdict"] == "UNCERTAIN"
    assert qc["findings"][0]["code"] == "CONTINUITY_CRS_TEMPORAL_CONFLICT"
    assert qc["findings"][0]["finalCheck"]["retakeEligible"] is False
    assert qc["findings"][0]["finalCheck"]["autoDestroy"] is False


def test_continuity_unavailable_uncertain_not_pass():
    auth = {"authoritySource": "continuity_canon"}
    qc = cont.evaluate_continuity_qc(auth, {"availability": "unavailable", "error": "boom"})
    assert qc["verdict"] == "UNCERTAIN"
    assert qc["sceneFinishedEligible"] is False
    assert qc["verdict"] != "PASS"


def test_continuity_pass_when_gate_ran_no_breaks():
    auth = {"authoritySource": "continuity_canon"}
    qc = cont.evaluate_continuity_qc(
        auth,
        {
            "summary": "Anadriya and Korri talk in Quarters",
            "continuityFlags": [],
            "availability": "ready",
            "confidence": 0.8,
        },
    )
    assert qc["verdict"] == "PASS"
    assert qc["findings"] == []


def test_persist_continuity_packet_kind_accepted_by_ingest():
    batch = _batch()
    qc = cont.evaluate_continuity_qc(
        {"authoritySource": "continuity_canon", "establishedAuthority": True},
        {
            "summary": "sides flip mid shot",
            "continuityFlags": ["screen direction flip"],
            "availability": "ready",
            "confidence": 0.85,
        },
    )
    cont.persist_continuity_qc_diagnostics(batch, qc)
    kinds = [r.get("kind") for r in batch.references]
    assert cont.CONTINUITY_QC_KIND in kinds
    master = SimpleNamespace(batchBlocks=[batch], sceneFinalCheck=None)
    packets = collect_batch_qc_packets(master)
    assert packets["continuityGateSeen"] is True
    assert packets["continuity"]
    shell = build_category_shell(
        [],
        continuity_gate_seen=True,
        continuity_findings=packets["continuity"],
    )
    by = {c["category"]: c for c in shell}
    assert by["continuity"]["status"] == "fail"
    assert by["continuity"]["status"] != "not_run"


def test_equipment_camera_move_never_auto_hard():
    assert equip.is_camera_move_language("slow push-in on Anadriya") is True
    assert equip.is_camera_move_language("dolly in toward Korri") is True
    assert equip.is_camera_move_language("boom up as camera move") is True
    assert equip.classify_equipment_code("dolly push-in") is None
    qc = equip.evaluate_equipment_qc(
        {
            "summary": "Camera dollies in on Korri",
            "equipmentFlags": ["dolly in"],
            "cameraMoves": [{"motionType": "dolly", "direction": "in"}],
            "availability": "ready",
            "confidence": 0.9,
        }
    )
    hard = [f for f in qc["findings"] if f.get("code") != "CREATIVE_CAMERA_TASTE"]
    assert hard == []
    assert qc["verdict"] == "PASS"


def test_equipment_camera_crew_hard_uses_rcp_authority():
    qc = equip.evaluate_equipment_qc(
        {
            "summary": "Camera crew visible behind Anadriya",
            "equipmentFlags": ["camera crew"],
            "cameraMoves": [],
            "availability": "ready",
            "confidence": 0.92,
        }
    )
    assert qc["verdict"] == "FAIL"
    assert qc["findings"]
    codes = {f["code"] for f in qc["equipmentFindings"]}
    assert "CAMERA_CREW_IN_FRAME" in codes or "UNAUTHORIZED_PRODUCTION_EQUIPMENT" in codes
    assert qc["authority"]["authoritySource"] == "retake_context_package.prompt_law_crew_out"
    mapped = map_equipment_finding(qc["equipmentFindings"][0], verdict="FAIL")
    assert mapped["retakeEligible"] is True
    assert mapped["authoritySource"] == "retake_context_package.prompt_law_crew_out"
    assert "camera" in (mapped.get("alsoCategories") or [])



def test_equipment_bare_interviewer_uncertain_not_auto_retake():
    """Omni flag 'interviewer' alone → UNCERTAIN (12B off-screen authority)."""
    from app.director_timeline_w46.generation.retake_context_package import (
        CREW_OBSERVATION_UNCERTAIN,
        classify_crew_equipment_observation,
        observation_matches_unauthorized_equipment,
    )

    assert classify_crew_equipment_observation("interviewer") == CREW_OBSERVATION_UNCERTAIN
    assert observation_matches_unauthorized_equipment("interviewer") is False
    assert equip.classify_equipment_code("interviewer") is None
    qc = equip.evaluate_equipment_qc(
        {
            "summary": "Characters answer an interviewer",
            "equipmentFlags": ["interviewer"],
            "cameraMoves": [],
            "availability": "ready",
            "confidence": 0.9,
        }
    )
    assert qc["verdict"] == "UNCERTAIN"
    assert qc["reason"] == "CREW_FRAMING_UNCERTAIN"
    assert qc["sceneFinishedEligible"] is False
    hard = [
        f
        for f in qc["findings"]
        if f.get("code")
        not in {"CREATIVE_CAMERA_TASTE", "CREW_OBSERVATION_UNCERTAIN", "CREW_OFFSCREEN_AUTHORIZED"}
    ]
    assert hard == []
    unc = [f for f in qc["findings"] if f.get("code") == "CREW_OBSERVATION_UNCERTAIN"]
    assert unc
    assert unc[0]["finalCheck"]["retakeEligible"] is False
    assert unc[0]["finalCheck"]["autoDestroy"] is False
    mapped = map_equipment_finding(unc[0], verdict=qc["verdict"])
    assert mapped["retakeEligible"] is False


def test_equipment_offscreen_interviewer_authorized_pass():
    """Behind-camera / off-screen interviewer is AUTHORIZED (12B refire prompt)."""
    from app.director_timeline_w46.generation.retake_context_package import (
        CREW_OBSERVATION_AUTHORIZED_OFFSCREEN,
        classify_crew_equipment_observation,
        observation_matches_unauthorized_equipment,
    )

    assert (
        classify_crew_equipment_observation("interviewer behind the camera")
        == CREW_OBSERVATION_AUTHORIZED_OFFSCREEN
    )
    assert observation_matches_unauthorized_equipment("interviewer behind the camera") is False
    qc = equip.evaluate_equipment_qc(
        {
            "summary": "Anadriya and Korri in Quarters; interviewer behind the camera off-screen",
            "equipmentFlags": ["interviewer behind the camera"],
            "cameraMoves": [],
            "availability": "ready",
            "confidence": 0.91,
        }
    )
    assert qc["verdict"] == "PASS"
    assert qc["sceneFinishedEligible"] is True
    assert qc["equipmentFindings"] == []
    assert any(f.get("code") == "CREW_OFFSCREEN_AUTHORIZED" for f in qc["findings"])
    assert all(f.get("finalCheck", {}).get("retakeEligible") is not True or f.get("code") == "x" for f in qc["findings"] if f.get("code") != "CREATIVE_CAMERA_TASTE")


def test_equipment_inframe_interviewer_still_hard():
    """Visible / in-frame interviewer or crew → Hard CREW_IN_FRAME retakeEligible."""
    from app.director_timeline_w46.generation.retake_context_package import (
        CREW_OBSERVATION_HARD,
        classify_crew_equipment_observation,
        observation_matches_unauthorized_equipment,
    )

    assert (
        classify_crew_equipment_observation("interviewer visible in frame")
        == CREW_OBSERVATION_HARD
    )
    assert observation_matches_unauthorized_equipment("interviewer visible in frame") is True
    qc = equip.evaluate_equipment_qc(
        {
            "summary": "Human interviewer visible in picture with cameras and crew members visible",
            "equipmentFlags": ["interviewer"],
            "cameraMoves": [],
            "availability": "ready",
            "confidence": 0.93,
        }
    )
    assert qc["verdict"] == "FAIL"
    assert any(
        f.get("code") in {"CREW_IN_FRAME", "CAMERA_CREW_IN_FRAME", "UNAUTHORIZED_PRODUCTION_EQUIPMENT", "DIEGETIC_CREW"}
        for f in qc["equipmentFindings"]
    )
    assert any(f.get("finalCheck", {}).get("retakeEligible") is True for f in qc["equipmentFindings"])


def test_extract_does_not_salvage_bare_interviewer_without_inframe():
    packet = {
        "summary": "Two characters speak with an interviewer present off camera",
        "availability": "ready",
        "equipmentFlags": [],
        "visualEvents": [],
    }
    obs = equip.extract_equipment_observations(packet)
    assert "interviewer" not in [str(x).lower() for x in obs["equipmentFlags"]]


def test_equipment_boom_in_frame_hard():
    qc = equip.evaluate_equipment_qc(
        {
            "summary": "Boom mic dips into frame",
            "equipmentFlags": ["boom in frame"],
            "availability": "ready",
            "confidence": 0.88,
        }
    )
    assert qc["verdict"] == "FAIL"
    assert any(f["code"] == "BOOM_IN_FRAME" for f in qc["equipmentFindings"])


def test_equipment_unavailable_uncertain_not_invented_fail():
    qc = equip.evaluate_equipment_qc({"availability": "unavailable", "error": "vram"})
    assert qc["verdict"] == "UNCERTAIN"
    assert qc["reason"] == "OMNI_EQUIPMENT_UNAVAILABLE"
    assert qc["sceneFinishedEligible"] is False
    # Must not invent a crew Hard finding
    assert not any(
        f.get("code") in equip.EQUIPMENT_QC_KINDS or "CREW" in str(f.get("code"))
        for f in qc.get("equipmentFindings") or []
    )


def test_persist_equipment_packet_ingest_and_preserve_pack():
    batch = _batch()
    qc = equip.evaluate_equipment_qc(
        {
            "summary": "Diegetic film crew in frame",
            "equipmentFlags": ["film crew", "camera crew"],
            "availability": "ready",
            "confidence": 0.9,
        }
    )
    equip.persist_equipment_qc_diagnostics(batch, qc)
    master = SimpleNamespace(batchBlocks=[batch], sceneFinalCheck=None)
    packets = collect_batch_qc_packets(master)
    assert packets["equipmentGateSeen"] is True
    shell = build_category_shell(
        [],
        equipment_gate_seen=True,
        equipment_findings=packets["equipment"],
    )
    eligible = []
    from app.director_timeline_w46.scene_final_check import auto_repair_eligible_findings

    eligible = auto_repair_eligible_findings(shell)
    assert eligible
    pack = build_retake_pack(eligible)
    assert "crew" in pack["WHAT_CHANGE"].lower() or "OUT OF FRAME" in pack["WHAT_CHANGE"]
    assert "Anadriya" in pack["WHAT_PRESERVE"] or "cast" in pack["WHAT_PRESERVE"].lower() or "Quarters" in pack["WHAT_PRESERVE"] or "identity" in pack["WHAT_PRESERVE"].lower()
    repair = attach_retake_repair_from_pack(batch, pack, eligible)
    assert repair["kind"] == "dialogueRetakeRepair"
    assert repair["neverInventAuthorityFromBadOutput"] is True
    assert "OUT OF FRAME" in repair["userCorrection"]["delta"]


def test_plan_local_auto_repair_api_asks_once():
    pack = {"WHAT_CHANGE": "remove crew", "WHAT_PRESERVE": "cast", "WHAT_WRONG": ["crew"]}
    master = SimpleNamespace(
        batchBlocks=[],
        sceneFinalCheck=SimpleNamespace(
            model_dump=lambda: {
                "lifecycleStatus": "FINAL_CHECK",
                "autoRepairEligibleCount": 1,
                "retakePack": pack,
                "retakeLoopCount": 0,
                "maxRetakeLoops": 3,
                "repairGate": {"runtimeKind": "api", "permission": "required"},
                "categories": [
                    {
                        "category": "equipment",
                        "findings": [
                            {
                                "code": "CAMERA_CREW_IN_FRAME",
                                "taxonomy": "Hard",
                                "retakeEligible": True,
                                "confidence": "high",
                            }
                        ],
                    }
                ],
            }
        ),
    )
    plan = plan_local_auto_repair_from_final_check(master)
    assert plan.get("shouldAutoRetake") is False
    assert plan.get("needsApiAsk") is True


def test_plan_local_auto_repair_local_high_conf():
    pack = {"WHAT_CHANGE": "remove crew", "WHAT_PRESERVE": "Anadriya/Korri/dialogue/quarters"}
    master = SimpleNamespace(
        batchBlocks=[],
        sceneFinalCheck={
            "lifecycleStatus": "FINAL_CHECK",
            "autoRepairEligibleCount": 1,
            "retakePack": pack,
            "retakeLoopCount": 0,
            "maxRetakeLoops": 3,
            "repairGate": {"runtimeKind": "local", "permission": "not_required"},
            "categories": [
                {
                    "category": "equipment",
                    "findings": [
                        {
                            "code": "CAMERA_CREW_IN_FRAME",
                            "taxonomy": "Hard",
                            "retakeEligible": True,
                            "confidence": "high",
                        }
                    ],
                }
            ],
        },
    )
    plan = plan_local_auto_repair_from_final_check(master)
    assert plan.get("shouldAutoRetake") is True
    assert plan.get("lifecycleStatus") == "REPAIRING"


def test_plan_max_loops_cleanup_could_not_resolve():
    master = SimpleNamespace(
        batchBlocks=[],
        sceneFinalCheck={
            "autoRepairEligibleCount": 1,
            "retakePack": {"WHAT_CHANGE": "x"},
            "retakeLoopCount": 3,
            "maxRetakeLoops": 3,
            "repairGate": {"runtimeKind": "local"},
            "categories": [],
        },
    )
    plan = plan_local_auto_repair_from_final_check(master)
    assert plan.get("cleanupFailed") is True
    assert plan.get("message") == "AUTOMATIC CLEANUP COULD NOT RESOLVE"