"""H3 R2V eradication pins - Film Timeline Director-only authority."""

from __future__ import annotations

import ast
from pathlib import Path

from app.film_timeline import director_refs
from app.film_timeline.orchestrator import _is_local_h3
from app.video_runtime.legal_canvas import check_duration


ROOT = Path(__file__).resolve().parents[1]
ORCH = ROOT / "app" / "film_timeline" / "orchestrator.py"
QW = ROOT / "app" / "queue_worker.py"
REFS = ROOT / "app" / "film_timeline" / "director_refs.py"


def _assert_no_w46_r2v_imports(path: Path) -> None:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if "generation.r2v" in mod or "director_timeline_w46" in mod and mod.endswith(".r2v"):
                names = {a.name for a in node.names}
                banned = {
                    "CanonicalR2VRequest",
                    "R2VSlot",
                    "mechanism_for_generator",
                    "_assign_picture_indices",
                }
                hit = names & banned
                assert not hit, f"{path.name} still imports {hit} from {mod}"
            if mod.endswith("generation.r2v"):
                raise AssertionError(f"{path.name} must not import {mod}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert "generation.r2v" not in alias.name


def test_orchestrator_has_no_canonical_r2v_import():
    _assert_no_w46_r2v_imports(ORCH)
    src = ORCH.read_text(encoding="utf-8")
    assert "build_director_refs" in src
    assert "directorRefs" in src


def test_director_refs_module_has_no_w46_r2v_import():
    _assert_no_w46_r2v_imports(REFS)


def test_assign_picture_indices_orders_character_place_prop():
    slots = [
        director_refs.make_ref_slot(role="prop", asset_id="p1", label="Venture"),
        director_refs.make_ref_slot(role="character", asset_id="c1", label="Korri"),
        director_refs.make_ref_slot(role="place", asset_id="e1", label="Cafe"),
        director_refs.make_ref_slot(role="audio", asset_id="a1", label="Korri"),
        director_refs.make_ref_slot(role="video", asset_id="v1", label="Prev"),
    ]
    ranked = director_refs.assign_picture_indices(slots)
    visuals = [s for s in ranked if s["role"] not in {"video", "audio"}]
    assert [s["label"] for s in visuals] == ["Korri", "Cafe", "Venture"]
    assert [s["pictureIndex"] for s in visuals] == [1, 2, 3]
    audio = next(s for s in ranked if s["role"] == "audio")
    video = next(s for s in ranked if s["role"] == "video")
    assert audio["audioIndex"] == 1
    assert video["videoIndex"] == 1
    assert audio["pictureIndex"] is None
    assert video["pictureIndex"] is None


def test_slots_from_params_prefers_director_refs():
    params = {
        "directorRefs": {
            "slots": [{"role": "character", "assetId": "c1", "pictureIndex": 1}],
        },
        "r2v": {
            "slots": [{"role": "character", "assetId": "OLD", "pictureIndex": 1}],
        },
    }
    slots = director_refs.slots_from_params(params)
    assert slots[0]["assetId"] == "c1"
    assert director_refs.slots_from_params({"r2v": params["r2v"]})[0]["assetId"] == "OLD"


def test_director_method_uses_director_era_error_codes():
    src = QW.read_text(encoding="utf-8")
    idx = src.index("async def _build_and_run_h3_director")
    nxt = src.find("\n    async def ", idx + 10)
    body = src[idx : nxt if nxt > 0 else idx + 12000]
    assert "H3_DIRECTOR_MODE_REQUIRED" in body
    assert "H3_DIRECTOR_REFS_REQUIRED" in body
    assert "TIMELINE_R2V_REQUIRED" not in body
    assert "slots_from_params" in body
    assert "frames_for_duration" not in body


def test_h3_timeline_surface_r2v_demoted_before_preflight():
    src = QW.read_text(encoding="utf-8")
    assert "_timeline_job_is_h3(_early_params, resolved_engine)" in src
    assert '_surface = "i2v"' in src


def test_check_duration_14s_fails_on_r2v_passes_on_i2v():
    """Phase 13 pin: 14s illegal under legacy R2V surface, legal under Director i2v surface."""
    r2v = check_duration("minimax-h3-i2v-local", 14.0, 24, surface="r2v")
    i2v = check_duration("minimax-h3-i2v-local", 14.0, 24, surface="i2v")
    assert r2v["ok"] is False
    msg = r2v["message"]
    assert (
        "Reference-to-Video" in msg
        or "mod 17" in msg
        or "will not pad" in msg.lower()
    )
    assert r2v["frames"] == 336
    assert i2v["ok"] is True


def test_cutover_fail_closed_markers_preserved():
    src = QW.read_text(encoding="utf-8")
    assert "Director cutover (fail-closed)" in src
    assert "H3_DIRECTOR_REQUIRED" in src
    assert "H3_LEGACY_REF2V_RETIRED" in src
    assert _is_local_h3("minimax-h3-i2v-local")
