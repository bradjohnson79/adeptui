"""WAVE 4 — dialogue_authority relocate + VerifiedContinuityMemory proof."""

from __future__ import annotations

import tempfile
from pathlib import Path

import app.codirector.dialogue_authority as cd_da
import app.director_timeline_w46.generation.dialogue_authority as w46_da
from app.codirector.dialogue_authority import (
    build_dialogue_manifest,
    submit_dialogue_authority_preflight,
)
from app.codirector.production.contracts import SceneProductionSpec
from app.codirector.verified_continuity_memory import (
    build_verified_record,
    continuity_refine_lines,
    read_verified_continuity,
    write_verified_continuity,
)


def test_dialogue_authority_canonical_is_codirector():
    assert cd_da.submit_dialogue_authority_preflight is w46_da.submit_dialogue_authority_preflight
    assert cd_da.build_dialogue_manifest is w46_da.build_dialogue_manifest
    assert Path(cd_da.__file__).as_posix().endswith("app/codirector/dialogue_authority.py")


def test_fail_closed_missing_manifest_when_locked_script():
    class Batch:
        speechWindows = [
            {
                "speechKind": "prompt_dialogue",
                "speakers": [{"speakerName": "Cade", "text": "Where is the Adept?"}],
            }
        ]

    blocked = submit_dialogue_authority_preflight(None, batch=Batch())
    assert blocked is not None
    assert blocked["error"] == "DIALOGUE_MANIFEST_MISSING"


def test_fail_closed_stale_manifest():
    manif = build_dialogue_manifest(
        project_id="p1",
        scene_id="s1",
        speech_windows=[
            {
                "speechKind": "prompt_dialogue",
                "speakers": [{"speakerName": "Cade", "text": "Hello."}],
            }
        ],
    )
    assert manif.get("lockedScript") and manif.get("lines")
    assert not manif.get("authorityExplicit")
    blocked = submit_dialogue_authority_preflight(manif)
    assert blocked is not None
    # Either SPOKEN_LANGUAGE_AUTHORITY_MISSING (existing) or DIALOGUE_MANIFEST_STALE
    assert blocked["error"] in {
        "SPOKEN_LANGUAGE_AUTHORITY_MISSING",
        "DIALOGUE_MANIFEST_STALE",
    }


def test_verified_continuity_parse_ok_false_never_canon(tmp_path, monkeypatch):
    monkeypatch.setenv("ADEPT_VERIFIED_CONTINUITY_DIR", str(tmp_path))
    rec = write_verified_continuity(
        project_id="proj",
        scene_id="scene",
        take_id="take1",
        revision="revA",
        batch_index=0,
        facts=[{"class": "OBSERVED", "text": "Should not canon"}],
        parse_ok=False,
    )
    assert rec["verifiedFacts"] == []
    assert read_verified_continuity(
        project_id="proj",
        scene_id="scene",
        take_id="take1",
        revision="revA",
        batch_index=0,
    ) is None


def test_verified_continuity_same_take_revision_only(tmp_path, monkeypatch):
    monkeypatch.setenv("ADEPT_VERIFIED_CONTINUITY_DIR", str(tmp_path))
    write_verified_continuity(
        project_id="proj",
        scene_id="scene",
        take_id="take1",
        revision="revA",
        batch_index=0,
        facts=[{"class": "OBSERVED", "text": "Corridor remains lit warm."}],
        parse_ok=True,
    )
    # Wrong take → None
    assert (
        read_verified_continuity(
            project_id="proj",
            scene_id="scene",
            take_id="take2",
            revision="revA",
            batch_index=0,
        )
        is None
    )
    # Wrong revision → None
    assert (
        read_verified_continuity(
            project_id="proj",
            scene_id="scene",
            take_id="take1",
            revision="revB",
            batch_index=0,
        )
        is None
    )
    ok = read_verified_continuity(
        project_id="proj",
        scene_id="scene",
        take_id="take1",
        revision="revA",
        batch_index=0,
    )
    assert ok is not None
    lines = continuity_refine_lines(ok)
    assert any("Corridor remains lit warm" in ln for ln in lines)


def test_uncertain_never_canon():
    rec = build_verified_record(
        project_id="p",
        scene_id="s",
        take_id="t",
        revision="r",
        batch_index=0,
        facts=[
            {"class": "UNCERTAIN", "text": "maybe speech"},
            {"class": "REJECTED", "text": "bad"},
            {"class": "OBSERVED", "text": "ok fact"},
        ],
        parse_ok=True,
    )
    texts = [f["text"] for f in rec["verifiedFacts"]]
    assert texts == ["ok fact"]


def test_scene_production_spec_continuity_keys():
    spec = SceneProductionSpec(
        project_id="p",
        take_id="take1",
        scene_revision="3",
        dialogue_manifest={"lockedScript": True, "lines": []},
    )
    assert spec.take_id == "take1"
    assert spec.scene_revision == "3"
