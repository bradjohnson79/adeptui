"""Capability registry, probes, workflow readiness, and the honesty rules that guard them.

The rules under test are the ones that make the registry worth trusting:

* the status vocabulary is fixed and complete,
* a mock provider can never produce a `locally_verified` claim,
* an absent feature reports `not_implemented` rather than a failure,
* a missing dependency downgrades everything that needs it,
* nothing is queued against a ComfyUI whose required nodes are provably absent,
* and no capability payload leaks a secret or a stack trace.
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_DOC = REPO_ROOT / "docs" / "audit" / "ADEPT_PRODUCTION_CAPABILITY_MATRIX.md"

#: The vocabulary is API surface. Adding or renaming a value is a breaking change for the
#: Health Dashboard, the Setup Wizard, and Co-Director M2.2.
EXPECTED_STATUSES = {
    "not_implemented",
    "ui_only",
    "backend_only",
    "partially_wired",
    "mock_verified",
    "locally_verified",
    "production_ready",
    "blocked",
    "degraded",
    "not_configured",
    "unknown",
    "deferred_version_1_2",
}


@pytest.fixture(autouse=True)
def _clear_capability_cache():
    from app.capabilities import service

    service.invalidate_cache()
    yield
    service.invalidate_cache()


def _create_project(client, name: str = "Capability Project") -> str:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()["id"]


def _snapshot(client, project_id: str | None = None, *, refresh: bool = False) -> dict:
    url = "/api/capabilities" if project_id is None else f"/api/projects/{project_id}/capabilities"
    params = {"refresh": "true"} if refresh else {}
    res = client.get(url, params=params)
    assert res.status_code == 200
    return res.json()


def _by_id(snapshot: dict) -> dict[str, dict]:
    return {item["id"]: item for item in snapshot["capabilities"]}


# --------------------------------------------------------------------------
# vocabulary + registry integrity
# --------------------------------------------------------------------------


def test_status_vocabulary_is_exactly_the_agreed_set() -> None:
    from app.capabilities.models import CapabilityStatus

    assert {status.value for status in CapabilityStatus} == EXPECTED_STATUSES


def test_registry_has_unique_ids_and_no_dangling_dependencies() -> None:
    from app.capabilities.registry import CAPABILITIES, BY_ID, validate_registry

    validate_registry()
    assert len(BY_ID) == len(CAPABILITIES)
    for definition in CAPABILITIES:
        for dependency in definition.dependencies:
            assert dependency in BY_ID
        assert definition.id == definition.id.strip().lower()
        assert definition.summary or definition.baseline_reason


def test_unproven_baselines_explain_themselves() -> None:
    """A capability that is not verified must say why, so the matrix is never a bare claim."""
    from app.capabilities.models import UNPROVEN_STATUSES
    from app.capabilities.registry import CAPABILITIES

    for definition in CAPABILITIES:
        if definition.baseline_status in UNPROVEN_STATUSES:
            assert definition.baseline_reason, f"{definition.id} lacks a baseline_reason"


def test_every_service_ref_resolves_to_real_code() -> None:
    """A `service_ref` naming a module that does not exist would be the exact dishonesty
    this registry is meant to remove."""
    import importlib

    from app.capabilities.registry import CAPABILITIES

    for definition in CAPABILITIES:
        if not definition.service_ref:
            continue
        module_path, _, attribute = definition.service_ref.partition(":")
        module = importlib.import_module(module_path)
        target: object = module
        for part in attribute.split("."):
            assert hasattr(target, part), f"{definition.id} -> {definition.service_ref} is dangling"
            target = getattr(target, part)


def test_capability_matrix_doc_lists_every_capability() -> None:
    assert MATRIX_DOC.is_file(), f"missing {MATRIX_DOC}"
    text = MATRIX_DOC.read_text(encoding="utf-8")

    from app.capabilities.registry import CAPABILITIES

    missing = [definition.id for definition in CAPABILITIES if f"`{definition.id}`" not in text]
    assert not missing, f"capability matrix doc is out of sync, missing: {missing}"


def test_dependency_graph_is_acyclic() -> None:
    from app.capabilities.registry import BY_ID, CAPABILITIES

    def walk(capability_id: str, seen: tuple[str, ...]) -> None:
        assert capability_id not in seen, f"dependency cycle through {capability_id}: {seen}"
        for dependency in BY_ID[capability_id].dependencies:
            walk(dependency, seen + (capability_id,))

    for definition in CAPABILITIES:
        walk(definition.id, ())


# --------------------------------------------------------------------------
# HTTP surface
# --------------------------------------------------------------------------


def test_capabilities_endpoint_returns_a_complete_snapshot(client) -> None:
    from app.capabilities.registry import CAPABILITIES

    snapshot = _snapshot(client)
    assert snapshot["schemaVersion"] == 1
    assert snapshot["correlationId"]
    assert len(snapshot["capabilities"]) == len(CAPABILITIES)
    assert sum(snapshot["counts"].values()) == len(CAPABILITIES)
    assert set(snapshot["counts"]).issubset(EXPECTED_STATUSES)
    for item in snapshot["capabilities"]:
        assert item["status"] in EXPECTED_STATUSES
        assert item["lastCheckedAt"]


def test_callable_list_only_contains_available_capabilities(client) -> None:
    snapshot = _snapshot(client)
    available = {item["id"] for item in snapshot["capabilities"] if item["available"]}
    assert set(snapshot["callable"]) == available

    usable = {"locally_verified", "production_ready", "degraded"}
    for item in snapshot["capabilities"]:
        if item["available"]:
            assert item["status"] in usable


def test_blockers_carry_a_reason_and_an_action(client) -> None:
    snapshot = _snapshot(client)
    blocking = {"blocked", "not_configured"}
    for item in snapshot["capabilities"]:
        if item["status"] in blocking:
            assert item["reasonCode"], f"{item['id']} is blocked without a reason code"
            assert item["message"], f"{item['id']} is blocked without a message"
            assert item["recommendedAction"], f"{item['id']} is blocked without an action"
    assert {item["capabilityId"] for item in snapshot["blockers"]} == {
        item["id"] for item in snapshot["capabilities"] if item["status"] in blocking
    }


def test_single_capability_read_matches_the_snapshot(client) -> None:
    snapshot = _by_id(_snapshot(client))
    res = client.get("/api/capabilities/storage.database")
    assert res.status_code == 200
    assert res.json()["status"] == snapshot["storage.database"]["status"]


def test_unknown_capability_returns_structured_404(client) -> None:
    res = client.get("/api/capabilities/does.not.exist")
    assert res.status_code == 404
    detail = res.json()["detail"]
    assert detail["code"] == "CAPABILITY_NOT_FOUND"
    assert detail["recoverable"] is False


def test_refresh_reprobes_without_mutating_anything(client) -> None:
    before = client.get("/api/setup/status")
    assert before.status_code == 200

    res = client.post("/api/capabilities/refresh")
    assert res.status_code == 200
    assert res.json()["capabilities"]

    after = client.get("/api/setup/status")
    assert after.status_code == 200
    assert [item["component_id"] for item in after.json()["components"]] == [
        item["component_id"] for item in before.json()["components"]
    ]


def test_project_scope_reports_missing_project_as_blocked(client) -> None:
    # Asking the dashboard question ("what can this studio do, in this project's context?")
    # still answers, and answers honestly: project-scoped entries are blocked.
    res = client.get(
        "/api/capabilities", params={"projectId": "no-such-project", "refresh": "true"}
    )
    assert res.status_code == 200
    capabilities = _by_id(res.json())
    assert capabilities["project.scenes.read"]["status"] == "blocked"
    assert capabilities["project.scenes.read"]["reasonCode"] == "PROJECT_NOT_FOUND"
    # Global capabilities are unaffected by a bad project id.
    assert capabilities["storage.database"]["status"] == "locally_verified"


def test_project_capability_route_404s_for_an_unknown_project(client) -> None:
    """Asking for *one project's* capabilities by id is a lookup, not a dashboard read.

    Returning a full snapshot of blockers for a typo'd id would make a healthy studio look
    broken, so this route 404s instead.
    """
    res = client.get("/api/projects/no-such-project/capabilities")
    assert res.status_code == 404
    detail = res.json()["detail"]
    assert detail["code"] == "PROJECT_NOT_FOUND"
    assert detail["recommendedAction"] == "open_project"


def test_project_scope_keeps_scene_capabilities_usable_for_a_real_project(client) -> None:
    project_id = _create_project(client)
    capabilities = _by_id(_snapshot(client, project_id))
    for capability_id in (
        "project.read",
        "project.update",
        "project.scenes.read",
        "project.scenes.create",
        "project.scenes.update",
        "project.scenes.delete",
    ):
        assert capabilities[capability_id]["status"] == "locally_verified", capability_id
        assert capabilities[capability_id]["available"] is True


# --------------------------------------------------------------------------
# honesty rules
# --------------------------------------------------------------------------


def test_absent_features_are_reported_as_not_implemented(client) -> None:
    capabilities = _by_id(_snapshot(client))
    for capability_id in (
        "project.scenes.reorder",
        "references.remove",
        "references.attach.scene",
        "codirector.tools",
    ):
        item = capabilities[capability_id]
        assert item["status"] == "not_implemented", capability_id
        assert item["available"] is False
        assert item["reasonCode"] == "CAPABILITY_NOT_IMPLEMENTED"
        assert item["message"]


def test_frontend_only_state_is_reported_as_ui_only(client) -> None:
    item = _by_id(_snapshot(client))["project.scenes.active"]
    assert item["status"] == "ui_only"
    assert item["available"] is False


def test_mock_provider_never_produces_a_local_verification(client, monkeypatch) -> None:
    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")

    capabilities = _by_id(_snapshot(client, refresh=True))
    assert capabilities["codirector.provider"]["status"] == "mock_verified"
    assert capabilities["codirector.provider"]["available"] is False
    assert capabilities["codirector.chat"]["status"] != "locally_verified"


def test_unreachable_comfy_blocks_comfy_and_generation(client, monkeypatch) -> None:
    from unittest.mock import AsyncMock

    from app.comfy_client import comfy

    monkeypatch.setattr(comfy, "health", AsyncMock(side_effect=RuntimeError("connection refused")))

    capabilities = _by_id(_snapshot(client))
    for capability_id in ("comfyui.health", "comfyui.queue", "generation.image.queue", "generation.video.queue"):
        item = capabilities[capability_id]
        assert item["status"] in ("blocked", "not_configured", "unknown"), capability_id
        assert item["available"] is False, capability_id


def test_capability_payloads_never_leak_secrets_or_traces(client) -> None:
    import json

    snapshot = _snapshot(client)
    serialized = json.dumps(snapshot).lower()
    for needle in ("traceback", "file \"", 'password"', "api_key", "authorization"):
        assert needle not in serialized, f"capability payload leaked {needle!r}"


def test_one_broken_probe_does_not_take_out_the_registry(client, monkeypatch) -> None:
    from app.source_manager import registry as source_registry

    def _boom() -> dict:
        raise RuntimeError("overview exploded")

    monkeypatch.setattr(source_registry, "overview_payload", _boom)

    snapshot = _snapshot(client, refresh=True)
    assert "source_manager_probe_failed" in snapshot["probeWarnings"]
    assert _by_id(snapshot)["source_manager.read"]["status"] in ("degraded", "unknown")
    # Unrelated capabilities are still answered.
    assert _by_id(snapshot)["storage.database"]["status"] == "locally_verified"


# --------------------------------------------------------------------------
# workflows + models
# --------------------------------------------------------------------------


def test_workflow_discovery_lists_registered_builders(client) -> None:
    res = client.get("/api/workflows")
    assert res.status_code == 200
    workflows = res.json()["workflows"]
    assert workflows
    for item in workflows:
        assert item["id"]
        assert item["modality"] in ("image", "video", "audio", "other")
        assert isinstance(item["requiredNodeTypes"], list)


def test_workflow_readiness_reports_missing_nodes_with_an_action() -> None:
    from app.workflows.readiness import workflow_readiness

    readiness = workflow_readiness("ltx.scene", node_types=set(), model_states={"ltx_checkpoint": True})
    assert readiness["status"] == "blocked"
    assert readiness["reasonCode"] == "WORKFLOW_MISSING_EXTENSIONS"
    assert readiness["missingExtensions"]
    assert readiness["recommendedAction"] == "install_comfyui_extensions"


def test_workflow_readiness_reports_missing_models_with_component_ids() -> None:
    from app.workflows.readiness import workflow_readiness

    nodes = set(_required_nodes("ltx.scene"))
    readiness = workflow_readiness("ltx.scene", node_types=nodes, model_states={"ltx_checkpoint": False})
    assert readiness["status"] == "blocked"
    assert readiness["reasonCode"] == "WORKFLOW_MISSING_MODELS"
    assert [item["componentId"] for item in readiness["missingModels"]] == ["ltx_checkpoint"]
    assert readiness["recommendedAction"] == "open_source_manager"


def test_workflow_readiness_is_ready_when_nodes_and_models_are_present() -> None:
    from app.workflows.readiness import workflow_readiness

    nodes = set(_required_nodes("ltx.scene"))
    readiness = workflow_readiness("ltx.scene", node_types=nodes, model_states={"ltx_checkpoint": True})
    assert readiness["status"] == "ready"
    assert readiness["reasonCode"] is None
    assert readiness["missingExtensions"] == []


def test_latentsync_readiness_accepts_d_latentsync_alias() -> None:
    """hay86 registers D_LatentSyncNode; legacy LatentSyncNode must not be required alongside it."""
    from app.workflows.readiness import workflow_readiness

    nodes = {"D_LatentSyncNode", "PreviewAny", "VHS_VideoCombine"}
    readiness = workflow_readiness("lipsync.latentsync", node_types=nodes, model_states={})
    assert "LatentSyncNode" not in readiness["missingExtensions"]
    assert readiness["missingExtensions"] == []
    assert readiness["status"] in ("ready", "unknown")  # unknown if models unverified by design


def test_workflow_readiness_is_unknown_without_a_node_catalogue() -> None:
    from app.workflows.readiness import workflow_readiness

    readiness = workflow_readiness("ltx.scene", node_types=None, model_states={"ltx_checkpoint": True})
    assert readiness["status"] == "unknown"
    assert readiness["reasonCode"] == "WORKFLOW_READINESS_UNKNOWN"
    assert readiness["nodeCatalogAvailable"] is False


def test_unknown_workflow_readiness_returns_structured_404(client) -> None:
    res = client.get("/api/workflows/not-a-workflow/readiness")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "WORKFLOW_NOT_FOUND"


def _required_nodes(workflow_id: str) -> tuple[str, ...]:
    from app.workflows.registry import DEFAULT_WORKFLOW_REGISTRY

    return tuple(DEFAULT_WORKFLOW_REGISTRY.get(workflow_id).compatibility.required_node_types)


def test_graph_guard_refuses_provably_missing_node_types() -> None:
    from app.capabilities.errors import CapabilityError
    from app.workflows.readiness import assert_graph_runnable

    graph = {"1": {"class_type": "MadeUpLoader", "inputs": {}}}
    with pytest.raises(CapabilityError) as err:
        assert_graph_runnable(graph, {"CheckpointLoaderSimple"})
    assert err.value.code == "EXTENSION_MISSING"
    assert "MadeUpLoader" in err.value.message


def test_graph_guard_is_permissive_when_the_catalogue_is_unreadable() -> None:
    from app.workflows.readiness import assert_graph_runnable

    graph = {"1": {"class_type": "MadeUpLoader", "inputs": {}}}
    # Unknown is not the same as invalid: a slow /object_info must not break a working install.
    assert_graph_runnable(graph, None)


def test_queue_prompt_refuses_an_invalid_graph(monkeypatch) -> None:
    from app.capabilities.errors import CapabilityError
    from app.comfy_client import ComfyClient

    client = ComfyClient("http://127.0.0.1:65535")

    async def _catalogue(*_args, **_kwargs):
        return {"CheckpointLoaderSimple": {}}

    monkeypatch.setattr(client, "get_object_info", _catalogue)

    with pytest.raises(CapabilityError) as err:
        asyncio.run(client.queue_prompt({"1": {"class_type": "GhostNode", "inputs": {}}}))
    assert err.value.code == "EXTENSION_MISSING"
    assert err.value.recommended_action == "install_comfyui_extensions"


def test_model_readiness_follows_component_verification(client, monkeypatch) -> None:
    from app.capabilities import probes

    original = probes.probe_setup

    def _with_installed_models(snapshot) -> None:
        original(snapshot)
        snapshot.setup_components["zimage_models"] = {
            "component_id": "zimage_models",
            "name": "Z-Image Turbo Models",
            "status": "ready",
            "required": False,
        }

    monkeypatch.setattr(probes, "probe_setup", _with_installed_models)
    assert _by_id(_snapshot(client))["models.image.ready"]["status"] == "locally_verified"


def test_source_pending_components_are_not_configured_rather_than_broken(client, monkeypatch) -> None:
    from app.capabilities import probes

    original = probes.probe_setup

    def _with_pending_pack(snapshot) -> None:
        original(snapshot)
        snapshot.setup_components["zimage_models"] = {
            "component_id": "zimage_models",
            "name": "Z-Image Turbo Models",
            "status": "source_pending",
            "required": False,
        }

    monkeypatch.setattr(probes, "probe_setup", _with_pending_pack)
    item = _by_id(_snapshot(client, refresh=True))["models.image.ready"]
    assert item["status"] == "not_configured"
    assert item["reasonCode"] == "MODEL_SOURCE_PENDING"
    assert item["componentIds"] == ["zimage_models"]


def test_comfy_health_endpoint_is_structured_and_pathless(client) -> None:
    res = client.get("/api/comfy/health")
    assert res.status_code == 200
    payload = res.json()
    assert set(payload) >= {
        "reachable",
        "status",
        "baseUrl",
        "nodeCatalogAvailable",
        "models",
        "missingModelComponentIds",
        "checkedAt",
    }
    for model in payload["models"]:
        assert set(model) >= {"componentId", "name", "present"}


def test_health_endpoint_reports_component_ids_for_missing_models(client) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    payload = res.json()
    assert "missing_model_component_ids" in payload
    assert payload["comfy_status"] in ("ready", "degraded", "unreachable", "unknown")


# --------------------------------------------------------------------------
# references (slice 2)
# --------------------------------------------------------------------------


#: Smallest valid PNG, so the reference slice touches real bytes on disk rather than a stub.
_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/58BAwAI/AL+2Ir7pAAAAABJRU5ErkJggg=="
)


def _upload_png(client, project_id: str, tag: str) -> str:
    png = _ONE_PIXEL_PNG
    res = client.post(
        f"/api/projects/{project_id}/assets",
        files={"file": (f"{tag}.png", png, "image/png")},
        data={"tag": tag, "kind": "image"},
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_reference_ingredient_round_trip_survives_reload(client) -> None:
    project_id = _create_project(client, "Reference Project")
    asset_id = _upload_png(client, project_id, "ada_face")

    attached = client.post(
        f"/api/projects/{project_id}/references/ingredients",
        json={"asset_id": asset_id, "role": "character", "subject_name": "Ada", "priority": "primary"},
    )
    assert attached.status_code == 200
    ingredient_id = attached.json()["id"]

    listed = client.get(f"/api/projects/{project_id}/references/ingredients")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [ingredient_id]

    # Reload from the durable JSON store rather than from the response we just received.
    from app.references import store

    persisted = store.list_ingredients(project_id)
    assert [item["id"] for item in persisted] == [ingredient_id]
    assert persisted[0]["subject_name"] == "Ada"


def test_reference_exclusion_is_the_supported_removal_path(client) -> None:
    """There is no DELETE route; `include=false` is the honest substitute, and it persists."""
    project_id = _create_project(client, "Reference Exclude Project")
    asset_id = _upload_png(client, project_id, "prop_lamp")

    created = client.post(
        f"/api/projects/{project_id}/references/ingredients",
        json={"asset_id": asset_id, "role": "prop", "include": True},
    )
    ingredient_id = created.json()["id"]

    excluded = client.post(
        f"/api/projects/{project_id}/references/ingredients",
        json={"id": ingredient_id, "asset_id": asset_id, "role": "prop", "include": False},
    )
    assert excluded.status_code == 200
    assert excluded.json()["include"] is False

    from app.references import store

    persisted = store.list_ingredients(project_id)
    assert len(persisted) == 1
    assert persisted[0]["include"] is False

    assert client.delete(f"/api/projects/{project_id}/references/ingredients/{ingredient_id}").status_code in (
        404,
        405,
    )


def test_reference_capabilities_are_project_scoped(client) -> None:
    project_id = _create_project(client, "Reference Capability Project")
    capabilities = _by_id(_snapshot(client, project_id))
    for capability_id in ("references.read", "references.attach.project", "references.exclude"):
        assert capabilities[capability_id]["scope"] == "project"
        assert capabilities[capability_id]["status"] == "locally_verified"

    ic_lora = capabilities["references.ic_lora.ready"]
    assert ic_lora["status"] in ("locally_verified", "blocked", "not_configured", "unknown")
    if ic_lora["status"] != "locally_verified":
        assert ic_lora["reasonCode"]
        assert ic_lora["recommendedAction"]


# --------------------------------------------------------------------------
# source manager (slice 3)
# --------------------------------------------------------------------------


def test_source_manager_capabilities_reflect_real_state(client) -> None:
    capabilities = _by_id(_snapshot(client))
    assert capabilities["source_manager.read"]["status"] in ("locally_verified", "degraded", "unknown")
    assert capabilities["downloads.read"]["status"] in ("locally_verified", "degraded", "unknown")
    # Real archives for the Essential Packs are not published; enqueueing is fixture-proven only.
    assert capabilities["downloads.queue"]["status"] == "mock_verified"
    assert capabilities["downloads.queue"]["available"] is False


def test_install_capability_points_at_source_pending_components(client) -> None:
    item = _by_id(_snapshot(client))["source_manager.install"]
    assert item["status"] in ("partially_wired", "not_configured")
    if item["status"] == "not_configured":
        assert item["reasonCode"] == "MODEL_SOURCE_PENDING"
        assert item["recommendedAction"] == "add_source_url"
    assert item["available"] is False
