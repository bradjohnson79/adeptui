"""M42 W45 Audio Studio — contracts, select≠approve, mix persistence, gate surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_contracts_importable():
    from app.audio_studio.contracts import (
        AudioCreativeBrief,
        AudioMixClipState,
        AudioMasterOutput,
        MusicStemSet,
        MusicIntent,
        AmbienceIntent,
        SoundEffectIntent,
    )

    brief = AudioCreativeBrief(project_id="p1", prompt="hopeful score")
    assert brief.prompt == "hopeful score"
    clip = AudioMixClipState(clip_id="c1", gain=0.8, pan=-0.25, mute=False, solo=True)
    assert clip.gain == 0.8
    master = AudioMasterOutput(gain=1.0)
    assert master.gain == 1.0
    stems = MusicStemSet(parent_version_id="v1", stems=[])
    assert stems.stems == []
    assert MusicIntent(brief=brief).kind == "music"
    ambience_brief = AudioCreativeBrief(project_id="p1", prompt="rain", loop_required=True)
    assert AmbienceIntent(brief=ambience_brief).kind == "ambience"
    assert SoundEffectIntent(brief=AudioCreativeBrief(project_id="p1", prompt="footstep")).kind == "sfx"


def test_provider_resolver_local_ready_and_no_silent_switch():
    from app.audio_studio.provider_resolver import local_runtime_status, resolve_execution, hosted_audio_status

    local = local_runtime_status()
    assert "ACE-Step" in local and "MMAudio" in local
    # Hosted always declares stem honesty
    hosted = hosted_audio_status()
    assert len(hosted) == 3
    assert all(h.get("stems_supported") is False for h in hosted)

    res = resolve_execution("music")
    assert res["mock"] is False
    assert res["recommendation"]["requiresApprovalToSwitch"] is True
    assert res["recommendation"]["requiresApprovalForCpuFallback"] is True
    # Without allow_switch, hosted preferred does not silently activate
    res2 = resolve_execution("music", preferred_provider="kie.ai", allow_switch=False)
    if res2["recommendation"]["mode"] == "hosted":
        pytest.fail("silent hosted switch without allow_switch")


def test_provider_resolver_blocks_cpu_without_explicit_fallback(monkeypatch):
    from app.audio_studio import provider_resolver as pr

    monkeypatch.setattr(
        pr,
        "local_runtime_status",
        lambda: {
            "ACE-Step": {
                "runtime": "ACE-Step",
                "ready": True,
                "cuda": False,
                "accelerator": "cpu",
                "message": "CPU only",
                "stems_supported": False,
            },
            "MMAudio": {
                "runtime": "MMAudio",
                "ready": True,
                "cuda": False,
                "accelerator": "cpu",
                "message": "CPU only",
                "stems_supported": False,
            },
        },
    )
    blocked = pr.resolve_execution("music", allow_cpu_fallback=False)
    assert blocked["recommendation"]["mode"] == "blocked_cpu"
    allowed = pr.resolve_execution("music", allow_cpu_fallback=True)
    assert allowed["recommendation"]["mode"] == "local"
    assert allowed["recommendation"]["cpuFallbackUsed"] is True


def test_select_not_approve(tmp_path, monkeypatch):
    from app.audio_studio import store, service

    monkeypatch.setattr("app.audio_studio.store.settings.data_dir", str(tmp_path))
    pid = "proj-w45"
    batch = {
        "id": "b1",
        "project_id": pid,
        "method": "music",
        "candidates": [
            {"id": "c1", "asset_id": "a1", "status": "ready"},
            {"id": "c2", "asset_id": "a2", "status": "ready"},
        ],
    }
    store.save_batch(pid, batch)
    selected = service.select_candidate(pid, "b1", "c1")
    assert selected["selected"] is True
    assert selected["approved"] is False
    batch2 = store.get_batch(pid, "b1")
    assert batch2["candidates"][0]["status"] == "selected"
    approved = service.approve_candidate(pid, "b1", "c1")
    assert approved["approved"] is True
    batch3 = store.get_batch(pid, "b1")
    assert batch3["candidates"][0]["status"] == "approved"


def test_mix_persistence_reload(tmp_path, monkeypatch):
    from app.audio_studio import store, service

    monkeypatch.setattr("app.audio_studio.store.settings.data_dir", str(tmp_path))
    pid = "proj-mix"
    mix = service.update_mix(
        pid,
        {
            "master": {"gain": 0.7, "peak": -3.0, "lufs_integrated": -16.0},
            "clip": {
                "clip_id": "clip-1",
                "asset_id": "a1",
                "gain": 0.5,
                "pan": 0.2,
                "mute": False,
                "solo": True,
                "fade_in_ms": 100,
                "fade_out_ms": 200,
            },
        },
    )
    assert mix["master"]["gain"] == 0.7
    reloaded = store.get_mix(pid)
    assert reloaded["clips"]["clip-1"]["solo"] is True
    assert reloaded["clips"]["clip-1"]["gain"] == 0.5
    assert reloaded["master"]["lufs_integrated"] == -16.0


def test_no_fake_stems_on_expand(tmp_path, monkeypatch):
    from app.audio_studio import store, service

    monkeypatch.setattr("app.audio_studio.store.settings.data_dir", str(tmp_path))
    pid = "proj-stems"
    service.update_mix(pid, {"clip": {"clip_id": "c1", "asset_id": "a1", "gain": 1.0}})
    service.update_mix(pid, {"stem": {"clip_id": "c1", "stem_id": "missing", "expand": True}})
    mix = store.get_mix(pid)
    assert mix["clips"]["c1"].get("stemsExpanded") is False
    assert "did not return stems" in (mix["clips"]["c1"].get("stemsMessage") or "")


def test_taxonomy_audio_roles():
    from app.project_library.taxonomy import TAXONOMY_ROOT

    keys = set()

    def walk(node):
        keys.add(node.system_key)
        for child in getattr(node, "children", ()) or ():
            walk(child)

    walk(TAXONOMY_ROOT)
    for required in (
        "audio.music",
        "audio.music_stem",
        "audio.ambience",
        "audio.foley",
        "audio.reaction",
        "audio.room_tone",
    ):
        assert required in keys, required


def test_gate_endpoint_shape():
    from app.audio_studio.production_gate import evaluate_m42_audio_studio_gate

    gate = evaluate_m42_audio_studio_gate()
    assert gate["ok"] is True
    assert gate["mock"] is False
    assert "audioStudioGo" in gate
    assert "flags" in gate
    assert gate["flags"]["providerSwitchNeverSilent"] is True
    assert gate["flags"]["audioStudioNoMockData"] is True
    # Binary — no Conditional GO key
    assert "conditionalGo" not in gate
    assert gate["verdict"] in ("GO", "NO-GO")


def test_codirector_audio_tools_registered():
    from app.codirector.tools import registry as reg
    from app.codirector.tools import definitions as defs

    tool_ids = {t.tool_id for t in defs.TOOL_DEFINITIONS}
    required = {
        "audio.status",
        "audio.library",
        "audio.generate_music",
        "audio.generate_sfx",
        "audio.generate_ambience",
        "audio.select_candidate",
        "audio.approve_candidate",
        "audio.place",
        "audio.open_studio",
        "audio.cancel_batch",
        "audio.get_batch",
        "audio.compare_candidates",
    }
    missing = required - tool_ids
    assert not missing, missing
    for tid in ("audio.generate_music", "audio.approve_candidate", "audio.place", "audio.cancel_batch"):
        assert tid in reg._MUTATION_HANDLERS
    assert "audio.status" in reg._READ_HANDLERS
    assert "audio.get_batch" in reg._READ_HANDLERS
    cancel_def = next(t for t in defs.TOOL_DEFINITIONS if t.tool_id == "audio.cancel_batch")
    assert cancel_def.requires_approval is False


def _gpu_ready_resolution(kind="music"):
    runtime = "ACE-Step" if kind == "music" else "MMAudio"
    return {
        "recommendation": {
            "mode": "local",
            "runtime": runtime,
            "provider": None,
            "reason": f"Local {runtime} is ready on GPU.",
            "requiresApprovalToSwitch": True,
            "cuda": True,
            "gpuRequired": True,
            "cpuFallbackUsed": False,
        },
        "local": {},
        "hosted": [],
        "mock": False,
    }


def test_async_batch_progress_updates(tmp_path, monkeypatch):
    from app.audio_studio import store, service

    monkeypatch.setattr("app.audio_studio.store.settings.data_dir", str(tmp_path))
    monkeypatch.setattr(
        "app.audio_studio.service.resolve_execution",
        lambda *a, **k: _gpu_ready_resolution("music"),
    )

    def fake_generate(db, *, project_id, kind, prompt, duration_sec=4.0, seed=None):
        return {"assetId": f"asset-{seed or prompt[-1]}", "m29": {"fixture": False, "sha256": f"h-{seed}"}}

    monkeypatch.setattr("app.generation_tools.ops.run_audio_generate", fake_generate)
    batch = service.begin_generate_batch(
        "proj-progress",
        kind="music",
        brief={"prompt": "hopeful score"},
        candidate_count=3,
    )
    assert batch["progress"]["percent"] == 0
    assert batch["progress"]["total"] == 3
    assert all(c["status"] == "queued" for c in batch["candidates"])
    seeds = {c.get("seed") for c in batch["candidates"]}
    assert len(seeds) == 3

    class _DummyDb:
        pass

    done = service.execute_generate_batch(_DummyDb(), "proj-progress", batch["id"])
    assert done["status"] == "complete"
    assert done["progress"]["percent"] == 100
    assert done["progress"]["completed"] == 3
    assert done["uniqueness"]["ok"] is True
    asset_ids = [c["asset_id"] for c in done["candidates"]]
    assert len(set(asset_ids)) == 3
    reloaded = store.get_batch("proj-progress", batch["id"])
    assert reloaded["progress"]["percent"] == 100


def test_cancel_batch_marks_source_cancel(tmp_path, monkeypatch):
    from app.audio_studio import store, service

    monkeypatch.setattr("app.audio_studio.store.settings.data_dir", str(tmp_path))
    monkeypatch.setattr(
        "app.audio_studio.service.resolve_execution",
        lambda *a, **k: _gpu_ready_resolution("music"),
    )
    monkeypatch.setattr(
        "app.audio_studio.process_registry.terminate_orphan_audio_workers",
        lambda: {"ok": True, "killed": [], "count": 0, "sourceCancel": True},
    )
    batch = service.begin_generate_batch(
        "proj-cancel",
        kind="music",
        brief={"prompt": "cancel me"},
        candidate_count=2,
    )
    out = service.cancel_batch("proj-cancel", batch["id"])
    assert out["cancelled"] is True
    assert out["sourceCancel"] is True
    reloaded = store.get_batch("proj-cancel", batch["id"])
    assert reloaded["status"] == "cancelled"
    assert all(c["status"] == "cancelled" for c in reloaded["candidates"])


def test_codirector_generate_starts_async(tmp_path, monkeypatch):
    from app.audio_studio import store
    from app.codirector.tools.definitions import ToolContext
    from app.codirector.tools.handlers import audio_studio_tools as tools

    monkeypatch.setattr("app.audio_studio.store.settings.data_dir", str(tmp_path))
    monkeypatch.setattr(
        "app.audio_studio.service.resolve_execution",
        lambda *a, **k: _gpu_ready_resolution("music"),
    )
    started = {}

    def fake_job(project_id, batch_id):
        started["project_id"] = project_id
        started["batch_id"] = batch_id

    monkeypatch.setattr("app.audio_studio.service.run_generate_batch_job", fake_job)

    class _Db:
        pass

    ctx = ToolContext(db=_Db(), project_id="proj-cd-async", scene_id=None)
    out = tools.apply_generate_music(ctx, {"prompt": "hopeful cinematic rise", "candidateCount": 3})
    assert out["async"] is True
    assert out["batchId"]
    assert out["uiAction"] == "open_audio_studio"
    assert out["cancelTool"] == "audio.cancel_batch"
    assert started["batch_id"] == out["batchId"]
    batch = store.get_batch("proj-cd-async", out["batchId"])
    assert batch is not None
    assert len({c.get("seed") for c in batch["candidates"]}) == 3


def test_shared_contracts_doc_exists():
    root = Path(__file__).resolve().parents[2]
    assert (root / "docs" / "release-gate" / "m42" / "M42_W45_SHARED_CONTRACTS.md").is_file()
    assert (root / "studio-web" / "src" / "components" / "audio-studio" / "AudioStudioWorkspace.tsx").is_file()
    assert (root / "studio-web" / "src" / "components" / "audio-studio" / "AudioMixerPanel.tsx").is_file()
