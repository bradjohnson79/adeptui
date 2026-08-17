"""CDX-076 / CDX-082 — no silent model substitution + truthful checkpoint names.

Verifies:
- queue_worker._checkpoint_for_model("qwen2512") returns the Qwen UNET name
  (not the FLUX checkpoint) so job status is truthful (CDX-082).
- queue_worker._imagegen FAILS with an actionable MODEL_NOT_INSTALLED-style
  error when an explicitly selected / pinned Z-Image model is not verified on
  disk — no alternate model executes, enginePreference is untouched, and no
  workflow is resolved (CDX-076).
- the legacy unpinned "auto" fallback (alternate engine selected by design) is
  disclosed as a first-class visible status: job.message names the actual
  executed model AND the reason, not only history_json (CDX-076).
- image_core preflight returns MODEL_NOT_INSTALLED when the selected local
  model's component verification fails, and image_core.generate refuses before
  enqueue (CDX-076).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import settings
from app.image_core.errors import MODEL_NOT_INSTALLED
from app.image_core.request import ImageCoreRequest


# --- CDX-082: truthful checkpoint names --------------------------------------


def test_checkpoint_for_model_qwen2512_returns_qwen_unet() -> None:
    from app.queue_worker import JobQueue

    worker = JobQueue.__new__(JobQueue)
    assert worker._checkpoint_for_model("qwen2512") == settings.qwen_image_2512_unet
    assert worker._checkpoint_for_model("QWEN2512") == settings.qwen_image_2512_unet
    assert worker._checkpoint_for_model("qwen-image-2512") == settings.qwen_image_2512_unet
    assert worker._checkpoint_for_model("qwen_image_2512") == settings.qwen_image_2512_unet
    assert worker._checkpoint_for_model("qwen") == settings.qwen_image_2512_unet
    # Existing families unchanged.
    assert worker._checkpoint_for_model("zimage") == settings.zimage_unet
    assert worker._checkpoint_for_model("auto") == settings.zimage_unet
    assert worker._checkpoint_for_model("illustrious") == settings.imagegen_illustrious_checkpoint
    assert worker._checkpoint_for_model("flux") == settings.imagegen_flux_checkpoint
    assert "qwen_image_2512" in settings.qwen_image_2512_unet


# --- CDX-076: no silent substitution at execution time -----------------------


class _FakeDB:
    def __init__(self, objects=None):
        self.objects = objects or {}
        self.messages: list[str] = []

    def commit(self) -> None:
        return None

    def add(self, _obj: object) -> None:
        return None

    def get(self, model, obj_id: str):
        if obj_id in self.objects:
            return self.objects[obj_id]
        return None


def _job(params: dict):
    return SimpleNamespace(
        id="job-cdx076",
        kind="imagegen",
        history_json="{}",
        params_json=json.dumps(params),
        progress=0.0,
        stage="",
        message="",
        comfy_prompt_id="",
        updated_at=None,
        status="running",
    )


def test_imagegen_zimage_selected_not_ready_fails_no_substitution(monkeypatch) -> None:
    """Explicit Z-Image selection + failed zimage_models verify -> job FAILS;
    no alternate model executes, no workflow resolved, no submit."""
    from app.queue_worker import JobQueue

    params = {
        "prompt": "a cinematic still",
        "model": "zimage",
        "width": 1024,
        "height": 1024,
        "seed": 1,
        "imageIntent": {
            "projectId": "proj-cdx076",
            "prompt": "a cinematic still",
            "enginePreference": "zimage",
            "providerPreference": "local",
            "operation": "image.generate",
            "purpose": "scene_shot_final",
            "width": 1024,
            "height": 1024,
            "metadata": {},
        },
        "imageRuntime": {
            "provider": "local",
            "engine": "comfy",
            "adapter": "comfy",
            "workflowKey": "zimage.txt2img",
        },
    }
    monkeypatch.setattr(JobQueue, "_zimage_stack_ready", lambda self: False)

    called = {"resolve": 0, "submit": 0}

    def boom_resolve(*_a, **_k):
        called["resolve"] += 1
        raise AssertionError("no workflow may resolve when the selected model is unavailable")

    async def boom_submit(*_a, **_k):
        called["submit"] += 1
        raise AssertionError("no alternate model may execute")

    monkeypatch.setattr("app.image_runtime.contract.resolve_image_workflow", boom_resolve)
    monkeypatch.setattr("app.image_runtime.local_comfy_adapter.submit", boom_submit)

    job = _job(params)
    project = SimpleNamespace(id="proj-cdx076", negative_prompt="", seed=0)
    worker = JobQueue()

    with pytest.raises(RuntimeError) as ei:
        asyncio.run(worker._imagegen(_FakeDB(), job, project))

    msg = str(ei.value).lower()
    assert "z-image" in msg or "zimage" in msg
    assert "not installed" in msg
    assert "zimage_models" in msg
    assert "no alternate model" in msg
    assert called["resolve"] == 0
    assert called["submit"] == 0


def test_imagegen_pinned_zimage_fails_when_not_ready(monkeypatch) -> None:
    """Pinned zimage workflow + zimage_models verify fail -> job FAILS
    (pinned path previously swapped inertly and advertised an alternate
    checkpoint while still building the zimage graph)."""
    from app.queue_worker import JobQueue

    params = {
        "prompt": "a pinned zimage job",
        "model": "zimage",
        "width": 1024,
        "height": 1024,
        "seed": 2,
        "imageIntent": {
            "projectId": "proj-cdx076",
            "prompt": "a pinned zimage job",
            "enginePreference": "zimage",
            "providerPreference": "local",
            "operation": "image.generate",
            "purpose": "scene_shot_final",
            "width": 1024,
            "height": 1024,
            "metadata": {},
        },
        "imageRuntime": {
            "provider": "local",
            "engine": "comfy",
            "adapter": "comfy",
            "workflowKey": "zimage.txt2img",
            "workflowVersion": "1.0.0",
            "modelFamily": "zimage",
        },
    }
    monkeypatch.setattr(JobQueue, "_zimage_stack_ready", lambda self: False)

    def boom_resolve(*_a, **_k):
        raise AssertionError("pinned zimage must fail before workflow resolution")

    monkeypatch.setattr("app.image_runtime.contract.resolve_image_workflow", boom_resolve)

    job = _job(params)
    project = SimpleNamespace(id="proj-cdx076", negative_prompt="", seed=0)
    worker = JobQueue()

    with pytest.raises(RuntimeError) as ei:
        asyncio.run(worker._imagegen(_FakeDB(), job, project))

    msg = str(ei.value).lower()
    assert "not installed" in msg
    assert "no alternate model was substituted" in msg


def test_imagegen_legacy_auto_fallback_visible_in_job_message(monkeypatch, isolated_data_dir: Path) -> None:
    """Legacy unpinned 'auto' path: an alternate engine selected by design is
    recorded as a first-class visible status — job.message names the actual
    executed model AND the reason (not only history_json)."""
    from app.queue_worker import JobQueue

    params = {
        "prompt": "a legacy auto job",
        "model": "auto",
        "width": 1024,
        "height": 1024,
        "seed": 3,
        "imageIntent": {
            "projectId": "proj-cdx076",
            "prompt": "a legacy auto job",
            "enginePreference": "auto",
            "providerPreference": "local",
            "operation": "image.generate",
            "purpose": "",
            "width": 1024,
            "height": 1024,
            "metadata": {},
        },
    }
    # Z-Image not ready; flux checkpoint "present" -> _resolve_ready_still_model
    # selects the alternate by design (legacy auto semantics).
    monkeypatch.setattr(JobQueue, "_zimage_stack_ready", lambda self: False)
    monkeypatch.setattr(JobQueue, "_checkpoint_file_present", lambda self, name: name == settings.imagegen_flux_checkpoint)

    contract = SimpleNamespace(
        workflow_key="flux.txt2img",
        workflow_version="1.0.0",
        certification_record_id=None,
        status="Draft",
        required_inputs=["prompt"],
        to_pinned_snapshot=lambda: {
            "workflowKey": "flux.txt2img",
            "provider": "local",
            "engine": "comfy",
            "adapter": "comfy",
            "officialModelId": "flux",
        },
    )
    monkeypatch.setattr("app.image_runtime.contract.resolve_image_workflow", lambda *_a, **_k: contract)

    verbs: list[str] = []
    note_at_commit: list[str] = []

    async def fake_submit(*_a, **_k):
        verbs.append("submit")
        return {"ok": True, "taskId": "pid-auto", "providerId": "local", "adapter": "comfy"}

    async def fake_poll(submitted, *_a, **_k):
        verbs.append("poll")
        out = isolated_data_dir / "auto_out.png"
        out.write_bytes(b"png")
        return {"ok": True, "state": "completed", "files": [out], "imagePath": out, "imageUrl": str(out)}

    async def fake_download(src, dest):
        verbs.append("download")
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(Path(src).read_bytes())
        return Path(dest)

    monkeypatch.setattr("app.image_runtime.local_comfy_adapter.submit", fake_submit)
    monkeypatch.setattr("app.image_runtime.local_comfy_adapter.poll", fake_poll)
    monkeypatch.setattr("app.image_runtime.local_comfy_adapter.download", fake_download)

    committed: list[str] = []

    async def fake_commit(self, *_a, **_k):
        committed.append("commit")
        note_at_commit.append(str(_k.get("note") or ""))

    monkeypatch.setattr(JobQueue, "_imagegen_commit_asset", fake_commit)

    gate = SimpleNamespace(ok=True, errors=[], checksum="sha256:auto", to_dict=lambda: {"ok": True})
    monkeypatch.setattr("app.image_runtime.output_gate.validate_image_output", lambda *_a, **_k: gate)

    db = _FakeDB()
    job = _job(params)
    project = SimpleNamespace(id="proj-cdx076", negative_prompt="", seed=0)
    worker = JobQueue()

    # Snapshot the visible job.message at each commit so we can prove the
    # disclosure was persisted as a first-class status during execution.
    real_commit = db.commit

    def commit_with_snapshot():
        db.messages.append(job.message)
        real_commit()

    db.commit = commit_with_snapshot
    asyncio.run(worker._imagegen(db, job, project))

    assert verbs == ["submit", "poll", "download"]
    assert committed == ["commit"]
    # The PREPARING status persisted to the DB names the executed model + reason.
    assert any("flux.txt2img" in m and "Z-Image unavailable" in m and "compatible local still engine" in m for m in db.messages), db.messages
    # The note is threaded into the final done status (first-class visible status).
    assert note_at_commit, "note must reach _imagegen_commit_asset"
    assert "Z-Image unavailable" in note_at_commit[0]
    assert "flux" in note_at_commit[0]
    # Reasons still recorded in history_json for diagnostics.
    hist = json.loads(job.history_json)
    assert any("Z-Image unavailable" in r for r in (hist.get("reasons") or []))
    # The executed model is the alternate, truthfully recorded.
    assert hist.get("model") == "flux"
    assert hist.get("checkpoint") == settings.imagegen_flux_checkpoint


# --- CDX-076: preflight MODEL_NOT_INSTALLED ----------------------------------


def _unhealthy_verification(detail: str):
    return SimpleNamespace(healthy=False, absent=True, issue_code="required_models_missing", summary=detail)


def test_local_model_installed_reflects_component_verify(monkeypatch) -> None:
    import importlib

    pf = importlib.import_module("app.image_core.preflight")

    monkeypatch.setattr(
        "app.setup.diagnostics.verify_component",
        lambda cid: _unhealthy_verification("One or more Z-Image still-image model files are missing."),
    )
    installed, detail = pf.local_model_installed("zimage")
    assert installed is False
    assert "missing" in detail

    monkeypatch.setattr(
        "app.setup.diagnostics.verify_component",
        lambda cid: SimpleNamespace(healthy=True, summary="Z-Image readable."),
    )
    installed, detail = pf.local_model_installed("zimage")
    assert installed is True

    # Unknown / unverifiable families never block.
    installed, detail = pf.local_model_installed("nano-banana-fal")
    assert installed is True
    installed, detail = pf.local_model_installed("")
    assert installed is True


def test_preflight_model_not_installed_when_zimage_verify_fails(monkeypatch) -> None:
    from app.image_core.preflight import preflight
    from app.image_core.request import ImageCoreRequest

    monkeypatch.setattr(
        "app.setup.diagnostics.verify_component",
        lambda cid: _unhealthy_verification("One or more Z-Image still-image model files are missing."),
    )
    decision = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="scene_shot_final",
            operation="image.generate",
            model_id="zimage",
        )
    )
    assert decision.ok is False
    assert decision.code == MODEL_NOT_INSTALLED
    assert "not installed" in decision.message.lower()
    assert "no alternate model" in decision.message.lower()


def test_preflight_model_not_installed_for_qwen_when_verify_fails(monkeypatch) -> None:
    from app.image_core.preflight import preflight
    from app.image_core.request import ImageCoreRequest

    monkeypatch.setattr(
        "app.setup.diagnostics.verify_component",
        lambda cid: _unhealthy_verification("One or more Qwen-Image-2512 model files are missing."),
    )
    decision = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="scene_shot_final",
            operation="image.generate",
            model_id="qwen2512",
        )
    )
    assert decision.ok is False
    assert decision.code == MODEL_NOT_INSTALLED
    assert "qwen" in decision.message.lower()


def test_preflight_ok_when_selected_local_model_installed(monkeypatch) -> None:
    from app.image_core.preflight import preflight
    from app.image_core.request import ImageCoreRequest

    monkeypatch.setattr(
        "app.setup.diagnostics.verify_component",
        lambda cid: SimpleNamespace(healthy=True, summary="readable"),
    )
    decision = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="scene_shot_final",
            operation="image.generate",
            model_id="zimage",
        )
    )
    assert decision.ok is True
    assert decision.workflow_key == "zimage.txt2img"


def test_preflight_empty_model_skips_installation_check(monkeypatch) -> None:
    from app.image_core.preflight import preflight
    from app.image_core.request import ImageCoreRequest

    monkeypatch.setattr(
        "app.setup.diagnostics.verify_component",
        lambda cid: _unhealthy_verification("missing"),
    )
    # No explicit model -> auto resolution at the worker owns selection.
    decision = preflight(
        ImageCoreRequest(
            project_id="p",
            purpose="scene_shot_preview",
            operation="image.generate",
            model_id="",
        )
    )
    assert decision.ok is True


def test_generate_raises_model_not_installed_before_enqueue(monkeypatch) -> None:
    import sys

    from app.image_core.errors import ImageCoreError
    from app.image_core.generate import generate

    pf = sys.modules["app.image_core.preflight"]
    monkeypatch.setattr(
        pf,
        "local_model_installed",
        lambda family: (False, "One or more Z-Image still-image model files are missing."),
    )

    enqueued: list[str] = []

    def _enqueue(*_a, **_k):
        enqueued.append("enqueue")
        raise AssertionError("must fail BEFORE enqueue")

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _enqueue)

    request = ImageCoreRequest(
        project_id="p",
        purpose="scene_shot_final",
        operation="image.generate",
        model_id="zimage",
    )
    with pytest.raises(ImageCoreError) as ei:
        generate(object(), request)

    assert ei.value.code == MODEL_NOT_INSTALLED
    assert enqueued == []
