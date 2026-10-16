"""Installation profile readiness. A profile change does not delete files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.setup.first_run import assess_first_run
from app.setup.installation_profile import (
    LTX_GROUP,
    expand_local_selection,
    local_ai_contract,
    local_ai_required,
    required_ids_for,
    save_installation_profile,
)
from app.setup.state import load_state
from app.setup.lifecycle.service import remove_component


@pytest.fixture()
def setup_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.config import settings
    from app.setup import status as setup_status

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    setup_status._STATUS_CACHE = None
    return tmp_path


def _components(**overrides: str) -> list[dict]:
    ids = (
        "python",
        "ffmpeg",
        "comfyui",
        "zimage_models",
        "ltx_2_5_checkpoint",
        "ltx_2_5_text_encoder",
        "ltx_2_5_video_vae",
    )
    return [
        {
            "id": component_id,
            "name": component_id,
            "required": component_id in {"python", "ffmpeg", "comfyui"},
            "status": overrides.get(component_id, "not_installed"),
        }
        for component_id in ids
    ]


def test_discovered_models_do_not_commit_a_profile(setup_data_dir: Path) -> None:
    report = assess_first_run(
        _components(python="ready", ffmpeg="ready", comfyui="ready", zimage_models="ready"),
        fetch_nodes=False,
    )
    assert report["installationProfile"] is None
    assert not (setup_data_dir / "setup_state.json").exists() or "installation_profile" not in json.loads(
        (setup_data_dir / "setup_state.json").read_text(encoding="utf-8")
    )


def test_a_saved_profile_is_reported_and_keys_stay_out_of_setup_json(setup_data_dir: Path) -> None:
    save_installation_profile("api", providers=["fal"])
    raw = (setup_data_dir / "setup_state.json").read_text(encoding="utf-8")
    assert "fal-secret" not in raw
    assert "api_key" not in raw
    report = assess_first_run(_components(python="ready", ffmpeg="ready"), fetch_nodes=False)
    assert report["installationProfile"] == "api"


def test_manual_engine_is_not_queued_as_an_install(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    save_installation_profile("local")
    monkeypatch.setattr(
        "app.setup.status.build_status",
        lambda persist=True: {
            "components": [
                {"id": "python", "status": "ready"},
                {"id": "ffmpeg", "status": "ready"},
                {"id": "comfyui", "status": "not_installed"},
                {"id": "zimage_models", "status": "ready"},
                {"id": "ltx_2_5_checkpoint", "status": "ready"},
                {"id": "ltx_2_5_text_encoder", "status": "ready"},
                {"id": "ltx_2_5_video_vae", "status": "ready"},
            ]
        },
    )

    def placeholder(component_id: str, **kwargs: object) -> dict:
        return {
            "id": f"job-{component_id}",
            "active": False,
            "state": "awaiting_confirmation",
            "message": "cannot be enqueued",
            "error": {"message": "cannot be enqueued"},
        }

    monkeypatch.setattr("app.source_manager.install_jobs.service.create_or_resume_install", placeholder)
    from app.setup.installation_profile import COMFY_NOT_DOWNLOADABLE, apply_saved_profile

    result = apply_saved_profile()
    assert result["queued"] == []
    assert result["errors"] == [{"id": "comfyui", "message": COMFY_NOT_DOWNLOADABLE}]


def test_api_profile_does_not_require_local_weights(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    save_installation_profile("api", providers=["fal"])
    monkeypatch.setattr(
        "app.setup.installation_profile.verified_providers",
        lambda: [{"id": "fal", "name": "fal.ai"}],
    )
    report = assess_first_run(
        _components(python="ready", ffmpeg="ready"),
        node_types=set(),
        fetch_nodes=False,
    )
    assert report["installationProfile"] == "api"
    assert "zimage_models" not in report["baselineIds"]
    assert "ltx_2_5_checkpoint" not in report["baselineIds"]
    assert report["baselineImageWorkflow"] == "not_required"
    assert report["baselineVideoWorkflow"] == "not_required"
    assert report["ready"] is True
    assert report["connectedProviders"] == [{"id": "fal", "name": "fal.ai"}]


def test_api_profile_blocks_without_a_verified_provider(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    save_installation_profile("api")
    monkeypatch.setattr("app.setup.installation_profile.verified_providers", lambda: [])
    report = assess_first_run(_components(python="ready", ffmpeg="ready"), fetch_nodes=False)
    assert report["ready"] is False
    assert any(item["id"] == "provider:validated" for item in report["essentialBlockers"])


def test_hybrid_without_a_selection_is_not_complete(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    save_installation_profile("hybrid", selected_models=[], providers=[])
    monkeypatch.setattr("app.setup.installation_profile.verified_providers", lambda: [])
    report = assess_first_run(_components(python="ready", ffmpeg="ready"), fetch_nodes=False)
    assert any(item["id"] == "profile:selection" for item in report["essentialBlockers"])


def test_ltx_selection_keeps_the_encoder_and_video_vae() -> None:
    expanded = expand_local_selection(["ltx_2_5_checkpoint"])
    assert set(LTX_GROUP).issubset(expanded)
    assert "comfyui" in expanded


def test_profile_switch_does_not_delete_weights_or_projects(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    weight = setup_data_dir / "models" / "zimage.safetensors"
    project = setup_data_dir / "projects" / "scene.json"
    weight.parent.mkdir()
    project.parent.mkdir()
    weight.write_bytes(b"weight")
    project.write_text("{}", encoding="utf-8")
    save_installation_profile("local")
    save_installation_profile("api", providers=["fal"])
    state = json.loads((setup_data_dir / "setup_state.json").read_text(encoding="utf-8"))
    assert state["installation_profile"] == "api"
    assert state["selected_local_models"] == []
    assert weight.read_bytes() == b"weight"
    assert project.read_text(encoding="utf-8") == "{}"

    calls: list[str] = []

    def refuse(component_id: str, **kwargs: object) -> dict:
        calls.append(component_id)
        raise AssertionError("already-ready components must not be queued")

    monkeypatch.setattr("app.source_manager.install_jobs.service.create_or_resume_install", refuse)
    monkeypatch.setattr(
        "app.setup.status.build_status",
        lambda persist=True: {
            "components": [
                {"id": "python", "status": "ready"},
                {"id": "ffmpeg", "status": "ready"},
            ]
        },
    )
    from app.setup.installation_profile import apply_saved_profile

    result = apply_saved_profile()
    assert result["queued"] == []
    assert calls == []
    assert weight.exists()


def test_api_completion_does_not_block_on_missing_ffmpeg(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    save_installation_profile("api", providers=["fal"])
    monkeypatch.setattr(
        "app.setup.installation_profile.verified_providers",
        lambda: [{"id": "fal", "name": "fal.ai"}],
    )
    report = assess_first_run(
        _components(python="ready", ffmpeg="not_installed"),
        fetch_nodes=False,
    )
    assert report["ready"] is True
    assert report["essentialBlockerCount"] == 0
    assert all(item["id"] != "ffmpeg" for item in report["essentialNeeded"])
    assert "zimage_models" not in report["baselineIds"]
    assert "comfyui" not in report["baselineIds"]


def test_api_apply_does_not_enqueue_ffmpeg(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    save_installation_profile("api", providers=["fal"])
    calls: list[str] = []

    def refuse(component_id: str, **kwargs: object) -> dict:
        calls.append(component_id)
        return {
            "id": f"job-{component_id}",
            "active": False,
            "state": "awaiting_confirmation",
            "error": {"message": f"{component_id} cannot be enqueued through install jobs yet."},
        }

    monkeypatch.setattr("app.source_manager.install_jobs.service.create_or_resume_install", refuse)
    monkeypatch.setattr(
        "app.setup.status.build_status",
        lambda persist=True: {
            "components": [
                {"id": "python", "status": "ready"},
                {"id": "ffmpeg", "status": "not_installed"},
            ]
        },
    )
    from app.setup.installation_profile import apply_saved_profile

    result = apply_saved_profile()
    assert calls == []
    assert result["errors"] == []
    assert "ffmpeg" not in result["queued"]


def test_local_missing_ffmpeg_does_not_block_or_enqueue(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_installation_profile("local")
    calls: list[str] = []

    def track(component_id: str, **kwargs: object) -> dict:
        calls.append(component_id)
        return {"id": f"job-{component_id}", "active": True, "state": "queued"}

    monkeypatch.setattr("app.source_manager.install_jobs.service.create_or_resume_install", track)
    monkeypatch.setattr(
        "app.setup.status.build_status",
        lambda persist=True: {
            "components": [
                {"id": "python", "status": "ready"},
                {"id": "ffmpeg", "status": "not_installed"},
                {"id": "comfyui", "status": "ready"},
                {"id": "zimage_models", "status": "ready"},
                {"id": "ltx_2_5_checkpoint", "status": "ready"},
                {"id": "ltx_2_5_text_encoder", "status": "ready"},
                {"id": "ltx_2_5_video_vae", "status": "ready"},
            ]
        },
    )
    from app.setup.installation_profile import apply_saved_profile

    result = apply_saved_profile()
    assert "ffmpeg" not in calls
    assert result["errors"] == []
    report = assess_first_run(
        _components(
            python="ready",
            ffmpeg="not_installed",
            comfyui="ready",
            zimage_models="ready",
            ltx_2_5_checkpoint="ready",
            ltx_2_5_text_encoder="ready",
            ltx_2_5_video_vae="ready",
        ),
        fetch_nodes=False,
    )
    assert "ffmpeg" not in report["baselineIds"]
    assert all(item["id"] != "ffmpeg" for item in report["essentialNeeded"])


def test_ffmpeg_is_required_only_when_a_selected_workflow_depends_on_it(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_installation_profile("local")
    assert "ffmpeg" not in required_ids_for("local", load_state())
    save_installation_profile("api", providers=["fal"])
    assert required_ids_for("api", load_state()) == ("python",)
    save_installation_profile("hybrid", selected_models=["ace_step_local"], providers=["fal"])
    hybrid_ids = required_ids_for("hybrid", load_state())
    assert "ace_step_local" in hybrid_ids
    assert "ffmpeg" in hybrid_ids
    calls: list[str] = []

    def track(component_id: str, **kwargs: object) -> dict:
        calls.append(component_id)
        return {"id": f"job-{component_id}", "active": True, "state": "queued"}

    monkeypatch.setattr("app.source_manager.install_jobs.service.create_or_resume_install", track)
    monkeypatch.setattr(
        "app.setup.status.build_status",
        lambda persist=True: {
            "components": [
                {"id": "python", "status": "ready"},
                {"id": "ffmpeg", "status": "not_installed"},
                {"id": "comfyui", "status": "ready"},
                {"id": "ace_step_local", "status": "ready"},
            ]
        },
    )
    from app.setup.installation_profile import apply_saved_profile

    applied = apply_saved_profile()
    assert "ffmpeg" not in calls
    assert applied["errors"] == []
    monkeypatch.setattr(
        "app.setup.installation_profile.verified_providers",
        lambda: [{"id": "fal", "name": "fal.ai"}],
    )
    rows = _components(
        python="ready",
        ffmpeg="not_installed",
        comfyui="ready",
    )
    rows.append({"id": "ace_step_local", "name": "ACE-Step", "required": False, "status": "ready"})
    report = assess_first_run(rows, fetch_nodes=False)
    assert report["ready"] is False
    assert any(item["id"] == "ffmpeg" for item in report["essentialNeeded"])


def test_ffmpeg_candidate_path_counts_as_installed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from app.setup import diagnostics

    binary = tmp_path / "ffmpeg"
    binary.write_bytes(b"ffmpeg")
    diagnostics._VERIFY_CACHE.pop("ffmpeg", None)
    monkeypatch.setattr(diagnostics.shutil, "which", lambda _: None)
    monkeypatch.setattr(diagnostics, "ffmpeg_search_paths", lambda: [str(binary)])
    monkeypatch.setattr(diagnostics, "_run_version", lambda _cmd: (True, "ffmpeg version test", ""))
    result = diagnostics.verify_component("ffmpeg")
    assert result.healthy is True
    assert result.path == str(binary)


def test_remove_protects_essentials_and_deletes_only_a_managed_file(setup_data_dir: Path) -> None:
    managed = setup_data_dir / "models" / "extra.safetensors"
    shared = setup_data_dir / "shared.bin"
    managed.parent.mkdir()
    managed.write_bytes(b"weight")
    shared.write_bytes(b"shared")
    from app.setup.state import update_state

    update_state(
        lambda latest: latest.__setitem__(
            "status",
            {
                "extra_model": {"path": str(managed)},
                "shared_model": {"path": str(shared)},
            },
        )
    )
    assert remove_component("python")["status"] == "protected"
    assert remove_component("ffmpeg")["status"] == "protected"
    save_installation_profile("local")
    assert remove_component("zimage_models")["status"] == "protected"
    assert remove_component("extra_model")["status"] == "confirmation_required"
    assert managed.exists()
    deleted = remove_component("extra_model", confirm_delete=True)
    assert deleted["status"] == "removed"
    assert deleted["deleted"] is True
    assert not managed.exists()
    untouched = remove_component("shared_model", confirm_delete=True)
    assert untouched["deleted"] is False
    assert shared.read_bytes() == b"shared"


def test_local_ai_requirement_follows_the_installation_profile() -> None:
    assert local_ai_required("api") is False
    assert local_ai_required("local") is True
    assert local_ai_required("hybrid", {"selected_local_models": []}) is False
    assert local_ai_required("hybrid", {"selected_local_models": ["zimage_models"]}) is True
    absent = local_ai_contract("api", configured=False, daemon_online=False, model_ready=False)
    assert absent["result"] == "NOT_REQUIRED"
    missing = local_ai_contract("local", configured=False, daemon_online=False, model_ready=False)
    assert missing["result"] == "NOT_CONFIGURED"
    ready = local_ai_contract("local", configured=True, daemon_online=True, model_ready=True)
    assert ready["result"] == "PASS"
    down = local_ai_contract("local", configured=True, daemon_online=False, model_ready=False)
    assert down["result"] == "FAIL"
