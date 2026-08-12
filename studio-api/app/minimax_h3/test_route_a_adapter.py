"""Route A adapter unit tests with mocked HTTP (no real ComfyUI contact)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.minimax_h3 import route_a_adapter, store
from app.minimax_h3.route_a_adapter import (
    EXPERIMENTAL_HEIGHT,
    EXPERIMENTAL_LENGTH,
    EXPERIMENTAL_STEPS,
    EXPERIMENTAL_WIDTH,
    I2V_CONDITIONING_NODE_ID,
    LOAD_IMAGE_NODE_ID,
    RouteAJobState,
    RouteARuntimeAdapter,
    assert_i2va_graph_binding,
    build_i2va_graph,
    build_t2va_graph,
    validate_media,
)


def test_experimental_profile_is_fixed_5_frames_256_height() -> None:
    assert EXPERIMENTAL_HEIGHT == 256
    assert EXPERIMENTAL_WIDTH == 480
    assert EXPERIMENTAL_LENGTH == 5
    assert EXPERIMENTAL_STEPS == 4


def test_graph_uses_isolated_profile_dimensions() -> None:
    graph = build_t2va_graph("coastal observatory blue light", seed=42, filename_prefix="video/Adept")
    sampler = graph["5"]
    assert sampler["class_type"] == "MiniMaxH3ImageToVideo"
    inputs = sampler["inputs"]
    assert inputs["width"] == EXPERIMENTAL_WIDTH
    assert inputs["height"] == EXPERIMENTAL_HEIGHT
    assert inputs["length"] == EXPERIMENTAL_LENGTH
    assert inputs["prompt"] == "coastal observatory blue light"
    # SaveVideo must use the prefixed path, never raw checkpoint names.
    save = graph["14"]["inputs"]
    assert save["filename_prefix"] == "video/Adept"
    dumped = json.dumps(graph)
    # No diffusers-shard markers may leak into the graph.
    for marker in route_a_adapter.FORBIDDEN_SHARD_MARKERS:
        assert marker not in dumped


def test_i2va_graph_wires_loadimage_first_frame() -> None:
    graph = build_i2va_graph(
        "identity-preserving motion",
        seed=7,
        filename_prefix="video/Adept_I2V",
        first_frame_comfy_name="studio/h3_i2v_abcd.png",
    )
    assert graph[LOAD_IMAGE_NODE_ID]["class_type"] == "LoadImage"
    assert graph[LOAD_IMAGE_NODE_ID]["inputs"]["image"] == "studio/h3_i2v_abcd.png"
    first = graph[I2V_CONDITIONING_NODE_ID]["inputs"]["first_frame"]
    assert first == [LOAD_IMAGE_NODE_ID, 0]
    assert_i2va_graph_binding(graph, expected_comfy_name="studio/h3_i2v_abcd.png")
    # T2V graph must not silently satisfy I2V binding.
    t2v = build_t2va_graph("x", seed=1, filename_prefix="video/x")
    with pytest.raises(ValueError, match="LoadImage"):
        assert_i2va_graph_binding(t2v, expected_comfy_name="studio/h3_i2v_abcd.png")


def test_i2va_graph_rejects_empty_comfy_name() -> None:
    with pytest.raises(ValueError, match="first_frame_comfy_name"):
        build_i2va_graph("x", seed=1, filename_prefix="video/x", first_frame_comfy_name="")


def test_submit_i2va_fails_when_image_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(store, "_root", lambda: tmp_path)
    adapter = _make_adapter()
    monkeypatch.setattr(adapter, "readiness", lambda: {"ready": True, "creatorStatus": "ok"})
    state = adapter.submit_i2va(
        project_id="p1",
        plan_id="plan1",
        prompt="motion",
        start_image_path=tmp_path / "missing.png",
    )
    assert state.status == "failed"
    assert state.error_code == "H3_START_IMAGE_MISSING"


def test_graph_has_no_comfy_checkpoint_filenames_exposed() -> None:
    graph = build_t2va_graph("prompt", seed=1, filename_prefix="video/x")
    dumped = json.dumps(graph).lower()
    # The graph references node names internally, but the creator-facing
    # surface must never expose raw .safetensors shard names.
    assert "minimax_h3_fl2va_pruned_int8_convrot" not in dumped.replace("_", "")
    assert "from_pretrained" not in dumped


class _FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _make_adapter():
    return RouteARuntimeAdapter(base_url="http://127.0.0.1:8192")


def test_health_offline_returns_unavailable(monkeypatch) -> None:
    adapter = _make_adapter()

    def _boom(*a, **k):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(adapter._session, "get", _boom)
    health = adapter.health()
    assert health["ok"] is False
    assert health["errorCode"] == "H3_RUNTIME_UNAVAILABLE"


def test_readiness_missing_files_blocks_ready(monkeypatch, tmp_path) -> None:
    adapter = _make_adapter()

    monkeypatch.setattr(
        adapter._session,
        "get",
        lambda url, **k: _FakeResponse(
            body={
                "system": {"comfyui_version": "x"},
                "devices": [{"name": "cuda:0 NVIDIA RTX"}],
            }
        )
        if "system_stats" in url
        else _FakeResponse(body={node: {} for node in route_a_adapter.REQUIRED_NODES}),
    )
    # Force all checkpoint paths to missing.
    monkeypatch.setattr(
        route_a_adapter,
        "required_checkpoint_paths",
        lambda: {"transformer": tmp_path / "missing.safetensors"},
    )
    result = adapter.readiness()
    assert result["ready"] is False
    assert "transformer" in result["missingFiles"]
    assert result["profile"]["label"] == "Experimental Private Profile"


def test_readiness_missing_nodes_blocks_ready(monkeypatch) -> None:
    adapter = _make_adapter()

    monkeypatch.setattr(
        adapter._session,
        "get",
        lambda url, **k: _FakeResponse(
            body={
                "system": {"comfyui_version": "x"},
                "devices": [{"name": "cuda:0 NVIDIA"}],
            }
        )
        if "system_stats" in url
        else _FakeResponse(body={"UNETLoader": {}}),  # missing most nodes
    )
    monkeypatch.setattr(
        route_a_adapter,
        "required_checkpoint_paths",
        lambda: {"transformer": tmp_path / "ok.safetensors"} if False else {},
    )
    result = adapter.readiness()
    assert result["ready"] is False
    assert result["missingNodes"]


def test_readiness_ready_when_files_nodes_gpu_present(monkeypatch, tmp_path) -> None:
    adapter = _make_adapter()
    ckpt = tmp_path / "unet.safetensors"
    ckpt.write_bytes(b"x")

    monkeypatch.setattr(
        adapter._session,
        "get",
        lambda url, **k: _FakeResponse(
            body={
                "system": {"comfyui_version": "x"},
                "devices": [{"name": "cuda:0 NVIDIA RTX"}],
            }
        )
        if "system_stats" in url
        else _FakeResponse(body={node: {} for node in route_a_adapter.REQUIRED_NODES}),
    )
    monkeypatch.setattr(
        route_a_adapter,
        "required_checkpoint_paths",
        lambda: {"transformer": ckpt},
    )
    result = adapter.readiness()
    assert result["ready"] is True
    assert result["profile"]["nativeAudio"] is True
    assert result["profile"]["height"] == 256


def test_submit_blocks_when_not_ready(monkeypatch, tmp_path) -> None:
    adapter = _make_adapter()
    monkeypatch.setattr(adapter._session, "get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(adapter, "_persist_job", lambda s: None)
    state = adapter.submit_t2va(project_id="p", plan_id="pl", prompt="x", seed=1)
    assert state.status == "failed"
    assert state.error_code == "H3_RUNTIME_UNAVAILABLE"


def test_submit_rejects_diffusers_shard_graph(monkeypatch, tmp_path) -> None:
    adapter = _make_adapter()
    monkeypatch.setattr(adapter, "readiness", lambda: {"ready": True, "profile": {}})
    monkeypatch.setattr(adapter, "_persist_job", lambda s: None)
    # Inject a forbidden marker into the prompt so the dumped graph contains it.
    state = adapter.submit_t2va(
        project_id="p",
        plan_id="pl",
        prompt="model-00001-of-00002.safetensors",
        seed=1,
    )
    assert state.status == "failed"
    assert state.error_code == "H3_MODEL_INCOMPATIBLE"


def test_submit_success_returns_prompt_id(monkeypatch) -> None:
    adapter = _make_adapter()
    monkeypatch.setattr(adapter, "readiness", lambda: {"ready": True, "profile": {}})
    monkeypatch.setattr(adapter, "_persist_job", lambda s: None)

    captured = {}

    def _post(url, json=None, **k):
        captured["url"] = url
        captured["body"] = json
        return _FakeResponse(body={"prompt_id": "pid-123"})

    monkeypatch.setattr(adapter._session, "post", _post)
    state = adapter.submit_t2va(project_id="p", plan_id="pl", prompt="coastal", seed=7)
    assert state.status == "running"
    assert state.prompt_id == "pid-123"
    assert "client_id" in captured["body"]
    assert captured["url"].endswith("/prompt")


def test_poll_completes_and_validates(monkeypatch, tmp_path) -> None:
    adapter = _make_adapter()
    mp4 = tmp_path / "Adept_H3_Private_abcd1234.mp4"
    mp4.write_bytes(b"\x00\x00\x00\x20ftypisom")  # tiny non-empty file

    state = RouteAJobState(
        job_id="abcd1234deadbeef",
        project_id="p",
        plan_id="pl",
        prompt="x",
        seed=1,
        prompt_id="pid-123",
        status="running",
    )

    history_body = {
        "pid-123": {
            "status": {"status_str": "success"},
            "outputs": {
                "14": {
                    "videos": [
                        {"filename": mp4.name, "subfolder": ""},
                    ]
                }
            },
        }
    }

    monkeypatch.setattr(
        adapter._session,
        "get",
        lambda url, **k: _FakeResponse(body=history_body),
    )
    monkeypatch.setattr(adapter, "_resolve_output_file", lambda filename, subfolder: mp4)
    monkeypatch.setattr(adapter, "_persist_job", lambda s: None)
    # validate_media needs ffprobe; stub it to a passing result.
    monkeypatch.setattr(
        route_a_adapter,
        "validate_media",
        lambda path: {"ok": True, "path": str(path), "width": 480, "height": 256},
    )

    result = adapter.poll(state, timeout_sec=5.0)
    assert result.status == "completed"
    assert result.output_path == str(mp4)
    assert result.provenance["modelId"] == "minimax-h3-route-a-local"
    assert result.provenance["apiUsed"] is False
    assert result.provenance["ltxUsed"] is False
    assert result.provenance["runtime"] == "route-a"
    assert result.provenance["profile"] == "Experimental Private Profile"


def test_poll_failed_runtime_marks_failed(monkeypatch) -> None:
    adapter = _make_adapter()
    state = RouteAJobState(
        job_id="j",
        project_id="p",
        plan_id="pl",
        prompt="x",
        seed=1,
        prompt_id="pid-err",
        status="running",
    )
    monkeypatch.setattr(
        adapter._session,
        "get",
        lambda url, **k: _FakeResponse(body={"pid-err": {"status": {"status_str": "error"}}}),
    )
    monkeypatch.setattr(adapter, "_persist_job", lambda s: None)
    result = adapter.poll(state, timeout_sec=5.0)
    assert result.status == "failed"
    assert result.error_code == "H3_JOB_FAILED"
    # The adapter must surface a real message, not null (regression for the
    # RED symptom H3_JOB_FAILED with errorMessage=null).
    assert result.error_message
    assert result.error_message != "null"


def test_poll_surfaces_execution_error_detail(monkeypatch) -> None:
    """Regression: the real ComfyUI execution_error must be surfaced."""
    adapter = _make_adapter()
    state = RouteAJobState(
        job_id="j",
        project_id="p",
        plan_id="pl",
        prompt="x",
        seed=1,
        prompt_id="pid-errno22",
        status="running",
    )
    history = {
        "pid-errno22": {
            "status": {
                "status_str": "error",
                "completed": False,
                "messages": [
                    ["execution_start", {"prompt_id": "pid-errno22"}],
                    [
                        "execution_error",
                        {
                            "prompt_id": "pid-errno22",
                            "node_id": "10",
                            "node_type": "SamplerCustomAdvanced",
                            "exception_message": "[Errno 22] Invalid argument\n",
                            "exception_type": "OSError",
                        },
                    ],
                ],
            }
        }
    }
    monkeypatch.setattr(
        adapter._session,
        "get",
        lambda url, **k: _FakeResponse(body=history),
    )
    monkeypatch.setattr(adapter, "_persist_job", lambda s: None)
    result = adapter.poll(state, timeout_sec=5.0)
    assert result.status == "failed"
    assert result.error_code == "H3_JOB_FAILED"
    # The swallowed null message is gone; the real cause is surfaced.
    assert result.error_message is not None
    assert "Errno 22" in result.error_message
    assert "OSError" in result.error_message
    assert "SamplerCustomAdvanced" in result.error_message


def test_poll_interrupted_surfaces_interrupt_message(monkeypatch) -> None:
    """An interrupted status (no execution_error payload) surfaces a real message."""
    adapter = _make_adapter()
    state = RouteAJobState(
        job_id="j",
        project_id="p",
        plan_id="pl",
        prompt="x",
        seed=1,
        prompt_id="pid-int",
        status="running",
    )
    monkeypatch.setattr(
        adapter._session,
        "get",
        lambda url, **k: _FakeResponse(body={"pid-int": {"status": {"status_str": "interrupted"}}}),
    )
    monkeypatch.setattr(adapter, "_persist_job", lambda s: None)
    result = adapter.poll(state, timeout_sec=5.0)
    assert result.status == "failed"
    assert result.error_code == "H3_JOB_FAILED"
    assert result.error_message == "interrupted"


def test_poll_cancelled_state_short_circuits(monkeypatch) -> None:
    adapter = _make_adapter()
    state = RouteAJobState(
        job_id="j",
        project_id="p",
        plan_id="pl",
        prompt="x",
        seed=1,
        prompt_id="pid-c",
        status="running",
        cancelled=True,
    )
    monkeypatch.setattr(adapter, "_persist_job", lambda s: None)
    result = adapter.poll(state, timeout_sec=5.0)
    assert result.status == "cancelled"
    assert result.error_code == "H3_CANCELLED"


def test_cancel_calls_interrupt_and_marks_cancelled(monkeypatch) -> None:
    adapter = _make_adapter()
    called = {"interrupt": False}

    def _post(url, **k):
        called["interrupt"] = url.endswith("/interrupt")
        return _FakeResponse()

    monkeypatch.setattr(adapter._session, "post", _post)
    monkeypatch.setattr(adapter, "_persist_job", lambda s: None)
    state = RouteAJobState(job_id="j", project_id="p", plan_id="pl", prompt="x", seed=1)
    result = adapter.cancel(state)
    assert result.status == "cancelled"
    assert called["interrupt"] is True


def test_validate_media_missing_file_returns_invalid(tmp_path) -> None:
    result = validate_media(tmp_path / "nope.mp4")
    assert result["ok"] is False
    assert result["errorCode"] == "H3_OUTPUT_INVALID"


def test_import_output_to_project_library_copies_asset(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(store, "_root", lambda: tmp_path / "h3store")
    src = tmp_path / "src.mp4"
    src.write_bytes(b"\x00\x00\x00\x20ftypisom")

    class _FakeAsset:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class _FakeProject:
        updated_at = None

    class _FakeDb:
        def __init__(self):
            self.added = []
            self.committed = False

        def get(self, cls, pk):
            # The helper only looks up the project by id; assets are created, not fetched.
            if pk == "proj-1":
                return _FakeProject()
            return None

        def add(self, obj):
            self.added.append(obj)

        def commit(self):
            self.committed = True

        def refresh(self, obj):
            return obj

    # Patch the config + db symbols the helper imports lazily.
    from app import config as config_mod
    from app import db as db_mod

    monkeypatch.setattr(config_mod, "settings", type("S", (), {"data_dir": tmp_path / "data"})())
    monkeypatch.setattr(db_mod, "Asset", _FakeAsset)
    monkeypatch.setattr(db_mod, "Project", _FakeProject)
    db = _FakeDb()
    receipt = route_a_adapter.import_output_to_project_library(
        project_id="proj-1",
        source_mp4=src,
        tag="minimax-h3",
        db=db,
    )
    assert receipt["projectId"] == "proj-1"
    assert receipt["tag"] == "minimax-h3"
    assert db.committed is True
    assert Path(receipt["path"]).is_file()
