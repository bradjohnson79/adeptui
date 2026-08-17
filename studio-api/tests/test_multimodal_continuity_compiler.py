"""Deterministic tests for the Co-Director multimodal continuity compiler."""

from __future__ import annotations

import pytest

from app.codirector.knowledgebase.ers_compiler import compile_environment_reference_sheet_prompt
from app.codirector.knowledgebase.multimodal_continuity.packet import compile_packet
from app.codirector.knowledgebase.multimodal_continuity.schema import ContinuityCompileError
from app.codirector.knowledgebase.multimodal_continuity.sync_validator import validate_sync
from app.codirector.knowledgebase.multimodal_continuity.terminology import GLOSSARY
from app.codirector.vision.visual_canon import EnvironmentVisualCanon

ORIGINAL_ID = "4d3062e8-8c30-4230-8376-bc25d1d4f735"
ATLAS_ID = "caa72759-d965-41f9-b1d5-77cdcf9b9614"

KORRI = {
    "label": "Korri",
    "characterId": "korri-schnick",
    "miniPrompt": "standing behind the barista bar beside the espresso station on the staff side",
    "gridColumn": 5,
    "gridRow": 5,
    "visible": True,
}


def _korri_packet(**kwargs):
    defaults = dict(
        scene_title="Schnick Coffee",
        original_asset_id=ORIGINAL_ID,
        atlas_asset_id=ATLAS_ID,
        characters=[KORRI],
        panel_task="occupied_scale",
        provider="qwen",
    )
    defaults.update(kwargs)
    return compile_packet(**defaults)


def test_korri_behind_counter_json_english_chinese_agree() -> None:
    packet = _korri_packet()
    actor = packet.continuityJson.actors[0]
    assert actor.relativePosition == "behind_service_counter"
    assert actor.landmark == "espresso_station"
    assert actor.barrierSide == "employee_side"
    assert actor.factStatus == "creator_confirmed"
    assert actor.gridCell == "F6"
    en = packet.englishPrompt.lower()
    zh = packet.chinesePrompt
    assert GLOSSARY["behind_service_counter"][0] in en
    assert GLOSSARY["behind_service_counter"][1] in zh
    assert GLOSSARY["espresso_station"][0] in en
    assert GLOSSARY["espresso_station"][1] in zh
    assert GLOSSARY["employee_side"][0] in en
    assert GLOSSARY["employee_side"][1] in zh
    assert packet.syncOk is True


def test_english_behind_vs_chinese_front_blocks() -> None:
    packet = _korri_packet()
    packet.chinesePrompt = packet.chinesePrompt.replace(
        GLOSSARY["behind_service_counter"][1],
        GLOSSARY["front_of_counter"][1],
    )
    with pytest.raises(ContinuityCompileError) as exc:
        validate_sync(packet)
    assert exc.value.field == "sync"
    assert any("behind_service_counter" in c for c in exc.value.conflicts)


def test_canon_lineage_mismatch_blocks() -> None:
    canon = EnvironmentVisualCanon(
        availability="available",
        sourceAssetId=ATLAS_ID,
        groundingFingerprint="fp-atlas",
    )
    with pytest.raises(ContinuityCompileError) as exc:
        compile_packet(
            original_asset_id=ORIGINAL_ID,
            atlas_asset_id=ATLAS_ID,
            lineage_fingerprint="fp-original",
            canon=canon,
            characters=[KORRI],
        )
    assert exc.value.field == "sourceAuthority"


def test_unavailable_canon_still_compiles_from_map() -> None:
    canon = EnvironmentVisualCanon(
        availability="unavailable",
        unavailableReason="The vision provider returned no parseable environment canon.",
        sourceAssetId=ATLAS_ID,
    )
    packet = compile_packet(
        original_asset_id=ORIGINAL_ID,
        atlas_asset_id=ATLAS_ID,
        canon=canon,
        characters=[KORRI],
        panel_task="occupied_scale",
    )
    assert packet.continuityJson.actors[0].relativePosition == "behind_service_counter"
    assert any("unavailable" in u.lower() for u in packet.continuityJson.uncertainties)


def test_qwen_vs_gpt_prompt_shape() -> None:
    qwen = _korri_packet(provider="qwen")
    gpt = _korri_packet(provider="gpt-image-2")
    assert qwen.providerPrompt.index("参考图像") < qwen.providerPrompt.index("JSON:")
    assert "保持同一物理环境" in qwen.providerPrompt
    assert gpt.englishPrompt in gpt.providerPrompt
    assert "Chinese constraints:" in gpt.providerPrompt
    assert "Hard invariants:" in gpt.providerPrompt
    assert gpt.providerPrompt.index("Preserve this physical set") < gpt.providerPrompt.index("Chinese constraints:")


def test_same_packet_drives_qwen_gpt_krea2() -> None:
    # Pass C: the SAME canonical continuity packet drives all three renderers.
    # No second compiler, no Krea-specific truth model — same packet, different order.
    qwen = _korri_packet(provider="qwen")
    gpt = _korri_packet(provider="gpt-image-2")
    krea = _korri_packet(provider="krea2")
    # Same canonical facts across all three providers.
    assert qwen.fingerprint == gpt.fingerprint == krea.fingerprint
    assert qwen.syncOk == gpt.syncOk == krea.syncOk is True
    assert qwen.hardInvariants == gpt.hardInvariants == krea.hardInvariants
    assert [a.actor for a in qwen.continuityJson.actors] == [
        a.actor for a in gpt.continuityJson.actors
    ] == [a.actor for a in krea.continuityJson.actors]
    # Krea 2 is Qwen-Image-based → Chinese-first prompt shape (like Qwen).
    assert krea.providerPrompt.index("参考图像") < krea.providerPrompt.index("JSON:")
    assert "保持同一物理环境" in krea.providerPrompt
    assert "krea2 production_ers" in krea.providerPrompt  # Krea-specific view phrase
    # Qwen and Krea share the Chinese-first shape; GPT is English-primary.
    assert qwen.providerPrompt != krea.providerPrompt  # distinct view phrase
    assert gpt.providerPrompt != krea.providerPrompt


def test_semantic_continuity_not_identity_conditioning() -> None:
    # Pass C: semantic continuity ≠ identity conditioning. The packet carries
    # the environment description + spatial facts (semantic continuity) but
    # the referenceImage is the ENVIRONMENT plate, not Korri's character pixels.
    # Krea receiving this packet gets the correct description/spatial facts but
    # NOT Korri's visual identity — so a Krea ERS image cannot claim identity
    # preservation for Korri from this packet alone.
    packet = _korri_packet(provider="krea2")
    assert packet.referenceImage
    assert packet.referenceImage.get("assetId") == ORIGINAL_ID  # environment plate
    assert packet.referenceImage.get("type") == "original_environment"
    # Korri is carried as a placed actor (semantic placement), not as pixel identity.
    korri = packet.continuityJson.actors[0]
    assert korri.actor == "Korri"
    assert korri.factStatus == "creator_confirmed"
    # The packet does NOT carry a character identity image for Korri.
    assert not getattr(korri, "identityAssetId", None)
    assert not any(getattr(a, "identityAssetId", None) for a in packet.continuityJson.actors)


def test_top_down_omits_occupied_prose() -> None:
    top = _korri_packet(panel_task="top_down", provider="qwen")
    occupied = _korri_packet(panel_task="occupied_scale", provider="qwen")
    assert GLOSSARY["behind_service_counter"][0] not in top.englishPrompt.lower()
    assert "电影化占用" in top.chinesePrompt
    assert top.continuityJson.actors[0].relativePosition == "behind_service_counter"
    assert GLOSSARY["behind_service_counter"][0] in occupied.englishPrompt.lower()
    assert "Korri" in occupied.englishPrompt


def test_occluded_couch_remains_in_json() -> None:
    canon = EnvironmentVisualCanon(
        availability="available",
        sourceAssetId=ORIGINAL_ID,
        furniture={"couch": {"present": True, "location": "right wall"}},
        fixedArchitecture={"serviceCounterOrBar": {"location": "rear wall"}},
    )
    packet = compile_packet(
        original_asset_id=ORIGINAL_ID,
        atlas_asset_id=ATLAS_ID,
        canon=canon,
        characters=[KORRI],
        panel_task="east_elevation",
        provider="gpt-image-2",
    )
    couch = packet.continuityJson.persistentFurniture["couch"]
    assert couch["present"] is True
    blob = (packet.englishPrompt + " " + " ".join(packet.continuityJson.occlusionNotes)).lower()
    assert "occluded" in blob or "couch exists" in blob
    assert "no couch" not in blob


def test_hard_invariants_cannot_be_dropped() -> None:
    canon = EnvironmentVisualCanon(
        availability="available",
        sourceAssetId=ORIGINAL_ID,
        geometry={"windowLocations": ["storefront"], "doorOrEntranceLocations": ["front"]},
        fixedArchitecture={"serviceCounterOrBar": {"location": "rear wall"}},
        hardInvariants=["do not move the service counter", "preserve window count and location"],
    )
    packet = compile_packet(
        original_asset_id=ORIGINAL_ID,
        atlas_asset_id=ATLAS_ID,
        canon=canon,
        characters=[KORRI],
        panel_task="occupied_scale",
        provider="qwen",
    )
    compiled = compile_environment_reference_sheet_prompt(
        environment_name="Schnick Coffee",
        continuity_packet=packet,
        characters=[KORRI],
    )
    prompt = compiled["prompt"]
    assert "behind the service counter" in prompt.lower()
    assert GLOSSARY["behind_service_counter"][1] in prompt
    assert "service counter" in prompt.lower()
    assert "storefront windows" in prompt.lower() or "window" in prompt.lower()
    assert "LOCKED INVARIANTS" in prompt or "do not move the service counter" in prompt
    assert "AUTHORITATIVE ENVIRONMENT (Co-Director Vision):" not in prompt


def test_packet_fingerprint_changes_with_placement() -> None:
    a = _korri_packet()
    other = dict(KORRI)
    other["miniPrompt"] = "sitting in customer seating"
    b = compile_packet(
        scene_title="Schnick Coffee",
        original_asset_id=ORIGINAL_ID,
        atlas_asset_id=ATLAS_ID,
        characters=[other],
        panel_task="occupied_scale",
        provider="qwen",
    )
    assert a.fingerprint != b.fingerprint


def test_validate_sync_accepts_matching_packet() -> None:
    packet = _korri_packet()
    validate_sync(packet)
    assert packet.syncOk is True
    assert packet.syncConflicts == []
