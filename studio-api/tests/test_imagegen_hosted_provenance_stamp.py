"""Hosted imagegen asset stamp must match the executed provider.

Regression: _imagegen_commit_asset hardcoded ImageProvenance provider="local"
runtime="comfy" even when the job executed on Kie/fal. Job/candidate rows were
honest; the Library asset stamp was not.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from app.image_runtime.provenance import executed_image_stamp
from app.queue_worker import JobQueue


def test_executed_image_stamp_kie_not_local() -> None:
    provider, runtime, official = executed_image_stamp(
        {
            "hostedModelId": "nano-banana",
            "kieImageModelId": "nano-banana-2",
            "imageRuntime": {
                "workflowKey": "kie:nano-banana-2",
                "provider": "kie",
                "engine": "kie",
                "hostedModelId": "nano-banana",
                "kieImageModelId": "nano-banana-2",
            },
        },
        contract_key="kie:nano-banana-2",
        model="nano-banana",
    )
    assert provider == "kie"
    assert runtime == "kie"
    assert official == "nano-banana-2"
    assert provider != "local"


def test_executed_image_stamp_fal_not_local() -> None:
    provider, runtime, official = executed_image_stamp(
        {
            "falImageModelId": "fal-ai/flux/dev",
            "imageRuntime": {"provider": "fal", "engine": "fal", "hostedModelId": "flux"},
        },
        contract_key="fal-ai/flux/dev",
        model="flux",
    )
    assert provider == "fal"
    assert runtime == "fal"
    assert official == "fal-ai/flux/dev"
    assert provider != "local"


def test_executed_image_stamp_local_comfy_unchanged() -> None:
    provider, runtime, official = executed_image_stamp(
        {"imageRuntime": {"workflowKey": "zimage.txt2img", "provider": "local", "engine": "comfy"}},
        contract_key="zimage.txt2img",
        model="zimage",
    )
    assert provider == "local"
    assert runtime == "comfy"
    assert official == "zimage"


def test_kie_imagegen_commit_stamps_provider_kie_not_local(monkeypatch, isolated_data_dir: Path) -> None:
    """A Kie imagegen commit must stamp provenance.provider=kie + official model."""
    from app.asset_graph import add_edge, add_version  # noqa: F401 — patched below
    from app.config import settings

    project_id = "proj-kie-stamp"
    dest_dir = settings.data_dir / "projects" / project_id / "assets"
    pending = dest_dir / ".pending"
    pending.mkdir(parents=True, exist_ok=True)
    tmp = pending / "imagegen_kie_testhole.png"
    tmp.write_bytes(b"not-a-real-png")

    added: list[object] = []

    class FakeDB:
        def add(self, obj: object) -> None:
            added.append(obj)

        def commit(self) -> None:
            return None

        def get(self, *_a: object, **_k: object) -> None:
            return None

    job = SimpleNamespace(id="job-kie-stamp", kind="imagegen", history_json="{}", params_json="{}")
    project = SimpleNamespace(id=project_id)
    gate = SimpleNamespace(checksum="sha256:deadbeef", to_dict=lambda: {"ok": True, "checksum": "sha256:deadbeef"})

    monkeypatch.setattr("app.asset_graph.add_version", lambda *a, **k: None)
    monkeypatch.setattr("app.asset_graph.add_edge", lambda *a, **k: None)

    worker = JobQueue()
    monkeypatch.setattr(worker, "_set_status", lambda *a, **k: None)

    params = {
        "hostedModelId": "nano-banana",
        "kieImageModelId": "nano-banana-2",
        "tag": "prop_coffee-cup_c3",
        "imageRuntime": {
            "workflowKey": "kie:nano-banana-2",
            "workflowId": "kie:nano-banana-2",
            "provider": "kie",
            "engine": "kie",
            "hostedModelId": "nano-banana",
            "kieImageModelId": "nano-banana-2",
        },
    }

    asyncio.run(
        worker._imagegen_commit_asset(
            FakeDB(),
            job,
            project,
            params,
            tmp,
            gate,
            edit_op="generate",
            prompt="Prop: Coffee Cup",
            seed=1234991581,
            model="nano-banana",
            contract_key="kie:nano-banana-2",
        )
    )

    assert added, "commit must create a Library asset"
    asset = added[0]
    meta = json.loads(asset.prompt_meta_json)
    prov = meta["provenance"]
    assert prov["provider"] == "kie"
    assert prov["provider"] != "local"
    assert prov["runtime"] == "kie"
    assert prov["runtime"] != "comfy"
    assert prov["workflow"] == "kie:nano-banana-2"
    assert prov["settings"]["model"] == "nano-banana-2"

def test_kie_prop_cc_asset_provenance_provider_is_kie(monkeypatch, isolated_data_dir: Path) -> None:
    """Kie Prop / Character Creator assets must stamp provider=kie, not local."""
    from app.config import settings
    from app.image_product.compile import compile_image_request

    project_id = "proj-kie-prop-cc"
    dest_dir = settings.data_dir / "projects" / project_id / "assets"
    pending = dest_dir / ".pending"
    pending.mkdir(parents=True, exist_ok=True)
    tmp = pending / "imagegen_kie_propcc.png"
    tmp.write_bytes(b"not-a-real-png")

    added: list[object] = []

    class FakeDB:
        def add(self, obj: object) -> None:
            added.append(obj)

        def commit(self) -> None:
            return None

        def get(self, *_a: object, **_k: object) -> None:
            return None

    job = SimpleNamespace(id="job-kie-prop-cc", kind="imagegen", history_json="{}", params_json="{}")
    project = SimpleNamespace(id=project_id)
    gate = SimpleNamespace(checksum="sha256:propcc", to_dict=lambda: {"ok": True, "checksum": "sha256:propcc"})

    monkeypatch.setattr("app.asset_graph.add_version", lambda *a, **k: None)
    monkeypatch.setattr("app.asset_graph.add_edge", lambda *a, **k: None)

    worker = JobQueue()
    monkeypatch.setattr(worker, "_set_status", lambda *a, **k: None)

    compiled = compile_image_request(
        project_id,
        {
            "prompt": "Prop: Coffee Cup",
            "purpose": "project_prop",
            "source": "api",
            "hostedModelId": "nano-banana-kie",
            "tag": "prop_coffee-cup_c3",
        },
    )
    runtime = compiled["imageRuntime"]
    params = {
        "hostedModelId": runtime.get("hostedModelId"),
        "kieImageModelId": runtime.get("kieImageModelId"),
        "officialModelId": runtime.get("officialModelId"),
        "tag": "prop_coffee-cup_c3",
        "imageRuntime": runtime,
    }

    asyncio.run(
        worker._imagegen_commit_asset(
            FakeDB(),
            job,
            project,
            params,
            tmp,
            gate,
            edit_op="generate",
            prompt="Prop: Coffee Cup",
            seed=1234991581,
            model=str(runtime.get("hostedModelId") or ""),
            contract_key=str(runtime.get("workflowKey") or ""),
        )
    )

    assert added, "commit must create a Library asset"
    asset = added[0]
    meta = json.loads(asset.prompt_meta_json)
    prov = meta["provenance"]
    assert prov["provider"] == "kie"
    assert prov["provider"] != "local"
    assert prov["runtime"] == "kie"
    assert prov["settings"]["model"] == "nano-banana-2"
    assert prov["workflow"] == "kie:nano-banana-2"


def test_kie_character_sheet_asset_provenance_provider_is_kie(monkeypatch, isolated_data_dir: Path) -> None:
    """Kie Character Creator sheet assets must stamp provider=kie, not local."""
    from app.config import settings
    from app.image_product.compile import compile_image_request

    project_id = "proj-kie-cc-sheet"
    dest_dir = settings.data_dir / "projects" / project_id / "assets"
    pending = dest_dir / ".pending"
    pending.mkdir(parents=True, exist_ok=True)
    tmp = pending / "imagegen_kie_cc_sheet.png"
    tmp.write_bytes(b"not-a-real-png")

    added: list[object] = []

    class FakeDB:
        def add(self, obj: object) -> None:
            added.append(obj)

        def commit(self) -> None:
            return None

        def get(self, *_a: object, **_k: object) -> None:
            return None

    job = SimpleNamespace(id="job-kie-cc-sheet", kind="imagegen", history_json="{}", params_json="{}")
    project = SimpleNamespace(id=project_id)
    gate = SimpleNamespace(checksum="sha256:ccsheet", to_dict=lambda: {"ok": True, "checksum": "sha256:ccsheet"})

    monkeypatch.setattr("app.asset_graph.add_version", lambda *a, **k: None)
    monkeypatch.setattr("app.asset_graph.add_edge", lambda *a, **k: None)

    worker = JobQueue()
    monkeypatch.setattr(worker, "_set_status", lambda *a, **k: None)

    compiled = compile_image_request(
        project_id,
        {
            "prompt": "Korri four-panel character turnaround sheet",
            "purpose": "character_sheet",
            "source": "api",
            "hostedModelId": "nano-banana-kie",
            "layout": "four_view",
            "tag": "character_sheet_korri",
        },
    )
    runtime = compiled["imageRuntime"]
    params = {
        "hostedModelId": runtime.get("hostedModelId"),
        "kieImageModelId": runtime.get("kieImageModelId"),
        "officialModelId": runtime.get("officialModelId"),
        "purpose": "character_sheet",
        "layout": "four_view",
        "tag": "character_sheet_korri",
        "imageRuntime": runtime,
    }

    asyncio.run(
        worker._imagegen_commit_asset(
            FakeDB(),
            job,
            project,
            params,
            tmp,
            gate,
            edit_op="generate",
            prompt="Korri four-panel character turnaround sheet",
            seed=7,
            model=str(runtime.get("hostedModelId") or ""),
            contract_key=str(runtime.get("workflowKey") or ""),
        )
    )

    assert added, "commit must create a Library asset"
    asset = added[0]
    meta = json.loads(asset.prompt_meta_json)
    prov = meta["provenance"]
    assert prov["provider"] == "kie"
    assert prov["provider"] != "local"
    assert prov["runtime"] == "kie"
    assert prov["runtime"] != "comfy"
    assert str(prov.get("workflow") or "").startswith("kie:")
    assert prov["settings"]["model"] == "nano-banana-2"
