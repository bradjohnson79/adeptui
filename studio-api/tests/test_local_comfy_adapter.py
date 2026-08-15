"""Phase C: local imagegen uses the LocalComfy submit/poll/download façade."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace


def test_local_comfy_submit_poll_download_shape(monkeypatch, tmp_path: Path) -> None:
    from app.image_runtime import local_comfy_adapter as lca

    queued: dict[str, object] = {}

    async def fake_queue(wf, workflow_key=None, **_k):
        queued["wf"] = wf
        queued["key"] = workflow_key
        return "pid-local-1"

    hist = {"outputs": {"9": {"images": [{"filename": "out.png"}]}}}

    async def fake_wait(pid, **_k):
        queued["waited"] = pid
        return hist

    out = tmp_path / "comfy" / "out.png"
    out.parent.mkdir(parents=True)
    out.write_bytes(b"PNGDATA")

    def fake_find(_history):
        queued["found"] = True
        return [out]

    monkeypatch.setattr("app.comfy_client.comfy.queue_prompt", fake_queue)
    monkeypatch.setattr("app.comfy_client.comfy.wait_for_prompt", fake_wait)
    monkeypatch.setattr("app.comfy_client.comfy.find_output_files", fake_find)

    submitted = asyncio.run(lca.submit({"1": {"class_type": "X"}}, workflow_key="flux.txt2img"))
    assert submitted["ok"] is True
    assert submitted["taskId"] == "pid-local-1"
    assert submitted["providerId"] == "local"
    assert submitted["adapter"] == "comfy"
    assert queued["key"] == "flux.txt2img"

    polled = asyncio.run(lca.poll(submitted))
    assert polled["ok"] is True
    assert polled["state"] == "completed"
    assert polled["files"][0] == out
    assert queued["waited"] == "pid-local-1"

    dest = tmp_path / "pending" / "dest.png"
    result = asyncio.run(lca.download(polled["files"][0], dest))
    assert Path(result).read_bytes() == b"PNGDATA"


def test_local_comfy_submit_builds_leaf_graph(monkeypatch) -> None:
    from app.image_runtime import local_comfy_adapter as lca

    built: dict[str, object] = {}

    def fake_build(contract, **kw):
        built["contract"] = contract
        built["prompt"] = kw.get("prompt")
        return {"1": {"class_type": "Fake"}}

    def fake_prep(contract, wf, **_kw):
        built["prep"] = True
        return wf

    async def fake_queue(wf, workflow_key=None, **_k):
        built["queued"] = wf
        built["key"] = workflow_key
        return "pid-local-2"

    monkeypatch.setattr("app.image_runtime.workflow_execute.build_leaf_graph", fake_build)
    monkeypatch.setattr("app.image_runtime.workflow_execute.prepare_executable_graph", fake_prep)
    monkeypatch.setattr("app.comfy_client.comfy.queue_prompt", fake_queue)

    contract = SimpleNamespace(workflow_key="flux.txt2img", status="Draft")
    submitted = asyncio.run(
        lca.submit(contract=contract, settings=object(), prompt="a mug", width=1024, height=1024, seed=1)
    )
    assert built.get("prep") is True
    assert built.get("prompt") == "a mug"
    assert submitted["taskId"] == "pid-local-2"
    assert submitted["providerId"] == "local"


def test_local_imagegen_goes_through_facade(monkeypatch, isolated_data_dir: Path) -> None:
    """Worker local execute must call LocalComfy submit/poll/download, not raw Comfy."""
    from app.queue_worker import JobQueue

    verbs: list[str] = []

    async def fake_submit(*_a, **_k):
        verbs.append("submit")
        return {"ok": True, "taskId": "pid-facade", "providerId": "local", "adapter": "comfy"}

    async def fake_poll(submitted, *_a, **_k):
        verbs.append("poll")
        assert submitted.get("taskId") == "pid-facade"
        out = isolated_data_dir / "comfy_out.png"
        out.write_bytes(b"png")
        return {"ok": True, "state": "completed", "files": [out], "imagePath": out, "imageUrl": str(out)}

    async def fake_download(src, dest):
        verbs.append("download")
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(Path(src).read_bytes())
        return Path(dest)

    async def boom_queue(*_a, **_k):
        raise AssertionError("worker must not call comfy.queue_prompt directly")

    monkeypatch.setattr("app.image_runtime.local_comfy_adapter.submit", fake_submit)
    monkeypatch.setattr("app.image_runtime.local_comfy_adapter.poll", fake_poll)
    monkeypatch.setattr("app.image_runtime.local_comfy_adapter.download", fake_download)
    monkeypatch.setattr("app.comfy_client.comfy.queue_prompt", boom_queue)

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
    monkeypatch.setattr(
        "app.image_runtime.contract.resolve_image_workflow",
        lambda *_a, **_k: contract,
    )

    committed: list[str] = []

    async def fake_commit(self, *_a, **_k):
        committed.append("commit")

    monkeypatch.setattr(JobQueue, "_imagegen_commit_asset", fake_commit)
    monkeypatch.setattr(JobQueue, "_checkpoint_for_model", lambda self, model, custom="": "flux.safetensors")
    monkeypatch.setattr(JobQueue, "_zimage_stack_ready", lambda self: False)

    gate = SimpleNamespace(ok=True, errors=[], checksum="sha256:facade", to_dict=lambda: {"ok": True})
    monkeypatch.setattr("app.image_runtime.output_gate.validate_image_output", lambda *_a, **_k: gate)

    class FakeDB:
        def commit(self) -> None:
            return None

        def add(self, _obj: object) -> None:
            return None

        def get(self, *_a: object, **_k: object) -> None:
            return None

    project_id = "proj-local-facade"
    params = {
        "prompt": "a brass mug",
        "model": "flux",
        "source": "local",
        "providerPreference": "local",
        "width": 1024,
        "height": 1024,
        "seed": 7,
        "imageIntent": {
            "projectId": project_id,
            "prompt": "a brass mug",
            "enginePreference": "flux",
            "providerPreference": "local",
            "operation": "image.generate",
            "purpose": "project_prop",
            "width": 1024,
            "height": 1024,
            "metadata": {},
        },
        "imageRuntime": {"provider": "local", "engine": "comfy", "adapter": "comfy"},
    }
    job = SimpleNamespace(
        id="job-local-facade",
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
    project = SimpleNamespace(id=project_id, negative_prompt="", seed=0)
    worker = JobQueue()

    asyncio.run(worker._imagegen(FakeDB(), job, project))

    assert verbs == ["submit", "poll", "download"]
    assert committed == ["commit"]
    assert job.comfy_prompt_id == "pid-facade"


def test_local_execute_stamp_stays_provider_local() -> None:
    from app.image_runtime.provenance import executed_image_stamp

    provider, runtime, official = executed_image_stamp(
        {
            "imageRuntime": {
                "workflowKey": "flux.txt2img",
                "provider": "local",
                "engine": "comfy",
                "adapter": "comfy",
                "officialModelId": "flux",
            }
        },
        contract_key="flux.txt2img",
        model="flux",
    )
    assert provider == "local"
    assert runtime == "comfy"
    assert official == "flux"
    assert provider != "kie"
