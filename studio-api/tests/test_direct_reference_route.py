"""Direct Reference Route: checked Timeline References only reach Comfy sockets."""

from __future__ import annotations

from types import SimpleNamespace

from app.director_timeline_w46.contracts import BatchBlock, DurationState, TimelinePromptSegment
from app.director_timeline_w46.generation.direct_reference import (
    attach_direct_reference_payload,
    build_direct_reference_payload,
    delivery_error,
)
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.director_timeline_w46.generation.r2v import attach_canonical_r2v
from app.director_timeline_w46.generation.registry import get_registry


def _batch(*, generator_id: str, binding_ids: list[str], leftovers: list[dict] | None = None) -> BatchBlock:
    return BatchBlock(
        sceneId="scene-b",
        generatorId=generator_id,
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[
            TimelinePromptSegment(
                text="Addex is sitting. Korri sits next to him.",
                start=0,
                length=5,
                referenceBindingIds=binding_ids,
            )
        ],
        references=list(leftovers or []),
    )


def _resolve(binding_id: str) -> dict:
    catalog = {
        "bind-korri": {
            "bindingId": "bind-korri",
            "assetId": "asset-korri",
            "identityId": "id-korri",
            "mediaKind": "image",
            "referenceType": "character",
            "alias": "Korri40YearsOld",
            "broken": False,
            "brokenReason": None,
            "approvalStatus": "approved",
        },
        "bind-addex": {
            "bindingId": "bind-addex",
            "assetId": "asset-addex",
            "identityId": "id-addex",
            "mediaKind": "image",
            "referenceType": "character",
            "alias": "Addex",
            "broken": False,
            "brokenReason": None,
            "approvalStatus": "approved",
        },
        "bind-anadriya": {
            "bindingId": "bind-anadriya",
            "assetId": "asset-anadriya",
            "identityId": "id-anadriya",
            "mediaKind": "image",
            "referenceType": "character",
            "alias": "Anadriya",
            "broken": False,
            "brokenReason": None,
            "approvalStatus": "approved",
        },
        "bind-place": {
            "bindingId": "bind-place",
            "assetId": "asset-place",
            "identityId": "id-place",
            "mediaKind": "image",
            "referenceType": "environment",
            "alias": "SchnickCoffeeHouse",
            "broken": False,
            "brokenReason": None,
            "approvalStatus": "approved",
        },
        "bind-extra": {
            "bindingId": "bind-extra",
            "assetId": "asset-extra",
            "identityId": "id-extra",
            "mediaKind": "image",
            "referenceType": "prop",
            "alias": "Thermos",
            "broken": False,
            "brokenReason": None,
            "approvalStatus": "approved",
        },
        "bind-voice": {
            "bindingId": "bind-voice",
            "assetId": "asset-voice",
            "identityId": "id-korri",
            "mediaKind": "audio",
            "referenceType": "audio",
            "alias": "KorriVoice",
            "broken": False,
            "brokenReason": None,
            "approvalStatus": "approved",
        },
    }
    return catalog[binding_id]


def _install_resolver(monkeypatch, tmp_path) -> None:
    from app.director_timeline_w46.generation import direct_reference as dr

    def fake_resolve(db, project_id, binding_id, fallback_asset_id=None):
        return _resolve(str(binding_id))

    def fake_asset(db, asset_id: str):
        kind = "audio" if asset_id == "asset-voice" else "image"
        path = tmp_path / f"{asset_id}.png" if kind == "image" else tmp_path / f"{asset_id}.wav"
        path.write_bytes(b"x")
        return SimpleNamespace(id=asset_id, kind=kind, path=str(path))

    monkeypatch.setattr(dr, "resolve_binding_id", fake_resolve)
    monkeypatch.setattr(dr, "_asset_record", fake_asset)


def test_payload_uses_checked_bindings_only(monkeypatch, tmp_path):
    _install_resolver(monkeypatch, tmp_path)
    leftovers = [
        {
            "kind": "characterIdentity",
            "identityNames": ["Anadriya"],
            "identityAssetIds": ["asset-anadriya"],
            "source": "project_character",
            "consumed": True,
        }
    ]
    batch = _batch(
        generator_id="minimax-h3",
        binding_ids=["bind-addex", "bind-korri"],
        leftovers=leftovers,
    )
    payload = build_direct_reference_payload(
        None,
        project_id="proj",
        scene_id="scene-b",
        batch=batch,
        generator_id="minimax-h3",
    )
    assert [item.canonicalTag for item in payload.characters] == ["@Addex", "@Korri40YearsOld"]
    assert "Anadriya" not in " ".join(payload.tags())
    assert "asset-anadriya" not in payload.asset_ids()
    assert payload.audio == []
    assert payload.delivery_ok()


def test_prose_names_do_not_enter_payload(monkeypatch, tmp_path):
    _install_resolver(monkeypatch, tmp_path)
    batch = _batch(generator_id="minimax-h3", binding_ids=["bind-addex"])
    batch.promptSegments[0].text = "Anadriya and Korri walk with Addex."
    payload = build_direct_reference_payload(
        None,
        project_id="proj",
        scene_id="scene-b",
        batch=batch,
        generator_id="minimax-h3",
    )
    assert payload.tags() == ["@Addex"]
    assert "Korri" not in "".join(payload.tags())
    assert "Anadriya" not in "".join(payload.tags())


def test_h3_sockets_follow_checked_order(monkeypatch, tmp_path):
    _install_resolver(monkeypatch, tmp_path)
    batch = _batch(generator_id="minimax-h3", binding_ids=["bind-addex", "bind-korri"])
    payload = build_direct_reference_payload(
        None,
        project_id="proj",
        scene_id="scene-b",
        batch=batch,
        generator_id="minimax-h3",
    )
    sockets = {bind.socket: bind.canonicalTag for bind in payload.sockets}
    assert sockets == {"ref_image_0": "@Addex", "ref_image_1": "@Korri40YearsOld"}


def test_seedance_delivers_checked_pictures(monkeypatch, tmp_path):
    _install_resolver(monkeypatch, tmp_path)
    batch = _batch(generator_id="seedance-2.0", binding_ids=["bind-addex", "bind-korri"])
    payload = build_direct_reference_payload(
        None,
        project_id="proj",
        scene_id="scene-b",
        batch=batch,
        generator_id="seedance-2.0-mini",
    )
    assert delivery_error(payload) is None
    assert [bind.socket for bind in payload.sockets] == ["ref_image_0", "ref_image_1"]
    assert [bind.canonicalTag for bind in payload.sockets] == ["@Addex", "@Korri40YearsOld"]


def test_seedance_blocks_a_picture_past_the_slot_limit(monkeypatch, tmp_path):
    _install_resolver(monkeypatch, tmp_path)
    batch = _batch(
        generator_id="seedance-2.0",
        binding_ids=["bind-addex", "bind-korri", "bind-anadriya", "bind-place", "bind-extra"],
    )
    payload = build_direct_reference_payload(
        None,
        project_id="proj",
        scene_id="scene-b",
        batch=batch,
        generator_id="seedance-2.0",
    )
    err = delivery_error(payload)
    assert err is not None
    assert err["blocked"][-1]["reason"] == "over_limit"
    assert len(payload.sockets) == 4


def test_seedance_refuses_a_voice_reference(monkeypatch, tmp_path):
    _install_resolver(monkeypatch, tmp_path)
    batch = _batch(generator_id="seedance-2.0-mini", binding_ids=["bind-addex", "bind-voice"])
    payload = build_direct_reference_payload(
        None,
        project_id="proj",
        scene_id="scene-b",
        batch=batch,
        generator_id="seedance-2.0-mini",
    )
    err = delivery_error(payload)
    assert err is not None
    assert any(item["reason"] == "unsupported_audio_socket" for item in err["blocked"])


def test_ltx_blocks_second_character(monkeypatch, tmp_path):
    _install_resolver(monkeypatch, tmp_path)
    batch = _batch(generator_id="ltx-2.5", binding_ids=["bind-addex", "bind-korri"])
    payload = build_direct_reference_payload(
        None,
        project_id="proj",
        scene_id="scene-b",
        batch=batch,
        generator_id="ltx-2.5",
    )
    assert payload.sockets[0].socket == "start_image"
    assert payload.sockets[0].canonicalTag == "@Addex"
    err = delivery_error(payload)
    assert err is not None
    assert err["error"] == "REFERENCE_DELIVERY_FAILED"
    assert any("@Korri40YearsOld" in item["canonicalTag"] for item in err["blocked"])


def test_voice_reference_is_not_a_visual_socket(monkeypatch, tmp_path):
    _install_resolver(monkeypatch, tmp_path)
    batch = _batch(generator_id="minimax-h3", binding_ids=["bind-addex", "bind-voice"])
    payload = build_direct_reference_payload(
        None,
        project_id="proj",
        scene_id="scene-b",
        batch=batch,
        generator_id="minimax-h3",
    )
    assert [bind.socket for bind in payload.sockets] == ["ref_image_0", "ref_audio_0"]
    assert payload.sockets[0].canonicalTag == "@Addex"
    assert payload.sockets[1].kind == "audio"


def test_attach_does_not_rewrite_authored_prompt(monkeypatch, tmp_path):
    _install_resolver(monkeypatch, tmp_path)
    batch = _batch(generator_id="minimax-h3", binding_ids=["bind-addex", "bind-korri"])
    payload = build_direct_reference_payload(
        None,
        project_id="proj",
        scene_id="scene-b",
        batch=batch,
        generator_id="minimax-h3",
    )
    request = TimelineGenerationRequest(
        projectId="proj",
        sceneId="scene-b",
        batchBlockId=batch.id,
        executionSnapshotId="snap-1",
        generatorId="minimax-h3-t2v-local",
        prompt="Addex is sitting. Korri sits next to him.",
        duration=5.0,
        generationMode="reference",
        providerOptions={"authoredPrompt": "Addex is sitting. Korri sits next to him.", "visualStyle": "realistic_anime"},
    )
    attach_direct_reference_payload(request, payload)
    caps = get_registry().capabilities("minimax-h3-t2v-local")
    attach_canonical_r2v(request, batch, caps, db=None)
    assert request.prompt == "Addex is sitting. Korri sits next to him."
    r2v = request.providerOptions["r2v"]
    assert [slot["assetId"] for slot in r2v["slots"] if slot.get("pictureIndex")] == [
        "asset-addex",
        "asset-korri",
    ]
    assert request.providerOptions["directReferences"]["authority"] == "direct_reference_route"


def test_scene_c_has_no_prior_cast(monkeypatch, tmp_path):
    _install_resolver(monkeypatch, tmp_path)
    batch = _batch(generator_id="minimax-h3", binding_ids=[])
    batch.references = [
        {"kind": "characterIdentity", "identityNames": ["Korri"], "source": "project_character"},
        {"kind": "characterVoice", "identityName": "Addex", "source": "project_character_voice"},
    ]
    payload = build_direct_reference_payload(
        None,
        project_id="proj",
        scene_id="scene-c",
        batch=batch,
        generator_id="minimax-h3",
    )
    assert payload.all_items() == []
    assert payload.sockets == []
