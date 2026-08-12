"""MAGI Co-Director READ-only tool certification (m6).

Phase 5 regression contract for the MAGI Final Integration Certification:

    1. READ tools surface authoritative MAGI state (projectId-scoped).
    2. Ownership isolation: Project A state is never readable through a
       Project B ToolContext (structured not-found; no bare-ID leak).
    3. MAGI is no longer "completely unsupported": it is absent from
       ``UNSUPPORTED_SYSTEMS`` and ``assert_unsupported_systems_have_no_tools()``
       passes with ``magi.*`` tools registered.
    4. Capability-scoped exposure: ``magi.*`` reads are exposed only for the
       ``magi``/``magieditor`` surface or explicit MAGI intent.
    5. No ``magi.*`` mutating tools exist (WRITE / PERSIST are N/A).
    6. A MAGI write request gets a truthful read-only limitation (structured
       not-found; no fake proposal; no hidden mutation).
    7. Docs claim MAGI = Operational (read-only).

All reads drive the REAL pathway through the public HTTP API (registry lookup ->
sanitize -> handler). No handler or service is mocked; only the shared
``client`` fixture from ``conftest.py`` is reused.
"""

from __future__ import annotations

import inspect
import uuid
from pathlib import Path
from typing import Any

import pytest

from app.db import Asset, SessionLocal

MAGI_READ_TOOLS = (
    "magi.inspect_sequence",
    "magi.inspect_clip",
    "magi.inspect_tracks",
    "magi.inspect_selection",
    "magi.inspect_timeline_lineage",
    "magi.readiness",
)


# ---------------------------------------------------------------------------
# HTTP helpers (real pathway)
# ---------------------------------------------------------------------------


def _create_project(client, name: str = "MAGI Read-Only Cert") -> str:
    res = client.post("/api/projects", json={"name": name, "global_prompt": "Handheld documentary look."})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _read(client, project_id: str, tool_id: str, **arguments) -> Any:
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/read",
        json={"toolId": tool_id, "arguments": arguments},
    )


def _result_data(response) -> dict[str, Any]:
    return response.json()["result"]["data"]


def _seed_sequence(client, project_id: str, *, clip_id: str = "clip_cert_1") -> str:
    """Create a real Asset row + persist a MAGI sequence (with an m5 export ledger)."""
    from app.magi.sequence.store import get_sequence

    asset_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(
            Asset(
                id=asset_id,
                project_id=project_id,
                tag="MAGI read-only cert clip",
                kind="image",
                filename="magi_ro.png",
                path="",
            )
        )
        db.commit()
    finally:
        db.close()

    base = get_sequence(project_id)
    body = {
        **base,
        "tracks": [
            {"id": "trk_v1_ro", "kind": "video", "label": "V1", "order": 0},
            {"id": "trk_i1_ro", "kind": "image", "label": "I1", "order": 3},
        ],
        "clips": [
            {
                "id": clip_id,
                "trackId": "trk_i1_ro",
                "assetId": asset_id,
                "name": "Read-only cert clip",
                "startFrame": 0,
                "durationFrames": 72,
                "inPoint": 0,
                "outPoint": 72,
            }
        ],
        "playheadFrame": 48,
        "exportLedger": {
            "batch_b1": {
                "batchBlockId": "batch_b1",
                "sceneId": "scn_1",
                "clips": [{"clipId": clip_id, "assetId": asset_id}],
            }
        },
    }
    res = client.put(f"/api/magi/projects/{project_id}/sequence", json={"sequence": body})
    assert res.status_code == 200, res.text
    return asset_id


# ---------------------------------------------------------------------------
# 1. All six MAGI read tools return authoritative structured data
# ---------------------------------------------------------------------------


def test_all_six_magi_read_tools_return_structured_data(client) -> None:
    project_id = _create_project(client, "MAGI Read Tools")
    _seed_sequence(client, project_id)

    for tool_id in MAGI_READ_TOOLS:
        kwargs = {"clipId": "clip_cert_1"} if tool_id == "magi.inspect_clip" else {}
        res = _read(client, project_id, tool_id, **kwargs)
        assert res.status_code == 200, f"{tool_id}: {res.text}"
        data = _result_data(res)
        assert isinstance(data, dict)
        assert data.get("projectId") == project_id or tool_id == "magi.readiness"

    seq = _result_data(_read(client, project_id, "magi.inspect_sequence"))
    assert seq["sequence"]["clips"][0]["id"] == "clip_cert_1"

    clip = _result_data(_read(client, project_id, "magi.inspect_clip", clipId="clip_cert_1"))
    assert clip["clip"]["id"] == "clip_cert_1"
    assert clip["track"]["id"] == "trk_i1_ro"

    tracks = _result_data(_read(client, project_id, "magi.inspect_tracks"))
    assert [t["id"] for t in tracks["tracks"]] == ["trk_v1_ro", "trk_i1_ro"]

    selection = _result_data(_read(client, project_id, "magi.inspect_selection"))
    assert selection["selection"]["playheadFrame"] == 48

    lineage = _result_data(_read(client, project_id, "magi.inspect_timeline_lineage"))
    assert lineage["exportLedger"]["batch_b1"]["batchBlockId"] == "batch_b1"
    assert lineage["exportedBatchBlockIds"] == ["batch_b1"]
    assert lineage["exportedClipCount"] == 1

    readiness = _result_data(_read(client, project_id, "magi.readiness"))
    assert readiness.get("noFakeExecution") is True
    assert readiness.get("status") == "ready"
    assert isinstance(readiness.get("productionSurfaceCount"), int)
    assert readiness.get("productionSurfaceCount") > 0


def test_inspect_clip_unknown_clip_id_is_honest_not_found(client) -> None:
    project_id = _create_project(client, "MAGI Missing Clip")
    _seed_sequence(client, project_id)
    res = _read(client, project_id, "magi.inspect_clip", clipId="clip_does_not_exist")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "TOOL_TARGET_NOT_FOUND"
    assert "clip_does_not_exist" in res.json()["detail"]["message"]


# ---------------------------------------------------------------------------
# 2. Ownership isolation — Project A state never readable via Project B
# ---------------------------------------------------------------------------


def test_magi_read_tools_are_project_ownership_isolated(client) -> None:
    project_a = _create_project(client, "MAGI Project A")
    _seed_sequence(client, project_a, clip_id="clip_a_only")
    project_b = _create_project(client, "MAGI Project B")

    # B cannot resolve A's clipId (structured not-found, existence never leaks).
    leak = _read(client, project_b, "magi.inspect_clip", clipId="clip_a_only")
    assert leak.status_code == 404
    assert "clip_a_only" in leak.json()["detail"]["message"]

    # B's sequence view shows none of A's clips.
    seq_b = _result_data(_read(client, project_b, "magi.inspect_sequence"))
    assert all(c.get("id") != "clip_a_only" for c in seq_b["sequence"].get("clips") or [])

    # B's lineage view leaks no A ledger entry.
    lineage_b = _result_data(_read(client, project_b, "magi.inspect_timeline_lineage"))
    assert "batch_b1" not in lineage_b["exportLedger"]

    # B's track view does not include A's tracks.
    tracks_b = _result_data(_read(client, project_b, "magi.inspect_tracks"))
    assert all(t.get("id") != "trk_i1_ro" for t in tracks_b["tracks"])


# ---------------------------------------------------------------------------
# 3. MAGI is no longer "completely unsupported"
# ---------------------------------------------------------------------------


def test_magi_is_not_an_unsupported_system() -> None:
    from app.codirector.tools.exposure import UNSUPPORTED_SYSTEMS, assert_unsupported_systems_have_no_tools
    from app.codirector.tools.registry import all_definitions

    assert "magi" not in UNSUPPORTED_SYSTEMS
    # Must pass even though magi.* tools ARE registered (they derive to "magi").
    assert_unsupported_systems_have_no_tools()

    from app.codirector.tools.exposure import derive_domain

    registered = {d.tool_id for d in all_definitions()}
    for tool_id in MAGI_READ_TOOLS:
        assert tool_id in registered
        assert derive_domain(tool_id) == "magi"


# ---------------------------------------------------------------------------
# 4. Capability-scoped exposure
# ---------------------------------------------------------------------------


def test_magi_read_tools_capability_scoped_exposure() -> None:
    from app.codirector.tools.exposure import expose

    magi_surface = expose(workspace_surface="magi", intent="What is on the MAGI sequence?")
    assert MAGI_READ_TOOLS[0] in magi_surface
    for tool_id in MAGI_READ_TOOLS:
        assert tool_id in magi_surface, f"{tool_id} missing from magi surface"

    magieditor_surface = expose(workspace_surface="magieditor")
    for tool_id in MAGI_READ_TOOLS:
        assert tool_id in magieditor_surface

    magi_intent = expose(workspace_surface=None, intent="Show me the MAGI timeline lineage.")
    for tool_id in MAGI_READ_TOOLS:
        assert tool_id in magi_intent, f"{tool_id} missing from explicit MAGI intent"

    unrelated = expose(workspace_surface="voice", intent="Make the dialogue warmer.")
    assert not any(t.startswith("magi.") for t in unrelated)

    bible_surface = expose(workspace_surface="bible", intent="Update the Production Bible summary.")
    assert not any(t.startswith("magi.") for t in bible_surface)


# ---------------------------------------------------------------------------
# 5. No magi.* mutating tools exist (WRITE / PERSIST are N/A)
# ---------------------------------------------------------------------------


def test_no_magi_mutating_tools_exist() -> None:
    from app.codirector.tools import registry

    mutating = [
        d.tool_id for d in registry.all_definitions() if d.tool_id.startswith("magi") and d.kind == "mutating"
    ]
    assert mutating == [], f"MAGI mutating tools must not exist (found: {mutating})"


# ---------------------------------------------------------------------------
# 6. A MAGI write request gets a truthful read-only limitation
# ---------------------------------------------------------------------------


def test_magi_write_attempt_gets_truthful_read_only_limitation(client) -> None:
    project_id = _create_project(client, "MAGI Write Refusal")
    _seed_sequence(client, project_id)

    # There is no magi.* mutating tool, so a write proposal is refused with a
    # structured TOOL_NOT_FOUND — never a fake proposal or hidden mutation.
    proposal = client.post(
        f"/api/codirector/projects/{project_id}/tools/proposals",
        json={"toolId": "magi.move_clip", "arguments": {"clipId": "clip_cert_1"}},
    )
    assert proposal.status_code == 404
    assert proposal.json()["detail"]["code"] == "TOOL_NOT_FOUND"

    # No execution receipt/partial work may have been created for the refused write.
    receipts = client.get(f"/api/codirector/projects/{project_id}/tool-invocations").json().get("invocations", [])
    assert not any(i.get("toolId") == "magi.move_clip" for i in receipts)

    # The sequence was not mutated by the refused write.
    seq = _result_data(_read(client, project_id, "magi.inspect_sequence"))
    assert seq["sequence"]["clips"][0]["id"] == "clip_cert_1"


# ---------------------------------------------------------------------------
# 7. Docs claim MAGI = Operational (read-only)
# ---------------------------------------------------------------------------


def test_magi_docs_claim_operational_read_only() -> None:
    from app.codirector.tools import exposure

    doc = inspect.getdoc(exposure) or ""
    assert "OPERATIONAL read-only" in doc

    handlers_doc = inspect.getsource(exposure.assert_unsupported_systems_have_no_tools)
    assert "Operational (read-only)" in handlers_doc

    magi_handler_path = (
        Path(exposure.__file__).resolve().parent / "handlers" / "magi.py"
    )
    src = magi_handler_path.read_text(encoding="utf-8")
    assert "READ-only" in src
    assert "No writes or proposals exist" in src


@pytest.mark.parametrize("tool_id", MAGI_READ_TOOLS)
def test_every_magi_read_tool_has_a_read_definition(client, tool_id) -> None:
    from app.codirector.tools.registry import all_definitions

    definitions = {d.tool_id: d for d in all_definitions()}
    definition = definitions[tool_id]
    assert definition.kind == "read"
    assert definition.capability == "project"
