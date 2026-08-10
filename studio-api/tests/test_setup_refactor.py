from __future__ import annotations

import json
import time
from pathlib import Path

import pytest


@pytest.fixture()
def setup_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.config import settings
    from app.setup import diagnostics as setup_diagnostics
    from app.setup import status as setup_status

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    # Keep path helpers inside the temp tree instead of the developer's Comfy Shared folder.
    monkeypatch.setattr(settings, "comfy_input_dir", tmp_path / "missing-comfy" / "input")
    if hasattr(settings, "comfy_models_dir"):
        monkeypatch.setattr(settings, "comfy_models_dir", None)
    setup_status._STATUS_CACHE = None
    setup_diagnostics._VERIFY_CACHE.clear()
    return tmp_path


def test_status_uses_only_canonical_states_and_requires_verification(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.setup import status
    from app.setup.diagnostics import Verification

    def fake_verify(component_id: str, state=None):
        if component_id == "python":
            return Verification(True, False, None, "ok", "python", "3.11")
        return Verification(False, True, "missing", "missing", recommendation="install")

    monkeypatch.setattr(status, "verify_component", fake_verify)
    result = status.build_status()
    states = {item["component_id"]: item["status"] for item in result["components"]}

    assert states["python"] == "ready"
    assert states["ltx_checkpoint"] == "not_installed"
    assert set(states.values()) <= status.CANONICAL_STATUSES
    assert result["overall_status"] == "additional_setup_required"
    ready = next(item for item in result["components"] if item["component_id"] == "python")
    assert ready["primary_action"] is None


def test_ltx_ready_only_when_required_checkpoint_exists(setup_data_dir: Path) -> None:
    from app.config import settings
    from app.setup.diagnostics import verify_component
    from app.setup.state import save_state

    model_dir = setup_data_dir / "models"
    model_dir.mkdir()
    save_state({"components": {}, "model_locations": {"ltx_checkpoint": str(model_dir)}})
    assert verify_component("ltx_checkpoint").healthy is False

    checkpoint = model_dir / settings.ltx_checkpoint
    checkpoint.write_bytes(b"verified-model-content")
    result = verify_component("ltx_checkpoint")
    assert result.healthy is True
    assert result.path == str(checkpoint)


def test_diagnostics_returns_one_recommendation(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.setup import diagnostics

    monkeypatch.setattr(diagnostics.shutil, "which", lambda _: None)
    result = diagnostics.diagnose("ffmpeg")

    assert result["healthy"] is False
    assert result["issue_code"] == "executable_missing"
    assert result["recommendation"] == "install"
    assert result["requires_user_interaction"] is True


def test_prepare_plan_excludes_optional_components(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.setup import orchestrator

    component_statuses = []
    for component in orchestrator.COMPONENTS:
        component_statuses.append(
            {
                "component_id": component.id,
                "status": "not_installed" if component.id in ("ffmpeg", "ollama") else "ready",
            }
        )
    monkeypatch.setattr(
        orchestrator,
        "build_status",
        lambda: {"components": component_statuses},
    )
    monkeypatch.setattr(
        orchestrator,
        "diagnose",
        lambda component_id: {
            "recommendation": "install",
            "summary": "missing",
            "requires_user_interaction": True,
        },
    )

    plan = orchestrator.get_prepare_plan()
    planned = {item["component_id"] for item in plan["required_actions"]}
    assert planned == {"ffmpeg"}
    assert "ollama" in plan["skipped_optional_component_ids"]
    assert all(not item.startswith("pack_") for item in planned)


def test_operation_checkpoint_and_global_lock() -> None:
    from app.setup.operations import OperationRegistry

    registry = OperationRegistry()
    operation = registry.create("prepare", ["ffmpeg"], global_operation=True)
    with pytest.raises(RuntimeError):
        registry.create("prepare", ["python"], global_operation=True)

    paused = registry.pause(
        operation["operation_id"],
        {"component_id": "ffmpeg", "summary": "Install FFmpeg"},
    )
    assert paused["status"] == "awaiting_checkpoint"
    checkpoint_id = paused["checkpoint"]["checkpoint_id"]

    registry.respond(operation["operation_id"], {"checkpoint_id": checkpoint_id, "accepted": True})
    resumed = registry.snapshot(operation["operation_id"])
    assert resumed["status"] == "running"
    assert resumed["checkpoint"] is None


def test_status_exposes_active_operation(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.setup import operations, status
    from app.setup.diagnostics import Verification
    from app.setup.operations import OperationRegistry

    local_registry = OperationRegistry()
    operation = local_registry.create(
        "prepare", ["ltx_checkpoint"], global_operation=True
    )
    local_registry.update(
        operation["operation_id"],
        status="running",
        phase="installing",
        stage="Preparing LTX Video Checkpoint",
        progress=0.25,
    )
    monkeypatch.setattr(operations, "registry", local_registry)
    monkeypatch.setattr(
        status,
        "verify_component",
        lambda component_id, state=None: Verification(
            component_id != "ltx_checkpoint",
            component_id == "ltx_checkpoint",
            None if component_id != "ltx_checkpoint" else "missing",
            "checked",
        ),
    )

    result = status.build_status(persist=False)
    ltx = next(
        item
        for item in result["components"]
        if item["component_id"] == "ltx_checkpoint"
    )

    assert result["active_operation"]["operation_id"] == operation["operation_id"]
    assert ltx["operation_id"] == operation["operation_id"]
    assert ltx["stage"] == "Preparing LTX Video Checkpoint"
    assert ltx["status"] == "installing"


def test_status_reuses_short_cache_when_idle(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.setup import status
    from app.setup.diagnostics import Verification

    calls = {"count": 0}

    def fake_verify(component_id: str, state=None):
        calls["count"] += 1
        return Verification(True, False, None, "ok", version="1")

    monkeypatch.setattr(status, "verify_component", fake_verify)

    first = status.build_status()
    first_calls = calls["count"]
    second = status.build_status()

    assert first["overall_status"] == "ready"
    assert second["overall_status"] == "ready"
    assert first_calls > 0
    assert calls["count"] == first_calls


def test_model_checkpoint_requires_license_and_auto_verifies(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings
    from app.setup import orchestrator
    from app.setup.diagnostics import verify_component
    from app.setup.operations import OperationRegistry

    local_registry = OperationRegistry()
    monkeypatch.setattr(orchestrator, "registry", local_registry)
    monkeypatch.setattr(
        orchestrator,
        "build_status",
        lambda: {"overall_status": "ready", "components": []},
    )
    operation = local_registry.create(
        "component_action", ["ltx_checkpoint"]
    )
    operation_id = operation["operation_id"]
    checkpoint = local_registry.pause(
        operation_id,
        {
            "type": "model_path",
            "component_id": "ltx_checkpoint",
            "summary": "Choose the LTX checkpoint.",
            "required_fields": ["path", "license_accepted"],
            "requires_license_acceptance": True,
        },
    )["checkpoint"]
    orchestrator._CONTEXTS[operation_id] = {
        "actions": [
            {
                "component_id": "ltx_checkpoint",
                "action": "install",
                "phase": "configuring",
            }
        ],
        "index": 0,
        "failures": [],
        "preflight": False,
    }

    model = setup_data_dir / settings.ltx_checkpoint
    model.write_bytes(b"verified-model-content")

    with pytest.raises(ValueError, match="license_accepted"):
        orchestrator.respond_to_checkpoint(
            operation_id,
            {
                "checkpoint_id": checkpoint["checkpoint_id"],
                "path": str(model),
            },
        )

    orchestrator.respond_to_checkpoint(
        operation_id,
        {
            "checkpoint_id": checkpoint["checkpoint_id"],
            "path": str(model),
            "license_accepted": True,
        },
    )
    deadline = time.monotonic() + 2
    snapshot = local_registry.snapshot(operation_id)
    while snapshot["status"] not in {"completed", "failed"} and time.monotonic() < deadline:
        time.sleep(0.01)
        snapshot = local_registry.snapshot(operation_id)

    assert snapshot["status"] == "completed"
    assert verify_component("ltx_checkpoint").healthy is True


def test_legacy_link_auto_verifies_without_false_ready(setup_data_dir: Path) -> None:
    from app.setup_wizard import approve_install, load_setup_state

    empty_model_dir = setup_data_dir / "empty-model-directory"
    empty_model_dir.mkdir()
    result = approve_install(
        "ltx_checkpoint", action="link", path=str(empty_model_dir)
    )

    # Compatibility status remains, while the additive verification is honest.
    assert result["status"] == "installed"
    assert result["verified"] is False
    assert result["verification"]["issue_code"] == "required_model_missing"
    state = load_setup_state()
    assert state["model_locations"]["ltx_checkpoint"] == str(empty_model_dir)


def test_atomic_state_preserves_legacy_fields(setup_data_dir: Path) -> None:
    from app.setup.state import load_state, save_state

    saved = save_state(
        {
            "components": {"ffmpeg": {"status": "installed"}},
            "model_locations": {"ltx_checkpoint": "D:/models"},
            "custom_legacy_field": {"keep": True},
        }
    )
    loaded = load_state()

    assert saved["schema_version"] >= 3
    assert loaded["components"]["ffmpeg"]["status"] == "installed"
    assert loaded["model_locations"]["ltx_checkpoint"] == "D:/models"
    assert loaded["custom_legacy_field"] == {"keep": True}
    assert json.loads((setup_data_dir / "setup_state.json").read_text(encoding="utf-8"))
    assert not list(setup_data_dir.glob("*.tmp"))


def test_status_refresh_does_not_overwrite_concurrent_path(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.setup import status
    from app.setup.diagnostics import Verification
    from app.setup.state import load_state, update_state

    selected = setup_data_dir / "selected-models"
    selected.mkdir()
    wrote_path = False

    def fake_verify(component_id: str, state=None):
        nonlocal wrote_path
        if not wrote_path:
            wrote_path = True
            update_state(
                lambda latest: latest.setdefault("model_locations", {}).__setitem__(
                    "pack_essential_photoreal", str(selected)
                )
            )
        return Verification(
            component_id == "python",
            component_id != "python",
            None if component_id == "python" else "missing",
            "checked",
        )

    monkeypatch.setattr(status, "verify_component", fake_verify)
    status.build_status()

    assert (
        load_state()["model_locations"]["pack_essential_photoreal"]
        == str(selected)
    )


def test_path_checkpoint_includes_suggested_path(setup_data_dir: Path) -> None:
    from app.setup.orchestrator import _checkpoint_for
    from app.setup.paths import suggested_install_path

    checkpoint = _checkpoint_for("pack_essential_photoreal", "link_existing")
    assert checkpoint["type"] == "path"
    assert checkpoint["workflow"] == "link_existing"
    assert checkpoint["suggested_path"] == suggested_install_path("pack_essential_photoreal")
    assert checkpoint["path_selector"] == "directory"
    assert not Path(checkpoint["suggested_path"]).exists()

    install_ck = _checkpoint_for("pack_essential_photoreal", "install")
    assert install_ck["workflow"] == "download_install"
    assert "empty folders are not accepted" not in install_ck["summary"].lower()


def test_status_does_not_auto_bind_asset_packs(setup_data_dir: Path) -> None:
    from app.setup.status import build_status
    from app.setup.state import load_state

    status = build_status()
    state = load_state()
    assert "pack_essential_photoreal" not in state.get("model_locations", {})
    pack = next(
        item for item in status["components"] if item["component_id"] == "pack_essential_photoreal"
    )
    assert pack["status"] == "source_pending"
    assert pack["issue_code"] in {
        "download_source_missing",
        "pack_provider_not_configured",
        "pack_release_not_found",
        "source_not_published",
    }
    assert pack["installed_bytes"] == 0
    assert pack["install_disabled"] is True


def test_status_refreshes_stale_path_not_configured_diagnostic(setup_data_dir: Path) -> None:
    from app.setup.state import save_state
    from app.setup.status import build_status

    pack_path = setup_data_dir / "models" / "creative_assets" / "essential_photoreal"
    pack_path.mkdir(parents=True)
    save_state(
        {
            "model_locations": {"pack_essential_photoreal": str(pack_path)},
            "status": {
                "pack_essential_photoreal": {
                    "status": "not_installed",
                    "installation_path": None,
                    "diagnostic": {
                        "component_id": "pack_essential_photoreal",
                        "healthy": False,
                        "issue_code": "path_not_configured",
                        "summary": "Essential Photoreal Pack has no configured path.",
                        "recommendation": "configure",
                    },
                }
            },
        }
    )

    status = build_status()
    pack = next(
        item for item in status["components"] if item["component_id"] == "pack_essential_photoreal"
    )
    assert pack["installation_path"] == str(pack_path)
    assert pack["issue_code"] == "required_files_missing"
    assert pack["installed_bytes"] == 0
    assert pack["estimated_installed_bytes"] > 0


def test_missing_asset_pack_path_is_not_recreated(setup_data_dir: Path) -> None:
    from app.setup.paths import ensure_configured_paths, suggested_install_path
    from app.setup.state import load_state, save_state

    suggested = Path(suggested_install_path("pack_essential_anime"))
    save_state({"model_locations": {"pack_essential_anime": str(suggested)}})
    if suggested.exists():
        suggested.rmdir()
    assert not suggested.exists()

    state = load_state()
    ensure_configured_paths(state)
    assert not suggested.exists()


def test_persist_path_accepts_empty_install_destination(setup_data_dir: Path) -> None:
    from app.setup.orchestrator import _persist_path
    from app.setup.state import load_state

    target = setup_data_dir / "models" / "creative_assets" / "auto_created_pack"
    target.mkdir(parents=True)
    _persist_path("pack_essential_cinematic", str(target), workflow="download_install")
    assert load_state()["model_locations"]["pack_essential_cinematic"] == str(target)

    missing = setup_data_dir / "models" / "creative_assets" / "creatable_pack"
    _persist_path("pack_essential_anime", str(missing), workflow="download_install")
    assert load_state()["model_locations"]["pack_essential_anime"] == str(missing)
    # Creatable destinations are recorded without pre-creating an empty pack root.
    assert not missing.exists()


def test_persist_path_accepts_populated_pack_directory(setup_data_dir: Path) -> None:
    from app.setup.orchestrator import _persist_path
    from app.setup.state import load_state

    target = setup_data_dir / "models" / "creative_assets" / "populated_pack"
    target.mkdir(parents=True)
    (target / "pack.json").write_text(
        '{"id":"pack_essential_photoreal","version":"1.0.0"}',
        encoding="utf-8",
    )

    _persist_path("pack_essential_photoreal", str(target), workflow="download_install")

    assert load_state()["model_locations"]["pack_essential_photoreal"] == str(target)


def test_missing_source_install_fails_without_creating_directory(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.setup import orchestrator
    from app.setup.operations import OperationRegistry
    from app.setup.paths import suggested_install_path
    from app.setup.status import build_status

    local_registry = OperationRegistry()
    monkeypatch.setattr(orchestrator, "registry", local_registry)

    suggested = Path(suggested_install_path("pack_essential_anime"))
    assert not suggested.exists()

    status = build_status()
    pack = next(
        item for item in status["components"] if item["component_id"] == "pack_essential_anime"
    )
    assert pack["status"] == "source_pending"
    assert pack["installed_bytes"] == 0

    snapshot = orchestrator.execute_recommended_action("pack_essential_anime")
    assert snapshot["status"] == "failed"
    assert snapshot["error"] in {
        "download_source_missing",
        "pack_provider_not_configured",
        "pack_release_not_found",
        "source_not_published",
    }
    assert not suggested.exists()


def test_populated_pack_link_existing_marks_ready(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.setup import orchestrator
    from app.setup.operations import OperationRegistry
    from app.setup.diagnostics import verify_component

    local_registry = OperationRegistry()
    monkeypatch.setattr(orchestrator, "registry", local_registry)
    monkeypatch.setattr(
        orchestrator,
        "build_status",
        lambda: {"overall_status": "ready", "components": []},
    )

    pack_dir = setup_data_dir / "models" / "creative_assets" / "ready_anime"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.json").write_text(
        '{"id":"pack_essential_anime","version":"1.0.0"}',
        encoding="utf-8",
    )

    snapshot = orchestrator.start_link_existing_pack("pack_essential_anime")
    operation_id = snapshot["operation_id"]
    deadline = time.monotonic() + 2
    while snapshot["status"] != "awaiting_checkpoint" and time.monotonic() < deadline:
        time.sleep(0.01)
        snapshot = local_registry.snapshot(operation_id)
    assert snapshot["status"] == "awaiting_checkpoint"
    checkpoint = snapshot["checkpoint"]

    orchestrator.respond_to_checkpoint(
        operation_id,
        {
            "checkpoint_id": checkpoint["checkpoint_id"],
            "path": str(pack_dir),
        },
    )
    deadline = time.monotonic() + 2
    snapshot = local_registry.snapshot(operation_id)
    while snapshot["status"] not in {"completed", "failed"} and time.monotonic() < deadline:
        time.sleep(0.01)
        snapshot = local_registry.snapshot(operation_id)

    assert snapshot["status"] == "completed"
    assert verify_component("pack_essential_anime").healthy is True


def test_status_exposes_install_kind_and_path_selector(setup_data_dir: Path) -> None:
    from app.setup.status import build_status

    status = build_status()
    by_id = {item["component_id"]: item for item in status["components"]}
    assert by_id["ltx_checkpoint"]["install_kind"] == "path_link"
    assert by_id["ltx_checkpoint"]["path_selector"] == "file"
    assert by_id["pack_essential_photoreal"]["install_kind"] == "asset_pack"
    assert by_id["pack_essential_photoreal"]["path_selector"] == "directory"
    assert by_id["ffmpeg"]["path_selector"] is None


def test_approve_install_creates_missing_directory(setup_data_dir: Path) -> None:
    from app.setup_wizard import approve_install
    from app.setup.state import load_state

    target = setup_data_dir / "models" / "creative_assets" / "legacy_link"
    assert not target.exists()
    result = approve_install("pack_essential_anime", action="link", path=str(target))

    assert result["status"] == "installed"
    assert target.exists()
    assert load_state()["model_locations"]["pack_essential_anime"] == str(target)


def test_default_models_root_creates_comfy_shared_models(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings
    from app.setup.paths import default_models_root

    comfy_root = setup_data_dir / "ComfyUI-Shared"
    comfy_input = comfy_root / "input"
    comfy_input.mkdir(parents=True)
    monkeypatch.setattr(settings, "comfy_input_dir", comfy_input)

    models = default_models_root()
    assert models == comfy_root / "models"
    assert models.exists()


def test_checkpoint_cancel_stops_operation(setup_data_dir: Path) -> None:
    from app.setup import orchestrator
    from app.setup.operations import OperationRegistry

    local_registry = OperationRegistry()
    operation = local_registry.create("prepare", ["ffmpeg"], global_operation=True)
    operation_id = operation["operation_id"]
    paused = local_registry.pause(
        operation_id,
        {"type": "path", "component_id": "ffmpeg", "summary": "Choose path", "required_fields": ["path"]},
    )
    orchestrator.registry = local_registry
    orchestrator._CONTEXTS[operation_id] = {
        "actions": [{"component_id": "ffmpeg", "action": "install"}],
        "index": 0,
        "failures": [],
        "preflight": False,
    }

    result = orchestrator.respond_to_checkpoint(
        operation_id,
        {"checkpoint_id": paused["checkpoint"]["checkpoint_id"], "cancelled": True},
    )
    assert result["status"] == "cancelled"
    assert operation_id not in orchestrator._CONTEXTS


def test_new_setup_endpoints(client, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.routers import extra

    monkeypatch.setattr(extra, "get_setup_status", lambda: {"overall_status": "ready", "components": []})
    monkeypatch.setattr(extra, "get_prepare_plan", lambda: {"required_actions": []})
    monkeypatch.setattr(
        extra, "diagnose_component", lambda component_id: {"component_id": component_id, "recommendation": "none"}
    )
    monkeypatch.setattr(
        extra,
        "dismiss_update",
        lambda component_id: {"component_id": component_id, "dismissed": True},
    )
    monkeypatch.setattr(
        extra,
        "browse_setup_path",
        lambda **kwargs: {"path": r"C:\Models", "cancelled": False},
    )

    assert client.get("/api/setup/status").json()["overall_status"] == "ready"
    assert client.post("/api/setup/prepare/plan").json()["required_actions"] == []
    assert client.post("/api/setup/components/ffmpeg/diagnostics").status_code == 200
    assert client.post("/api/setup/components/ffmpeg/update/later").json()["dismissed"] is True
    suggested = client.get("/api/setup/components/pack_essential_photoreal/suggested-path")
    assert suggested.status_code == 200
    assert suggested.json()["path_selector"] == "directory"
    assert client.post("/api/setup/browse-path", json={"component_id": "pack_essential_photoreal"}).json()["path"] == r"C:\Models"


def test_status_exposes_first_class_ai_guided_groups(setup_data_dir: Path) -> None:
    from app.setup.status import build_status

    status = build_status()
    by_id = {item["id"]: item for item in status["components"]}

    assert by_id["ace_step_local"]["group"] == "Music"
    assert by_id["ace_step_local"]["surfaceGroups"] == ["Music"]

    assert by_id["longcat-video-avatar-1-5-local"]["group"] == "Avatar"
    assert by_id["longcat-video-avatar-1-5-local"]["surfaceGroups"] == ["Avatar", "Motion"]

    assert by_id["fal_key"]["group"] == "API Providers"
    assert by_id["fal_key"]["subgroup"] == "Credentials"
    assert by_id["fal_key"]["surfaceGroups"] == ["API Providers"]

    assert by_id["pack_essential_photoreal"]["group"] == "Creative Packs"
    assert by_id["pack_essential_photoreal"]["subgroup"] == "Essential Packs"
    assert by_id["pack_essential_photoreal"]["surfaceGroups"] == ["Creative Packs"]
