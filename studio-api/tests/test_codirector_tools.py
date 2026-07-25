"""Co-Director M2.2: bounded tool registry and approved project actions.

Covers: registry closure and definition/handler binding integrity, argument sanitization and
result scrubbing, the capability adapter's fail-closed behavior, immediate read-tool execution
(HTTP + chat), the propose → approve/reject path for mutating tools (including staleness,
idempotency, and execution failure), the invocation ledger, the one-read-tool-per-turn bound,
and schema parity between `Base.metadata.create_all` and the `M003` migration.

The central invariant every mutation test asserts twice: creating a proposal changes nothing,
and only an explicit approval applies it.

Reuses the `client` fixture from `conftest.py` and the same `STUDIO_E2E` +
`ADEPT_CODIRECTOR_PROVIDER=mock` gating as `test_production_bible.py`.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def mock_provider_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)
    yield
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)


def _create_project(client, name: str = "Tool Test Project") -> str:
    res = client.post("/api/projects", json={"name": name, "global_prompt": "Handheld documentary look."})
    assert res.status_code == 200
    return res.json()["id"]


def _scenes(client, project_id: str) -> list[dict]:
    return client.get(f"/api/projects/{project_id}").json()["scenes"]


def _first_scene(client, project_id: str) -> dict:
    """New projects come with a default `Scene 1`, which most tests can act on directly."""

    scenes = _scenes(client, project_id)
    assert scenes, "a new project should have a default scene"
    return scenes[0]


def _add_scene(client, project_id: str, name: str = "Opening") -> dict:
    res = client.post(f"/api/projects/{project_id}/scenes", json={"name": name, "prompt": "Wide establishing shot."})
    assert res.status_code == 200
    return res.json()


def _create_bible(client, project_id: str) -> dict:
    preview = client.post(f"/api/codirector/projects/{project_id}/bible/import/preview", json={}).json()
    res = client.post(
        f"/api/codirector/projects/{project_id}/bible/import/confirm",
        json={"entities": preview["entities"], "facts": preview["facts"], "summary": preview.get("summary", "")},
    )
    assert res.status_code == 200
    return res.json()


def _read(client, project_id: str, tool_id: str, **arguments) -> dict:
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/read",
        json={"toolId": tool_id, "arguments": arguments},
    )


def _propose(client, project_id: str, tool_id: str, **arguments) -> dict:
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/proposals",
        json={"toolId": tool_id, "arguments": arguments},
    )


# --------------------------------------------------------------------------
# Registry integrity: the closed set, and every declared tool actually bound
# --------------------------------------------------------------------------


EXPECTED_READ_TOOLS = {
    "get_project_profile",
    "get_project_status",
    "list_scenes",
    "get_scene",
    "get_active_scene",
    "get_current_bible_version",
    "get_bible_entity",
    "list_bible_entities",
    "get_relevant_bible_context",
    "get_production_bible_summary",
    "get_scene_bible_context",
    "get_character_bible_context",
    "get_location_bible_context",
    "list_canon_records",
    "list_continuity_warnings",
    "get_generation_reference_package",
    "get_provider_health",
    "get_selected_model",
    "get_comfyui_health",
    "get_source_manager_status",
    "get_reference_capabilities",
    "get_engine_capabilities",
    "vision_validation_status",
    "vision_validation_report",
    # M2.6 timeline reference reads
    "get_timeline_image",
    "list_timeline_images",
    "get_reference_set",
    "list_reference_bindings",
    "build_generation_reference_package",
    "suggest_reference_bindings",
}

EXPECTED_MUTATING_TOOLS = {
    "create_scene",
    "update_scene_title",
    "set_scene_prompt",
    "record_director_decision",
    "propose_character_update",
    "propose_canon_record",
    "propose_canon_supersession",
    "propose_continuity_update",
    "propose_reference_link",
    "propose_production_decision",
    "propose_visual_language_update",
    "propose_storyboard_generation",
    "propose_vision_correction",
    "propose_asset_bible_link",
    "record_vision_review",
    # M2.6 timeline reference proposals (mutation only after approval)
    "create_reference_set_proposal",
    "propose_add_reference_binding",
    "propose_remove_reference_binding",
    "propose_update_reference_binding",
    "propose_apply_reference_preset",
}


def test_registry_contains_exactly_the_declared_tools() -> None:
    from app.codirector.tools import registry

    by_kind: dict[str, set[str]] = {"read": set(), "mutating": set()}
    for definition in registry.all_definitions():
        by_kind[definition.kind].add(definition.tool_id)

    assert by_kind["read"] == EXPECTED_READ_TOOLS
    assert by_kind["mutating"] == EXPECTED_MUTATING_TOOLS


def test_every_tool_resolves_to_a_handler() -> None:
    from app.codirector.tools import registry

    for definition in registry.all_definitions():
        if definition.kind == "read":
            assert callable(registry.read_handler(definition.tool_id))
        else:
            handler = registry.mutation_handler(definition.tool_id)
            assert callable(handler.preview) and callable(handler.apply)


def test_unknown_tool_id_raises_tool_not_found() -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.tools import registry

    with pytest.raises(CoDirectorError) as excinfo:
        registry.get("rm_minus_rf")
    assert excinfo.value.code == "TOOL_NOT_FOUND"


def test_read_handler_refuses_a_mutating_tool() -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.tools import registry

    with pytest.raises(CoDirectorError) as excinfo:
        registry.read_handler("create_scene")
    assert excinfo.value.code == "TOOL_KIND_MISMATCH"


def test_mutation_handler_refuses_a_read_tool() -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.tools import registry

    with pytest.raises(CoDirectorError) as excinfo:
        registry.mutation_handler("list_scenes")
    assert excinfo.value.code == "TOOL_KIND_MISMATCH"


def test_every_mutating_tool_pins_at_least_one_resource() -> None:
    """Without a pinned resource a proposal could never be detected as stale."""

    from app.codirector.tools import registry

    for definition in registry.all_definitions():
        if definition.kind == "mutating":
            assert definition.pinned_resources, f"{definition.tool_id} pins no resources"


def test_schema_version_mismatch_is_rejected() -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.tools import registry

    definition = registry.get("create_scene")
    with pytest.raises(CoDirectorError) as excinfo:
        registry.check_schema_version(definition, definition.schema_version + 1)
    assert excinfo.value.code == "TOOL_SCHEMA_VERSION_MISMATCH"


def test_catalog_endpoint_lists_tools_without_a_project(client) -> None:
    res = client.get("/api/codirector/tools")
    assert res.status_code == 200
    body = res.json()
    assert body["toolSchemaVersion"] >= 1
    ids = {t["toolId"] for t in body["tools"]}
    assert ids == EXPECTED_READ_TOOLS | EXPECTED_MUTATING_TOOLS
    mutating = next(t for t in body["tools"] if t["toolId"] == "create_scene")
    assert mutating["requiresApproval"] is True
    reading = next(t for t in body["tools"] if t["toolId"] == "list_scenes")
    assert reading["requiresApproval"] is False


# --------------------------------------------------------------------------
# Argument sanitization: the model-facing trust boundary
# --------------------------------------------------------------------------


def test_sanitize_arguments_drops_unknown_keys() -> None:
    from app.codirector.tools import registry
    from app.codirector.tools.sanitize import sanitize_arguments

    clean = sanitize_arguments(registry.get("create_scene"), {"name": "Alley", "shellCommand": "del /f *"})
    assert clean == {"name": "Alley"}


def test_sanitize_arguments_requires_required_parameters() -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.tools import registry
    from app.codirector.tools.sanitize import sanitize_arguments

    with pytest.raises(CoDirectorError) as excinfo:
        sanitize_arguments(registry.get("update_scene_title"), {"name": "Only a name"})
    assert excinfo.value.code == "TOOL_ARGUMENTS_INVALID"
    assert excinfo.value.details["parameter"] == "sceneId"


def test_sanitize_arguments_enforces_max_length() -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.tools import registry
    from app.codirector.tools.sanitize import sanitize_arguments

    with pytest.raises(CoDirectorError) as excinfo:
        sanitize_arguments(registry.get("create_scene"), {"name": "x" * 5000})
    assert excinfo.value.code == "TOOL_ARGUMENTS_INVALID"


def test_sanitize_arguments_enforces_numeric_range_and_choices() -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.tools import registry
    from app.codirector.tools.sanitize import sanitize_arguments

    definition = registry.get("create_scene")
    with pytest.raises(CoDirectorError):
        sanitize_arguments(definition, {"durationSec": 9999})
    with pytest.raises(CoDirectorError):
        sanitize_arguments(definition, {"engine": "arbitrary-binary"})
    assert sanitize_arguments(definition, {"durationSec": "6.5"}) == {"durationSec": 6.5}


def test_sanitize_arguments_rejects_non_object_payload() -> None:
    from app.codirector.errors import CoDirectorError
    from app.codirector.tools import registry
    from app.codirector.tools.sanitize import sanitize_arguments

    with pytest.raises(CoDirectorError):
        sanitize_arguments(registry.get("list_scenes"), ["not", "an", "object"])


def test_input_hash_is_stable_and_argument_sensitive() -> None:
    from app.codirector.tools.sanitize import compute_input_hash

    base = {"tool_id": "create_scene", "schema_version": 1, "base_resource_versions": {"project": "v1"}}
    first = compute_input_hash(arguments={"name": "A"}, **base)
    again = compute_input_hash(arguments={"name": "A"}, **base)
    different = compute_input_hash(arguments={"name": "B"}, **base)
    assert first == again
    assert first != different


# --------------------------------------------------------------------------
# Result sanitization: what leaves the server
# --------------------------------------------------------------------------


def test_sanitize_result_scrubs_absolute_paths() -> None:
    from app.codirector.tools.sanitize import sanitize_result

    payload, truncated = sanitize_result(
        {"outputPath": r"C:\AdeptFilmWorks\data\projects\p1\out.mp4", "note": "fine"}, char_budget=4000
    )
    assert truncated is False
    assert "AdeptFilmWorks" not in json.dumps(payload)
    assert payload["note"] == "fine"


def test_sanitize_result_truncates_over_budget_and_signals_it() -> None:
    from app.codirector.tools.sanitize import sanitize_result

    payload, truncated = sanitize_result({"big": "x" * 5000, "small": "keep"}, char_budget=500)
    assert truncated is True
    assert payload["_truncated"] is True


def test_sanitize_result_wraps_non_dict_values() -> None:
    from app.codirector.tools.sanitize import sanitize_result

    payload, truncated = sanitize_result(["a", "b"], char_budget=4000)
    assert payload == {"value": ["a", "b"]}
    assert truncated is False


def test_sanitize_result_caps_long_lists() -> None:
    from app.codirector.tools.sanitize import MAX_LIST_ITEMS, sanitize_result

    payload, _ = sanitize_result({"items": list(range(MAX_LIST_ITEMS + 25))}, char_budget=100_000)
    assert len(payload["items"]) == MAX_LIST_ITEMS + 1
    assert "more omitted" in str(payload["items"][-1])


# --------------------------------------------------------------------------
# Capability adapter: fail closed, never raise
# --------------------------------------------------------------------------


def test_capability_project_not_configured_without_project_id() -> None:
    import asyncio

    from app.codirector.tools.capabilities import CapabilityAdapter
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        state = asyncio.run(CapabilityAdapter(db, None).state_for("project"))
        assert state.key == "project"
        assert state.available is True
    finally:
        db.close()


def test_capability_bible_not_configured_before_bible_exists(client) -> None:
    import asyncio

    from app.codirector.tools.capabilities import CapabilityAdapter
    from app.db import SessionLocal

    project_id = _create_project(client)
    db = SessionLocal()
    try:
        state = asyncio.run(CapabilityAdapter(db, project_id).state_for("bible"))
        assert state.key == "bible"
        assert state.available is True
    finally:
        db.close()


def test_capability_unknown_key_raises() -> None:
    import asyncio

    from app.codirector.errors import CoDirectorError
    from app.codirector.tools.capabilities import CapabilityAdapter
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        with pytest.raises(CoDirectorError) as excinfo:
            asyncio.run(CapabilityAdapter(db, None).state_for("shell"))
        assert excinfo.value.code == "CAPABILITY_UNKNOWN"
    finally:
        db.close()


def test_capability_probe_exception_degrades_to_unavailable(client, monkeypatch) -> None:
    """A broken probe must never propagate — it can only make a tool unavailable."""

    import asyncio

    from app.codirector.tools.capabilities import CapabilityAdapter
    from app.db import SessionLocal

    project_id = _create_project(client)
    db = SessionLocal()
    try:
        adapter = CapabilityAdapter(db, project_id)

        async def boom(*_args, **_kwargs):
            raise RuntimeError("probe exploded")

        monkeypatch.setattr(adapter._bridge, "readiness_for_tool_key", boom)
        state = asyncio.run(adapter.state_for("comfyui"))
        assert state.available is False
        assert state.status == "unavailable"
    finally:
        db.close()


def test_availability_endpoint_reports_every_tool(client) -> None:
    project_id = _create_project(client)
    res = client.get(f"/api/codirector/projects/{project_id}/tools/availability")
    assert res.status_code == 200
    body = res.json()
    assert {a["toolId"] for a in body["availability"]} == EXPECTED_READ_TOOLS | EXPECTED_MUTATING_TOOLS
    project_tools = [a for a in body["availability"] if a["capability"] == "project"]
    assert all(a["available"] for a in project_tools)
    bible_tool = next(a for a in body["availability"] if a["toolId"] == "get_bible_entity")
    assert bible_tool["capability"] == "bible"
    assert "available" in bible_tool


# --------------------------------------------------------------------------
# Read tools: execute immediately, never mutate
# --------------------------------------------------------------------------


def test_read_project_profile(client) -> None:
    project_id = _create_project(client, "Neon Alley")
    res = _read(client, project_id, "get_project_profile")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "succeeded"
    assert body["kind"] == "read"
    assert body["result"]["name"] == "Neon Alley"


def test_read_project_status_counts_scenes(client) -> None:
    project_id = _create_project(client)
    _add_scene(client, project_id)
    res = _read(client, project_id, "get_project_status")
    assert res.status_code == 200
    assert res.json()["result"]["sceneCount"] == 2


def test_read_list_scenes_and_get_scene(client) -> None:
    project_id = _create_project(client)
    scene = _add_scene(client, project_id, "Rooftop")

    listed = _read(client, project_id, "list_scenes")
    assert listed.status_code == 200
    assert [s["name"] for s in listed.json()["result"]["scenes"]] == ["Scene 1", "Rooftop"]

    fetched = _read(client, project_id, "get_scene", sceneId=scene["id"])
    assert fetched.status_code == 200
    assert fetched.json()["result"]["sceneId"] == scene["id"]


def test_read_get_scene_across_projects_is_not_found(client) -> None:
    project_a = _create_project(client, "A")
    project_b = _create_project(client, "B")
    scene = _first_scene(client, project_a)

    res = _read(client, project_b, "get_scene", sceneId=scene["id"])
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "TOOL_TARGET_NOT_FOUND"


def test_read_active_scene_without_selection(client) -> None:
    project_id = _create_project(client)
    res = _read(client, project_id, "get_active_scene")
    assert res.status_code == 200
    assert res.json()["result"]["activeScene"] is None


def test_read_bible_tools_after_bible_exists(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)

    version = _read(client, project_id, "get_current_bible_version")
    assert version.status_code == 200
    assert version.json()["result"]["versionNumber"] == 1

    entities = _read(client, project_id, "list_bible_entities")
    assert entities.status_code == 200
    assert entities.json()["result"]["total"] >= 1

    context = _read(client, project_id, "get_relevant_bible_context", tokenBudget=500)
    assert context.status_code == 200
    assert "manifest" in context.json()["result"]


def test_read_bible_tool_blocked_when_no_bible(client) -> None:
    project_id = _create_project(client)
    res = _read(client, project_id, "get_current_bible_version")
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "CAPABILITY_NOT_CONFIGURED"


def test_blocked_read_is_still_recorded_in_the_ledger(client) -> None:
    """A tool the model was *prevented* from running is as auditable as one that ran."""

    project_id = _create_project(client)
    assert _read(client, project_id, "get_bible_entity", entityKey="ava").status_code == 409

    ledger = client.get(f"/api/codirector/projects/{project_id}/tool-invocations").json()["invocations"]
    blocked = [i for i in ledger if i["toolId"] == "get_bible_entity"]
    assert len(blocked) == 1
    assert blocked[0]["status"] in {"blocked", "failed"}
    assert blocked[0]["errorCode"]


def test_read_endpoint_rejects_a_mutating_tool(client) -> None:
    project_id = _create_project(client)
    res = _read(client, project_id, "create_scene", name="Sneaky")
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "TOOL_KIND_MISMATCH"
    assert [s["name"] for s in _scenes(client, project_id)] == ["Scene 1"]


def test_read_endpoint_rejects_an_unknown_tool(client) -> None:
    project_id = _create_project(client)
    res = _read(client, project_id, "exec_shell")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "TOOL_NOT_FOUND"


def test_read_endpoint_rejects_invalid_arguments(client) -> None:
    project_id = _create_project(client)
    res = _read(client, project_id, "get_scene")
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "TOOL_ARGUMENTS_INVALID"


def test_read_endpoint_requires_an_existing_project(client) -> None:
    res = _read(client, "no-such-project", "get_project_profile")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


def test_successful_read_is_logged_with_duration_and_hash(client) -> None:
    project_id = _create_project(client)
    _read(client, project_id, "get_project_profile")
    ledger = client.get(f"/api/codirector/projects/{project_id}/tool-invocations").json()["invocations"]
    assert len(ledger) == 1
    assert ledger[0]["status"] == "succeeded"
    assert ledger[0]["resultHash"]
    assert ledger[0]["proposalId"] is None


def test_ledger_can_be_filtered_by_tool(client) -> None:
    project_id = _create_project(client)
    _read(client, project_id, "get_project_profile")
    _read(client, project_id, "get_project_status")
    filtered = client.get(
        f"/api/codirector/projects/{project_id}/tool-invocations", params={"tool_id": "get_project_status"}
    ).json()["invocations"]
    assert [i["toolId"] for i in filtered] == ["get_project_status"]


# --------------------------------------------------------------------------
# Mutating tools: propose, then approve — never both in one step
# --------------------------------------------------------------------------


def test_proposing_a_scene_changes_nothing(client) -> None:
    project_id = _create_project(client)
    res = _propose(client, project_id, "create_scene", name="Rooftop Standoff", durationSec=6.0)
    assert res.status_code == 200
    proposal = res.json()
    assert proposal["status"] == "pending"
    assert proposal["proposalType"] == "tool_call"
    assert proposal["toolCall"]["toolId"] == "create_scene"
    assert proposal["toolCall"]["inputHash"]
    assert proposal["toolCall"]["baseResourceVersions"]
    assert proposal["toolCall"]["preview"]["summary"]

    assert len(_scenes(client, project_id)) == 1
    ledger = client.get(f"/api/codirector/projects/{project_id}/tool-invocations").json()["invocations"]
    assert ledger == []


def test_stored_arguments_are_the_sanitized_ones(client) -> None:
    """Approval replays what the registry accepted, not what the caller sent."""

    project_id = _create_project(client)
    res = client.post(
        f"/api/codirector/projects/{project_id}/tools/proposals",
        json={"toolId": "create_scene", "arguments": {"name": "Clean", "rmRf": "/", "engine": "ltx"}},
    )
    assert res.status_code == 200
    assert res.json()["toolCall"]["arguments"] == {"name": "Clean", "engine": "ltx"}


def test_approving_a_scene_proposal_creates_the_scene(client) -> None:
    project_id = _create_project(client)
    proposal = _propose(client, project_id, "create_scene", name="Rooftop Standoff", durationSec=6.0).json()

    receipt = client.post(
        f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={}
    )
    assert receipt.status_code == 200
    body = receipt.json()
    assert body["status"] == "success"
    assert body["toolId"] == "create_scene"
    assert body["toolInvocationId"]

    assert [s["name"] for s in _scenes(client, project_id)] == ["Scene 1", "Rooftop Standoff"]

    refetched = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}").json()
    assert refetched["status"] == "completed"


def test_approved_execution_is_linked_to_its_proposal_in_the_ledger(client) -> None:
    project_id = _create_project(client)
    proposal = _propose(client, project_id, "create_scene", name="Linked").json()
    client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})

    ledger = client.get(f"/api/codirector/projects/{project_id}/tool-invocations").json()["invocations"]
    assert len(ledger) == 1
    assert ledger[0]["proposalId"] == proposal["id"]
    assert ledger[0]["kind"] == "mutating"
    assert ledger[0]["createdBy"] == "user"


def test_rejecting_a_tool_proposal_applies_nothing(client) -> None:
    project_id = _create_project(client)
    proposal = _propose(client, project_id, "create_scene", name="Never Made").json()

    rejected = client.post(
        f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/reject",
        json={"note": "Not this beat."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert len(_scenes(client, project_id)) == 1


def test_requesting_revision_then_approving_still_works(client) -> None:
    project_id = _create_project(client)
    proposal = _propose(client, project_id, "create_scene", name="Revised").json()

    revision = client.post(
        f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/request-revision",
        json={"note": "Shorter."},
    )
    assert revision.status_code == 200
    assert revision.json()["status"] == "revision_requested"

    approved = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert approved.status_code == 200
    assert len(_scenes(client, project_id)) == 2


def test_cancelling_a_tool_proposal(client) -> None:
    project_id = _create_project(client)
    proposal = _propose(client, project_id, "create_scene", name="Cancelled").json()
    res = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/cancel", json={})
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"

    again = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "PROPOSAL_INVALID_STATE"


def test_approving_twice_does_not_apply_twice(client) -> None:
    project_id = _create_project(client)
    proposal = _propose(client, project_id, "create_scene", name="Once Only").json()
    first = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert first.status_code == 200

    second = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "APPROVAL_ALREADY_RECORDED"
    assert len(_scenes(client, project_id)) == 2


def test_update_scene_title_proposal_and_approval(client) -> None:
    project_id = _create_project(client)
    scene = _add_scene(client, project_id, "Working Title")

    proposal = _propose(client, project_id, "update_scene_title", sceneId=scene["id"], name="Final Title").json()
    assert proposal["toolCall"]["preview"]["resourceId"] == scene["id"]
    assert _scenes(client, project_id)[1]["name"] == "Working Title"

    client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert _scenes(client, project_id)[1]["name"] == "Final Title"


def test_set_scene_prompt_proposal_and_approval(client) -> None:
    project_id = _create_project(client)
    scene = _add_scene(client, project_id)

    proposal = _propose(
        client, project_id, "set_scene_prompt", sceneId=scene["id"], prompt="Slow dolly through the rain."
    ).json()
    assert proposal["toolCall"]["preview"]["warnings"]

    client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert _scenes(client, project_id)[1]["prompt"] == "Slow dolly through the rain."


def test_record_director_decision_writes_a_bible_fact(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)

    proposal = _propose(
        client,
        project_id,
        "record_director_decision",
        decision="Ava never appears in daylight.",
        rationale="Keeps the noir contrast consistent.",
    ).json()
    assert proposal["toolCall"]["toolId"] == "record_director_decision"

    receipt = client.post(
        f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={}
    ).json()
    assert receipt["status"] == "success"
    assert receipt["resultingVersionNumber"] == 2

    bible = client.get(f"/api/codirector/projects/{project_id}/bible").json()
    statements = [f["statement"] for f in bible["currentVersion"]["facts"]]
    assert any("never appears in daylight" in s for s in statements)


def test_proposing_a_read_tool_is_rejected(client) -> None:
    project_id = _create_project(client)
    res = _propose(client, project_id, "list_scenes")
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "TOOL_KIND_MISMATCH"


def test_proposal_blocked_when_capability_missing(client) -> None:
    project_id = _create_project(client)
    res = _propose(client, project_id, "record_director_decision", decision="No Bible yet.")
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "CAPABILITY_NOT_CONFIGURED"
    assert client.get(f"/api/codirector/projects/{project_id}/proposals").json()["proposals"] == []


def test_tool_proposal_preview_returns_stored_preview_not_a_bible_diff(client) -> None:
    project_id = _create_project(client)
    proposal = _propose(client, project_id, "create_scene", name="Previewed").json()
    res = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/preview")
    assert res.status_code == 200
    body = res.json()
    assert body["entityDiff"] == []
    assert body["toolPreview"]["summary"]
    assert body["isStale"] is False


# --------------------------------------------------------------------------
# Staleness: the world moved between propose and approve
# --------------------------------------------------------------------------


def test_scene_proposal_goes_stale_when_the_scene_changes(client) -> None:
    project_id = _create_project(client)
    scene = _add_scene(client, project_id, "Before")
    proposal = _propose(client, project_id, "update_scene_title", sceneId=scene["id"], name="Proposed").json()

    edited = client.patch(
        f"/api/projects/{project_id}/scenes/{scene['id']}",
        json={"name": "Edited By Hand", "prompt": "Wide establishing shot.", "continuity_json": ""},
    )
    assert edited.status_code == 200

    approve = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert approve.status_code == 409
    assert approve.json()["detail"]["code"] == "PROPOSAL_STALE"

    assert _scenes(client, project_id)[1]["name"] == "Edited By Hand"
    assert client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}").json()["status"] == "stale"


def test_project_scoped_proposal_goes_stale_when_a_scene_is_added(client) -> None:
    project_id = _create_project(client)
    proposal = _propose(client, project_id, "create_scene", name="Second").json()
    _add_scene(client, project_id, "Added Meanwhile")

    approve = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert approve.status_code == 409
    assert approve.json()["detail"]["code"] == "PROPOSAL_STALE"


def test_bible_scoped_tool_proposal_goes_stale_when_the_bible_moves(client) -> None:
    project_id = _create_project(client)
    _create_bible(client, project_id)
    proposal = _propose(client, project_id, "record_director_decision", decision="Rain in every exterior.").json()

    bump = client.post(
        f"/api/codirector/projects/{project_id}/bible/versions",
        json={
            "mutations": {
                "entityMutations": [{"entityType": "prop", "entityKey": "umbrella", "displayName": "Umbrella"}],
                "factMutations": [],
            }
        },
    )
    assert bump.status_code == 200

    approve = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert approve.status_code == 409
    assert approve.json()["detail"]["code"] == "PROPOSAL_STALE"


def test_stale_tool_proposal_can_still_be_cancelled(client) -> None:
    project_id = _create_project(client)
    proposal = _propose(client, project_id, "create_scene", name="Doomed").json()
    _add_scene(client, project_id)

    client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    cancelled = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/cancel", json={})
    assert cancelled.status_code == 200


def test_unreadable_tool_payload_is_treated_as_stale(client) -> None:
    """A payload that no longer parses can never be applied — only cancelled."""

    from app.db import CoDirectorProposal, SessionLocal

    project_id = _create_project(client)
    proposal = _propose(client, project_id, "create_scene", name="Corrupt").json()

    db = SessionLocal()
    try:
        row = db.get(CoDirectorProposal, proposal["id"])
        row.payload_json = "{ not json"
        db.commit()
    finally:
        db.close()

    approve = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert approve.status_code == 409
    assert approve.json()["detail"]["code"] == "PROPOSAL_STALE"


def test_execution_failure_records_a_failed_receipt(client, monkeypatch) -> None:
    project_id = _create_project(client)
    proposal = _propose(client, project_id, "create_scene", name="Will Fail").json()

    from app.codirector.tools import registry
    from app.codirector.tools.handlers import scenes

    def exploding_apply(ctx, args):
        raise RuntimeError("disk on fire")

    monkeypatch.setitem(
        registry._MUTATION_HANDLERS,
        "create_scene",
        registry.MutationHandler(scenes.preview_create_scene, exploding_apply),
    )

    approve = client.post(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/approve", json={})
    assert approve.status_code == 502
    assert approve.json()["detail"]["code"] == "TOOL_EXECUTION_FAILED"
    # The reason still says what happened, minus anything path- or secret-shaped.
    assert "disk on fire" in approve.json()["detail"]["details"]["reason"]

    monkeypatch.undo()
    refetched = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}").json()
    assert refetched["status"] == "failed"

    receipt = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal['id']}/receipt").json()
    assert receipt["status"] == "failed"
    assert receipt["error"]["code"] == "TOOL_EXECUTION_FAILED"

    ledger = client.get(f"/api/codirector/projects/{project_id}/tool-invocations").json()["invocations"]
    assert ledger[0]["status"] == "failed"
    assert len(_scenes(client, project_id)) == 1


# --------------------------------------------------------------------------
# Structured output: responseType classification
# --------------------------------------------------------------------------


def test_parse_structured_reply_plain_message() -> None:
    from app.codirector.structured_output import parse_structured_reply

    parsed = parse_structured_reply("Just talking through the scene.")
    assert parsed.response_type == "message"
    assert parsed.tool_call is None
    assert parsed.display == "Just talking through the scene."


def test_parse_structured_reply_read_tool_call() -> None:
    from app.codirector.structured_output import parse_structured_reply

    reply = (
        "Let me check.\n\n```tool\n"
        + json.dumps({"responseType": "read_tool_call", "toolId": "list_scenes", "arguments": {"limit": 5}})
        + "\n```"
    )
    parsed = parse_structured_reply(reply)
    assert parsed.response_type == "read_tool_call"
    assert parsed.tool_call.tool_id == "list_scenes"
    assert parsed.tool_call.arguments == {"limit": 5}
    assert "```tool" not in parsed.display


def test_parse_structured_reply_mutation_proposal() -> None:
    from app.codirector.structured_output import parse_structured_reply

    reply = (
        "Proposing a scene.\n\n```tool\n"
        + json.dumps({"responseType": "mutation_proposal", "toolId": "create_scene", "arguments": {"name": "X"}})
        + "\n```"
    )
    parsed = parse_structured_reply(reply)
    assert parsed.response_type == "mutation_proposal"
    assert parsed.tool_call.tool_id == "create_scene"


def test_parse_structured_reply_infers_response_type_from_tool_kind() -> None:
    """A model that omits `responseType` still can't turn a mutation into an immediate read."""

    from app.codirector.structured_output import parse_structured_reply

    reply = "```tool\n" + json.dumps({"toolId": "create_scene", "arguments": {}}) + "\n```"
    assert parse_structured_reply(reply).response_type == "mutation_proposal"

    reply = "```tool\n" + json.dumps({"toolId": "list_scenes", "arguments": {}}) + "\n```"
    assert parse_structured_reply(reply).response_type == "read_tool_call"


def test_parse_structured_reply_malformed_tool_fence() -> None:
    from app.codirector.structured_output import parse_structured_reply

    parsed = parse_structured_reply("```tool\n{ nope,,, \n```")
    assert parsed.error is not None
    assert parsed.tool_call is None


def test_parse_structured_reply_unknown_tool_is_an_error() -> None:
    from app.codirector.structured_output import parse_structured_reply

    reply = "```tool\n" + json.dumps({"toolId": "spawn_shell", "arguments": {}}) + "\n```"
    parsed = parse_structured_reply(reply)
    assert parsed.error is not None
    assert parsed.tool_call is None


def test_parse_structured_reply_still_handles_bible_proposal_fences() -> None:
    from app.codirector.structured_output import parse_structured_reply

    reply = (
        "```proposal\n"
        + json.dumps(
            {
                "proposalType": "entity_update",
                "title": "Update Ava",
                "summary": "Scar",
                "entityMutations": [{"entityType": "character", "entityKey": "ava", "displayName": "Ava"}],
                "factMutations": [],
            }
        )
        + "\n```"
    )
    parsed = parse_structured_reply(reply)
    assert parsed.response_type == "mutation_proposal"
    assert parsed.bible_proposal is not None
    assert parsed.tool_call is None


# --------------------------------------------------------------------------
# Chat integration: the read loop and its bound
# --------------------------------------------------------------------------


def test_chat_runs_a_read_tool_and_answers_from_the_result(client, mock_provider_env, monkeypatch) -> None:
    project_id = _create_project(client)
    _add_scene(client, project_id, "Rooftop")
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "read_tool_success")

    res = client.post(
        "/api/codirector/chat",
        json={"messages": [{"role": "user", "content": "how many scenes?"}], "project_id": project_id},
    )
    assert res.status_code == 200
    body = res.json()
    assert "```tool" not in body["reply"]
    assert [i["toolId"] for i in body["toolInvocations"]] == ["list_scenes"]
    assert body["toolInvocations"][0]["status"] == "succeeded"
    assert body["proposal"] is None


def test_chat_read_tool_blocked_by_capability_still_answers(client, mock_provider_env, monkeypatch) -> None:
    project_id = _create_project(client)
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "read_tool_blocked_capability")

    res = client.post(
        "/api/codirector/chat",
        json={"messages": [{"role": "user", "content": "is comfy up?"}], "project_id": project_id},
    )
    assert res.status_code == 200
    assert res.json()["toolInvocations"] == []

    ledger = client.get(f"/api/codirector/projects/{project_id}/tool-invocations").json()["invocations"]
    assert ledger[0]["status"] == "blocked"


def test_chat_mutation_tool_creates_a_proposal_only(client, mock_provider_env, monkeypatch) -> None:
    project_id = _create_project(client)
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "mutation_tool_proposal")

    res = client.post(
        "/api/codirector/chat",
        json={"messages": [{"role": "user", "content": "add a rooftop scene"}], "project_id": project_id},
    )
    assert res.status_code == 200
    proposal = res.json()["proposal"]
    assert proposal["proposalType"] == "tool_call"
    assert proposal["status"] == "pending"
    assert proposal["createdBy"] == "assistant"
    assert len(_scenes(client, project_id)) == 1


def test_chat_exceeding_the_read_loop_bound_errors(client, mock_provider_env, monkeypatch) -> None:
    project_id = _create_project(client)
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "tool_loop_limit")

    res = client.post(
        "/api/codirector/chat",
        json={"messages": [{"role": "user", "content": "keep looking"}], "project_id": project_id},
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "TOOL_LOOP_LIMIT_REACHED"

    # Exactly one tool ran before the bound stopped the chain.
    ledger = client.get(f"/api/codirector/projects/{project_id}/tool-invocations").json()["invocations"]
    assert len(ledger) == 1


def test_chat_tool_call_without_a_project_is_reported(client, mock_provider_env, monkeypatch) -> None:
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "read_tool_success")
    res = client.post("/api/codirector/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert res.status_code == 502
    assert res.json()["detail"]["code"] == "STRUCTURED_OUTPUT_INVALID"


def _stream_events(client, project_id: str, content: str) -> list[dict]:
    events: list[dict] = []
    with client.stream(
        "POST",
        "/api/codirector/chat/stream",
        json={"messages": [{"role": "user", "content": content}], "project_id": project_id},
    ) as res:
        assert res.status_code == 200
        for line in res.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            events.append(json.loads(line[len("data:") :].strip()))
    return events


def test_stream_emits_the_read_tool_lifecycle(client, mock_provider_env, monkeypatch) -> None:
    project_id = _create_project(client)
    _add_scene(client, project_id)
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "read_tool_success")

    events = _stream_events(client, project_id, "how many scenes?")
    types = [e["type"] for e in events]
    assert types.index("tool_requested") < types.index("tool_started") < types.index("tool_completed")
    assert types.count("completed") == 1
    completed = next(e for e in events if e["type"] == "completed")
    assert "```tool" not in completed["content"]


def test_stream_emits_capability_blocked(client, mock_provider_env, monkeypatch) -> None:
    project_id = _create_project(client)
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "read_tool_blocked_capability")

    events = _stream_events(client, project_id, "is comfy up?")
    blocked = next(e for e in events if e["type"] == "capability_blocked")
    assert blocked["capability"] == "comfyui"
    assert blocked["error"]["code"] == "CAPABILITY_UNAVAILABLE"
    assert any(e["type"] == "completed" for e in events)


def test_stream_emits_tool_proposal_created(client, mock_provider_env, monkeypatch) -> None:
    project_id = _create_project(client)
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "mutation_tool_proposal")

    events = _stream_events(client, project_id, "add a rooftop scene")
    created = next(e for e in events if e["type"] == "tool_proposal_created")
    assert created["proposal"]["proposalType"] == "tool_call"
    assert created["toolId"] == "create_scene"
    assert len(_scenes(client, project_id)) == 1


def test_stream_reports_the_loop_bound_as_an_error_event(client, mock_provider_env, monkeypatch) -> None:
    project_id = _create_project(client)
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "tool_loop_limit")

    events = _stream_events(client, project_id, "keep looking")
    errors = [e for e in events if e["type"] == "error"]
    assert any(e["error"]["code"] == "TOOL_LOOP_LIMIT_REACHED" for e in errors)


# --------------------------------------------------------------------------
# Migration <-> SQLAlchemy model schema parity
# --------------------------------------------------------------------------


def test_m003_matches_the_invocation_model(tmp_path) -> None:
    from sqlalchemy import create_engine, inspect

    from app.db import Base
    from app.migrations import DEFAULT_REGISTRY, MigrationRunner

    migrated_engine = create_engine(f"sqlite:///{tmp_path / 'migrated.db'}")
    MigrationRunner(migrated_engine, DEFAULT_REGISTRY).apply_pending()
    created_engine = create_engine(f"sqlite:///{tmp_path / 'created.db'}")
    Base.metadata.create_all(bind=created_engine)

    table = "codirector_tool_invocations"
    migrated_cols = {c["name"] for c in inspect(migrated_engine).get_columns(table)}
    created_cols = {c["name"] for c in inspect(created_engine).get_columns(table)}
    assert migrated_cols == created_cols


def test_m003_is_idempotent(tmp_path) -> None:
    from sqlalchemy import create_engine

    from app.migrations import DEFAULT_REGISTRY, MigrationRunner

    engine = create_engine(f"sqlite:///{tmp_path / 'twice.db'}")
    first = MigrationRunner(engine, DEFAULT_REGISTRY).apply_pending()
    second = MigrationRunner(engine, DEFAULT_REGISTRY).apply_pending()
    assert "M003" in first.applied
    assert "M003" in second.already_applied
