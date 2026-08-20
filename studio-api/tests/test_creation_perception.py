"""Revision B creation-perception contracts and Accept-into-slot."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

from app.codirector.perception.contracts import (
    PROVIDER_LEAK_KEYS,
    PerceptionPacket,
    ProposedSlotFill,
    SpatialDraft,
    UserCorrection,
    strip_provider_payload,
)
from app.codirector.perception.importance import filter_entities, is_wall_lint
from app.codirector.perception.contracts import PerceptionEntity
from app.codirector.perception.inpaint_leak import LEAK_THRESHOLD, unmasked_mean_delta
from app.image_runtime.output_gate import composite_generated_into_source
from app.codirector.perception.spatial_draft import apply_user_corrections
from app.codirector.perception.spatial_language import (
    detect_relation_tokens,
    detect_zone_phrases,
    extract_spatial_lines,
    match_known_names,
)
from app.codirector.entity_resolver import parse_shot_requests
from app.setup.catalog import get_component
from app.source_manager.downloads.executors import get_executor


def test_perception_packet_rejects_provider_logits():
    with pytest.raises(ValueError):
        PerceptionPacket(pose={"logits": [1, 2, 3]})


def test_strip_provider_payload_drops_detector_keys():
    clean = strip_provider_payload({"label": "cup", "logits": [0.1], "nms": True, "confidence": 0.9})
    assert "label" in clean
    assert "confidence" in clean
    assert not PROVIDER_LEAK_KEYS.intersection(clean)


def test_importance_drops_wall_lint():
    kept, unused = filter_entities(
        [
            PerceptionEntity(label="tiny wall poster", kindHint="prop"),
            PerceptionEntity(label="espresso machine", kindHint="prop"),
            PerceptionEntity(label="Korri", kindHint="character"),
        ]
    )
    assert is_wall_lint("tiny wall poster")
    assert [item.label for item in kept] == ["espresso machine", "Korri"]
    assert unused[0].reason == "not_important_to_blocking"


def test_user_correction_is_not_reversed():
    draft = SpatialDraft(
        proposedFills=[
            ProposedSlotFill(id="fill_a", kind="character", label="Korri", slotIndex=0),
        ]
    )
    draft = apply_user_corrections(
        draft,
        [UserCorrection(factKey="fill:fill_a", action="rename", value={"label": "Anadriya"})],
    )
    assert draft.proposedFills[0].label == "Anadriya"
    assert draft.proposedFills[0].authority == "filmmaker"
    again = apply_user_corrections(draft, [])
    assert again.proposedFills[0].label == "Anadriya"


def test_spatial_language_schnick_sentence():
    text = (
        "Put Korri behind the service counter beside the espresso machine "
        "while Anadriya stands on the customer side facing her."
    )
    assert "BEHIND" in detect_relation_tokens(text)
    assert "BESIDE" in detect_relation_tokens(text)
    assert "FACING" in detect_relation_tokens(text)
    assert "customer side" in detect_zone_phrases(text)
    shots = parse_shot_requests(text)
    assert shots
    assert "behind" in shots[0].additional_instructions.lower()
    assert match_known_names(text, ["Korri", "Anadriya"]) == ["Korri", "Anadriya"]
    lines = extract_spatial_lines(text)
    assert any("Zone:" in line for line in lines)


def test_stills_worker_python_is_not_studio_api():
    import sys

    from app.codirector.perception.paths import venv_root, worker_python

    assert "stills-perception-worker" in str(worker_python())
    assert "stills-perception-worker" in str(venv_root())
    if not (os.environ.get("ADEPT_STILLS_PERCEPTION_PYTHON") or "").strip():
        assert Path(worker_python()).resolve() != Path(sys.executable).resolve()


def test_geometry_revisions_are_pinned():
    from app.codirector.perception.paths import (
        DEPTH_ANYTHING_REVISION,
        GROUNDING_DINO_REVISION,
        SAM21_REVISION,
    )

    for rev in (GROUNDING_DINO_REVISION, SAM21_REVISION, DEPTH_ANYTHING_REVISION):
        assert rev != "main"
        assert len(rev) == 40


def test_stills_installer_is_not_hunyuan():
    grounding = get_component("grounding_dino_tiny")
    assert grounding.required is False
    assert grounding.installer == "stills_perception_hf"
    assert get_component("sam21_hiera_tiny").required is False
    assert get_component("depth_anything_v2_small").required is False
    from app.source_manager.downloads.executors.huggingface_snapshot import HuggingFaceSnapshotExecutor
    from app.source_manager.downloads.executors.stills_perception import StillsPerceptionExecutor

    assert isinstance(get_executor("stills_perception_hf"), StillsPerceptionExecutor)
    assert isinstance(get_executor("huggingface_snapshot"), HuggingFaceSnapshotExecutor)
    assert get_executor("stills_perception_hf").provider_id != "huggingface_snapshot"


def test_gpu_lease_module_is_untouched():
    lease = Path(__file__).resolve().parents[1] / "app" / "codirector" / "video_intelligence" / "gpu_lease.py"
    text = lease.read_text(encoding="utf-8")
    assert "preflight_for_stills" not in text
    assert "stills" not in text.lower()


def test_spatial_map_document_has_no_zones_field():
    from app.spatial_map.schemas import SpatialMapDocument

    assert "zones" not in SpatialMapDocument.model_fields


def test_inpaint_leak_detector_flags_restyled_background(tmp_path: Path):
    source = tmp_path / "source.png"
    output = tmp_path / "output.png"
    mask = tmp_path / "mask.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(source)
    Image.new("RGB", (32, 32), (200, 10, 10)).save(output)
    Image.new("L", (32, 32), 0).save(mask)
    delta = unmasked_mean_delta(output, source, mask)
    assert delta > LEAK_THRESHOLD


def test_inpaint_leak_detector_passes_preserved_background(tmp_path: Path):
    source = tmp_path / "source.png"
    output = tmp_path / "output.png"
    mask = tmp_path / "mask.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(source)
    Image.new("RGB", (32, 32), (10, 20, 30)).save(output)
    Image.new("L", (32, 32), 0).save(mask)
    assert unmasked_mean_delta(output, source, mask) < LEAK_THRESHOLD


def test_user_correction_survives_new_fill_ids():
    draft = SpatialDraft(
        proposedFills=[
            ProposedSlotFill(id="fill_new", kind="character", label="Korri", slotIndex=0),
        ]
    )
    draft = apply_user_corrections(
        draft,
        [UserCorrection(factKey="fill:korri", action="reject", value={})],
    )
    assert draft.proposedFills == []


def test_accept_writes_only_existing_placement_apis():
    from inspect import getsource

    from app.codirector.perception.spatial_draft import accept_into_slots

    src = getsource(accept_into_slots)
    assert "place_character" in src
    assert "place_prop" in src
    assert "create_camera" in src
    assert "document.characters.append" not in src
    assert "zones" not in src


def test_accept_caps_and_refuses_occupied(monkeypatch):
    from app.codirector.perception.contracts import AcceptItem, AcceptRequest
    from app.codirector.perception.importance import cap_slot_counts
    from app.codirector.perception.spatial_draft import accept_into_slots

    chars = [ProposedSlotFill(kind="character", slotIndex=i, label=f"C{i}") for i in range(6)]
    props = [ProposedSlotFill(kind="prop", slotIndex=i, label=f"P{i}") for i in range(6)]
    cams = [ProposedSlotFill(kind="camera", slotIndex=i, label=f"Cam{i}") for i in range(6)]
    c, p, k, overflow = cap_slot_counts(chars, props, cams)
    assert len(c) == 4 and len(p) == 4 and len(k) == 4
    assert len(overflow) == 6

    class _Doc:
        characters = [type("C", (), {"slotIndex": 0})()]
        props = []
        cameras = []

    draft = SpatialDraft(
        projectId="p1",
        mapId="m1",
        proposedFills=[
            ProposedSlotFill(id="fill_occ", kind="character", label="Korri", slotIndex=0, characterId="char-1"),
        ],
    )
    monkeypatch.setattr("app.codirector.perception.spatial_draft.load_spatial_draft", lambda *_a, **_k: draft)
    monkeypatch.setattr("app.codirector.perception.spatial_draft.save_spatial_draft", lambda *_a, **_k: draft)
    monkeypatch.setattr("app.spatial_map.service.get_document", lambda *_a, **_k: _Doc())
    result = accept_into_slots(object(), "p1", "m1", AcceptRequest(items=[AcceptItem(fillId="fill_occ")]))
    assert result.ok is False
    assert result.documentWritten is False
    assert result.failures[0].code == "SLOT_OCCUPIED"


def test_accept_resolves_stale_fill_id_by_label(monkeypatch):
    from app.codirector.perception.contracts import AcceptItem, AcceptRequest
    from app.codirector.perception.spatial_draft import accept_into_slots

    class _Doc:
        characters = []
        props = []
        cameras = []

    draft = SpatialDraft(
        projectId="p1",
        mapId="m1",
        proposedFills=[
            ProposedSlotFill(id="fill_new", kind="camera", label="Conversation camera", slotIndex=0),
        ],
    )
    placed = []

    def _create_camera(*_a, **_k):
        placed.append("camera")
        return _Doc()

    monkeypatch.setattr("app.codirector.perception.spatial_draft.load_spatial_draft", lambda *_a, **_k: draft)
    monkeypatch.setattr("app.codirector.perception.spatial_draft.save_spatial_draft", lambda *_a, **_k: draft)
    monkeypatch.setattr("app.spatial_map.service.get_document", lambda *_a, **_k: _Doc())
    monkeypatch.setattr("app.spatial_map.service.create_camera", _create_camera)
    result = accept_into_slots(
        object(),
        "p1",
        "m1",
        AcceptRequest(items=[AcceptItem(fillId="fill_stale", label="Conversation camera")]),
    )
    assert result.documentWritten is True
    assert placed == ["camera"]
    assert result.acceptedFillIds == ["fill_new"]


def test_pixel_boxes_are_normalized():
    from app.codirector.perception.boxes import normalize_box

    box = normalize_box({"xmin": 100, "ymin": 50, "xmax": 300, "ymax": 250}, width=400, height=400)
    assert 0.0 <= box["x0"] < box["x1"] <= 1.0
    assert abs(box["x0"] - 0.25) < 1e-6
    assert abs(box["y1"] - 0.625) < 1e-6


def test_orchestrator_routes_stills_before_hunyuan():
    from inspect import getsource

    from app.setup.orchestrator import execute_recommended_action

    src = getsource(execute_recommended_action)
    assert src.index("stills_perception_hf") < src.index("huggingface_snapshot")
    assert src.index("_enqueue_stills_perception_install") < src.index("_enqueue_hunyuan_install")


def test_license_memos_exist_for_geometry_pins():
    root = Path(__file__).resolve().parents[2]
    for rel in (
        "docs/models/grounding-dino-tiny/LICENSE_CLEARANCE.md",
        "docs/models/sam21-hiera-tiny/LICENSE_CLEARANCE.md",
        "docs/models/depth-anything-v2-small/LICENSE_CLEARANCE.md",
    ):
        text = (root / rel).read_text(encoding="utf-8")
        assert "Apache" in text
        assert "required=False" in text or "`required=False`" in text


def test_auto_mask_never_returns_a_box_as_mask():
    from app.codirector.perception import auto_mask as am
    from app.codirector.perception.contracts import PerceptionCapability

    draft = SpatialDraft(
        proposedFills=[
            ProposedSlotFill(id="fill_cup", kind="prop", label="cup", perceptionEntityId="ent_1"),
        ]
    )
    original_cap = am.get_capability
    original_load = am.load_spatial_draft
    am.get_capability = lambda: PerceptionCapability(autoMask="testing")  # type: ignore[arg-type]
    am.load_spatial_draft = lambda *_a, **_k: draft
    try:
        payload = am.resolve_auto_mask(object(), "p1", "m1", "cup")
    finally:
        am.get_capability = original_cap
        am.load_spatial_draft = original_load
    assert payload["ok"] is False
    assert payload["maskAssetId"] == ""
    assert "paint" in payload["message"].lower()


def test_camera_shot_packet_absorbs_accepted_draft_notes():
    from app.spatial_map.camera_shot_packet import _append_spatial_draft_notes
    from app.codirector.perception.contracts import ProposedRelationship, ProposedZonePhrase

    draft = SpatialDraft(
        relationships=[
            ProposedRelationship(
                subjectLabel="Korri",
                relation="BEHIND",
                objectLabel="service counter",
                factStatus="corrected",
            )
        ],
        zonePhrases=[ProposedZonePhrase(phrase="customer side", factStatus="inferred")],
    )

    class _Db:
        pass

    locked: list[str] = []
    flexible: list[str] = []

    def _load(*_a, **_k):
        return draft

    import app.codirector.perception.spatial_draft as sd

    original = sd.load_spatial_draft
    sd.load_spatial_draft = _load
    try:
        _append_spatial_draft_notes(_Db(), "p1", "m1", locked, flexible)
    finally:
        sd.load_spatial_draft = original
    assert any("Korri behind service counter" in item for item in locked)
    assert any("customer side" in item for item in flexible)


def test_region_composite_brings_inpaint_leak_under_threshold(tmp_path: Path):
    src = Image.new("RGB", (64, 64), (10, 20, 30))
    leaked = Image.new("RGB", (64, 64), (200, 10, 10))
    mask = Image.new("L", (64, 64), 0)
    for x in range(20, 44):
        for y in range(20, 44):
            mask.putpixel((x, y), 255)
    src_p = tmp_path / "src.png"
    gen_p = tmp_path / "gen.png"
    mask_p = tmp_path / "mask.png"
    out_p = tmp_path / "out.png"
    src.save(src_p)
    leaked.save(gen_p)
    mask.save(mask_p)
    assert unmasked_mean_delta(gen_p, src_p, mask_p) > LEAK_THRESHOLD
    composite_generated_into_source(gen_p, src_p, mask_p, out_p, feather_px=0)
    assert unmasked_mean_delta(out_p, src_p, mask_p) <= LEAK_THRESHOLD


def test_queue_worker_composites_inpaint_outputs():
    text = Path(__file__).resolve().parents[1].joinpath("app", "queue_worker.py").read_text(encoding="utf-8")
    assert "composite_generated_into_source" in text
    assert 'and "inpaint" not in contract.workflow_key' not in text
