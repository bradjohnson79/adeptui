"""Scene Creator reference packet consumption — not cosmetics."""

from __future__ import annotations

import pytest

from app.scene_creator.integrity import parse_assessment_fixture
from app.scene_creator.readiness import build_scene_creator_readiness
from app.scene_creator.reference_packet import (
    GROUNDING_BLOCKED_QWEN,
    GroundingBlocked,
    apply_reference_packet,
    compile_reference_packet,
    family_pixel_slots,
    packet_ticks,
)


def _body(**kwargs):
    ctx = {
        "characters": [
            {
                "character_id": "c49371ed-ba6b-4c16-ba98-a8b28b72118b",
                "name": "Korri",
                "approved_casting_asset_id": "b6ab91dd-9d0a-4e4b-98b4-b26d268950dc",
            }
        ],
        "prop_entities": [
            {
                "id": "78c5be96-cd03-4969-9f8b-655fcefd28ea",
                "display_label": "Clear Glass Cup",
                "approved_asset_id": "b157845d-89d2-4263-bd4e-6089ba9d3d4d",
            }
        ],
        "ers_composite_asset_id": "79a55177-10be-438b-9ae7-477c1781abe7",
        "structured_blocking": {"lines": ["Character: Korri, Position: L10."]},
        "cinematographer": {"cameraId": "cam-1", "cameraStateHash": "hash-c1", "framing": "extreme_close_up"},
    }
    ctx.update(kwargs.get("ctx") or {})
    return {
        "prompt": "Korri stands behind the Schnick Coffee bar holding her green slimy coffee cup and looking toward camera.",
        "aspectRatio": "16:9",
        "creativeContext": ctx,
        "referenceImage": "should-be-replaced",
        "sourceAssetId": "should-be-replaced",
        "referenceIds": ["dump-1", "dump-2"],
    }


def test_zimage_consumes_character_only():
    body = apply_reference_packet(_body(), family="zimage", profile_grounded=True, production_loaded=True)
    pkt = body["creativeContext"]["referencePacket"]
    assert pkt["consumedAssetIds"] == ["b6ab91dd-9d0a-4e4b-98b4-b26d268950dc"]
    assert body["sourceAssetId"] == "b6ab91dd-9d0a-4e4b-98b4-b26d268950dc"
    assert body["referenceImage"] == "b6ab91dd-9d0a-4e4b-98b4-b26d268950dc"
    assert body["referenceIds"] == ["b6ab91dd-9d0a-4e4b-98b4-b26d268950dc"]
    assert body["creativeContext"]["reference_image_ids"] == ["b6ab91dd-9d0a-4e4b-98b4-b26d268950dc"]
    assert pkt["characters"][0]["consumption"] == "consumed"
    assert pkt["props"][0]["consumption"] == "semantic_only"
    assert pkt["environment"]["consumption"] == "semantic_only"
    ticks = packet_ticks(pkt)
    assert ticks["character"] == "ok"
    assert ticks["prop"] == "warn"
    assert ticks["environment"] == "warn"


def test_qwen_profile_grounded_does_not_silent_t2i():
    with pytest.raises(GroundingBlocked, match="cannot use the character"):
        apply_reference_packet(_body(), family="qwen2512", profile_grounded=True, production_loaded=True)


def test_qwen_allowed_when_no_profile_selected():
    body = apply_reference_packet(
        _body(),
        family="qwen2512",
        profile_grounded=False,
        production_loaded=False,
    )
    assert body["referenceIds"] == []
    assert body["creativeContext"]["referencePacket"]["characters"][0]["consumption"] == "unsupported"


def test_qwen_prompt_only_diagnostic_does_not_load_pixels():
    body = apply_reference_packet(
        _body(),
        family="qwen2512",
        profile_grounded=False,
        production_loaded=False,
        diagnostic_mode="prompt_only",
    )
    assert body.get("sourceAssetId") in (None, "")
    assert body["referenceIds"] == []
    assert body["creativeContext"]["referencePacket"]["consumedAssetIds"] == []


def test_character_diagnostic_loads_korri_not_cup():
    body = apply_reference_packet(
        _body(),
        family="zimage",
        profile_grounded=False,
        diagnostic_mode="character",
    )
    pkt = body["creativeContext"]["referencePacket"]
    assert pkt["consumedAssetIds"] == ["b6ab91dd-9d0a-4e4b-98b4-b26d268950dc"]
    assert pkt["characters"][0]["consumption"] == "consumed"
    assert pkt["environment"]["consumption"] == "semantic_only"


def test_abcd_consumption_not_prettiness():
    """A/B/C/D score which file the graph would load — not which frame looks nicest."""
    a = apply_reference_packet(
        _body(), family="qwen2512", profile_grounded=False, diagnostic_mode="prompt_only"
    )
    b = apply_reference_packet(
        _body(), family="zimage", profile_grounded=False, diagnostic_mode="ers_only"
    )
    c = apply_reference_packet(
        _body(), family="zimage", profile_grounded=False, diagnostic_mode="character"
    )
    d = apply_reference_packet(_body(), family="zimage", profile_grounded=True, production_loaded=True)
    assert a["referenceIds"] == []
    assert b["sourceAssetId"] == "79a55177-10be-438b-9ae7-477c1781abe7"
    assert c["sourceAssetId"] == "b6ab91dd-9d0a-4e4b-98b4-b26d268950dc"
    assert d["sourceAssetId"] == "b6ab91dd-9d0a-4e4b-98b4-b26d268950dc"
    assert d["referenceIds"] == ["b6ab91dd-9d0a-4e4b-98b4-b26d268950dc"]
    assert d["creativeContext"]["referencePacket"]["props"][0]["consumption"] == "semantic_only"
    assert d["creativeContext"]["referencePacket"]["environment"]["consumption"] == "semantic_only"


def test_llm_down_falls_back_to_connections(monkeypatch):
    from app.scene_creator import integrity as ig

    ready = {
        "ready": True,
        "status": "pass",
        "fingerprint": "fp-llm-down",
        "checks": {},
        "issues": [],
    }
    monkeypatch.setattr(ig, "_call_cd_llm", lambda facts: (_ for _ in ()).throw(RuntimeError("down")))
    ig._CACHE.pop("fp-llm-down", None)
    out = ig.assess_production_integrity(ready, {}, invoke_llm=True)
    assert out["status"] == "llm_unavailable"
    assert out["llm"]["available"] is False
    assert out["ready"] is True


def test_ers_only_diagnostic_loads_ers_not_korri():
    body = apply_reference_packet(
        _body(),
        family="zimage",
        profile_grounded=False,
        diagnostic_mode="ers_only",
    )
    pkt = body["creativeContext"]["referencePacket"]
    assert pkt["consumedAssetIds"] == ["79a55177-10be-438b-9ae7-477c1781abe7"]
    assert body["sourceAssetId"] == "79a55177-10be-438b-9ae7-477c1781abe7"


def test_profile_selected_but_not_loaded_blocks():
    with pytest.raises(GroundingBlocked, match="not loaded"):
        apply_reference_packet(_body(), family="zimage", profile_grounded=True, production_loaded=False)


def test_compile_shot_prompt_does_not_force_zimage(monkeypatch):
    from types import SimpleNamespace

    from app.codirector import entity_resolver as er
    from app.spatial_map.ers_contracts import EnvironmentReferencePackage, ShotRequest

    monkeypatch.setattr(
        er,
        "_character_metadata",
        lambda db, pid, ids: [
            {
                "character_id": "korri",
                "name": "Korri",
                "approved_casting_asset_id": "cast-korri",
                "reference_asset_ids": ["sheet-1", "sheet-2", "sheet-3"],
                "visual_style": "",
            }
        ],
    )
    monkeypatch.setattr(er, "_prop_metadata", lambda db, pid, ids: [])
    monkeypatch.setattr(er, "_project_visual_style", lambda db, pid: "")
    package = EnvironmentReferencePackage(
        project_id="proj-1",
        scene_layout_id="map-1",
        directional_assets={"north": None, "east": None, "south": None, "west": None},
        ers_composite_asset_id="ers-composite-1",
        placements=[{"characterId": "korri", "label": "Korri", "slotIndex": 0}],
    )
    shot = ShotRequest(index=0, raw_text="@Korri", characters=["korri"], prop_entities=[])
    body = er.compile_shot_prompt(SimpleNamespace(), "proj-1", shot, ers_package=package)
    refs = body["creativeContext"].get("reference_image_ids") or []
    assert refs[0] == "cast-korri"
    assert "sheet-1" not in refs
    assert body["modelFamilyPreference"] != "forced-silent"
    # Family may be recommended, but must not be a silent zimage override unique to refs.
    assert "ers-composite-1" in refs


def test_readiness_qwen_is_blocked():
    packet = compile_reference_packet(
        char_meta=[{"character_id": "c1", "name": "Korri", "approved_casting_asset_id": "cast-1"}],
        prop_meta=[{"id": "p1", "display_label": "Cup", "approved_asset_id": "prop-1"}],
        ers_composite_asset_id="ers-1",
    )
    packet["characters"][0]["consumption"] = "unsupported"
    packet["props"][0]["consumption"] = "unsupported"
    packet["environment"]["consumption"] = "unsupported"
    packet["roles"] = packet["characters"] + packet["props"] + [packet["environment"]]
    packet["consumedAssetIds"] = []
    ready = build_scene_creator_readiness(
        production_context={
            "loaded": True,
            "handoffId": "h1",
            "ersLibraryAssetId": "ers-1",
            "spatialMapId": "map-1",
            "fingerprint": "fp",
        },
        packet=packet,
        family="qwen2512",
        camera_hash="abc",
        scene_id="s1",
    )
    assert ready["status"] == "blocked"
    assert ready["ready"] is False


def test_readiness_idle_without_profile():
    ready = build_scene_creator_readiness(production_context=None, selected_profile=None)
    assert ready["status"] == "idle"


def test_integrity_json_contract():
    parsed = parse_assessment_fixture(
        {"status": "advisory", "issues": [{"type": "blocking_conflict", "message": "Prompt vs map"}], "summary": "ok"}
    )
    assert parsed["status"] == "advisory"


def test_delete_refuses_timeline_lineage(monkeypatch):
    from types import SimpleNamespace

    from app.scene_creator import service as svc
    from app.spatial_map.ers_contracts import SceneShot, SceneShotCandidate, SceneShotTakeMemory

    cand = SceneShotCandidate(id="cand-1", asset_id="asset-1", status="complete")
    shot = SceneShot(
        project_id="proj",
        scene_id="scene",
        sheet_id="sheet",
        candidates=[cand],
        take_memory=SceneShotTakeMemory(takeState={"lastTimelineAssetId": "asset-1"}),
    )
    monkeypatch.setattr(svc, "_require_shot", lambda *a, **k: shot)
    monkeypatch.setattr(svc, "_sync_candidate_jobs", lambda *a, **k: None)
    with pytest.raises(svc.SceneCreatorError, match="Timeline"):
        svc.delete_shot_candidate(SimpleNamespace(), "proj", "shot", "cand-1")


def test_family_slots():
    assert family_pixel_slots("qwen2512") == 0
    assert family_pixel_slots("zimage") >= 1
    assert GROUNDING_BLOCKED_QWEN
