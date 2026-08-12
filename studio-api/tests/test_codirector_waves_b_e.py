"""Wave B–E — compaction, memory export/import, audit, append_tool_event."""

from __future__ import annotations

import uuid

from app.codirector.conversation_audit import audit_conversation, rebuild_fold
from app.codirector.conversation_events import EventInput, append_events, fold_events
from app.codirector.service import append_tool_event
from app.db import Project, get_db


def _create_project(client, name: str) -> dict:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()


def _append(client, project_id: str, event: dict) -> dict:
    res = client.post(f"/api/codirector/conversations/{project_id}/events", json={"events": [event]})
    assert res.status_code == 200, res.text
    return res.json()


def _user_event(content: str, *, message_id: str | None = None) -> dict:
    return {
        "role": "user",
        "content": content,
        "message_id": message_id or f"u-{uuid.uuid4().hex}",
        "client_request_id": f"cr-{uuid.uuid4().hex}",
        "actor": "user",
    }


def _assistant_event(content: str, *, message_id: str | None = None) -> dict:
    return {
        "role": "assistant",
        "content": content,
        "message_id": message_id or f"a-{uuid.uuid4().hex}",
        "actor": "assistant",
    }


def _tool_events(tool_id: str, *, request_id: str) -> list[dict]:
    return [
        {
            "role": "tool",
            "event_type": "tool_call",
            "content": "",
            "message_id": f"tool-call-{request_id}-{tool_id}",
            "tool_id": tool_id,
            "tool_arguments": {"q": "test"},
            "actor": "assistant",
            "request_id": request_id,
        },
        {
            "role": "tool",
            "event_type": "tool_result",
            "content": "",
            "message_id": f"tool-result-{request_id}-{tool_id}",
            "tool_id": tool_id,
            "tool_result": {"ok": True},
            "actor": "assistant",
            "request_id": request_id,
        },
    ]


def test_compact_then_fold_skips_compacted_messages(client) -> None:
    project = _create_project(client, "wave-b-compact")
    pid = project["id"]

    u1 = _user_event("hello one", message_id="u1")
    a1 = _assistant_event("reply one", message_id="a1")
    u2 = _user_event("hello two", message_id="u2")
    a2 = _assistant_event("reply two", message_id="a2")

    _append(client, pid, u1)
    _append(client, pid, a1)
    _append(client, pid, u2)

    res = client.post(
        f"/api/codirector/conversations/{pid}/compact",
        json={
            "beforeSequence": 1,
            "summaryText": "Earlier chat summarized: greeting exchange.",
            "requestId": "compact-req-1",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["compactedThroughSequence"] == 1
    assert body["appendedCount"] == 1

    _append(client, pid, a2)

    convo = client.get(f"/api/codirector/conversations/{pid}").json()
    ids = {m.get("id") for m in convo["messages"]}
    assert "u1" not in ids
    assert "a1" not in ids
    assert "u2" in ids
    assert "a2" in ids
    assert any("summarized" in (m.get("content") or "") for m in convo["messages"])


def test_tool_events_survive_compaction(client) -> None:
    project = _create_project(client, "wave-b-tool-compact")
    pid = project["id"]
    rid = "req-tool-1"

    _append(client, pid, _user_event("check status", message_id="u-tool"))
    for ev in _tool_events("system.status", request_id=rid):
        _append(client, pid, ev)

    res = client.post(
        f"/api/codirector/conversations/{pid}/compact",
        json={
            "beforeSequence": 0,
            "summaryText": "User asked about status.",
        },
    )
    assert res.status_code == 200

    convo = client.get(f"/api/codirector/conversations/{pid}").json()
    ids = {m.get("id") for m in convo["messages"]}
    assert f"tool-call-{rid}-system.status" in ids
    assert f"tool-result-{rid}-system.status" in ids


def test_export_import_roundtrip_events(client) -> None:
    project = _create_project(client, "wave-d-export")
    pid = project["id"]

    u1 = _user_event("export me", message_id="exp-u1")
    a1 = _assistant_event("saved", message_id="exp-a1")
    _append(client, pid, u1)
    _append(client, pid, a1)

    export_res = client.get(f"/api/codirector/projects/{pid}/memory/export")
    assert export_res.status_code == 200
    bundle = export_res.json()
    assert bundle["projectId"] == pid
    assert len(bundle["conversation"]["rawEvents"]) >= 2
    assert bundle["revision"] >= 2

    project2 = _create_project(client, "wave-d-import-target")
    pid2 = project2["id"]

    import_res = client.post(
        f"/api/codirector/projects/{pid2}/memory/import",
        json={"bundle": bundle},
    )
    assert import_res.status_code == 200, import_res.text
    imported = import_res.json()
    assert imported["appendedCount"] >= 2

    convo2 = client.get(f"/api/codirector/conversations/{pid2}").json()
    ids = {m.get("id") for m in convo2["messages"]}
    assert "exp-u1" in ids
    assert "exp-a1" in ids

    import_res2 = client.post(
        f"/api/codirector/projects/{pid2}/memory/import",
        json={"bundle": bundle},
    )
    assert import_res2.status_code == 200
    assert import_res2.json()["duplicateCount"] >= 2


def test_audit_healthy(client) -> None:
    project = _create_project(client, "wave-e-audit")
    pid = project["id"]
    _append(client, pid, _user_event("audit check"))
    _append(client, pid, _assistant_event("ok"))

    res = client.get(f"/api/codirector/conversations/{pid}/audit")
    assert res.status_code == 200
    audit = res.json()
    assert audit["healthy"] is True
    assert audit["sequenceMonotonic"] is True
    assert audit["uniqueMessageIds"] is True
    assert audit["revisionPresent"] is True
    assert audit["eventCount"] == 2
    assert audit["foldCount"] == 2

    repair = client.post(f"/api/codirector/conversations/{pid}/repair/rebuild-fold")
    assert repair.status_code == 200
    assert repair.json()["healthy"] is True


def test_revision_endpoint(client) -> None:
    project = _create_project(client, "wave-c-revision")
    pid = project["id"]
    _append(client, pid, _user_event("rev"))

    res = client.get(f"/api/codirector/conversations/{pid}/revision")
    assert res.status_code == 200
    body = res.json()
    assert body["projectId"] == pid
    assert body["revision"] >= 1


def _create_project_via_db(db, name: str) -> Project:
    project = Project(id=str(uuid.uuid4()), name=name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _append_via_db(db, project_id: str, event: dict) -> None:
    append_events(
        db,
        project_id,
        [
            EventInput(
                role=event["role"],
                content=event.get("content", ""),
                event_type=event.get("event_type", "message"),
                message_id=event.get("message_id"),
                client_request_id=event.get("client_request_id"),
                tool_id=event.get("tool_id"),
                tool_arguments=event.get("tool_arguments"),
                tool_result=event.get("tool_result"),
                request_id=event.get("request_id"),
                actor=event.get("actor", "user"),
            )
        ],
    )


def test_append_tool_event_produces_tool_call_and_result() -> None:
    db = next(get_db())
    try:
        project = _create_project_via_db(db, "tool-event-unit")
        pid = project.id
        rid = "unit-req-1"
        append_tool_event(
            db,
            pid,
            request_id=rid,
            tool_id="system.status",
            arguments={"scope": "project"},
            result={"status": "ok"},
        )
        folded = fold_events(db, pid)
        ids = {m.get("id") for m in folded}
        assert f"tool-call-{rid}-system.status" in ids
        assert f"tool-result-{rid}-system.status" in ids
        audit = audit_conversation(db, pid)
        assert audit["eventCount"] == 2
        assert rebuild_fold(db, pid)["healthy"] is True
    finally:
        db.close()


def test_audit_and_repair_unit() -> None:
    db = next(get_db())
    try:
        project = _create_project_via_db(db, "audit-unit")
        pid = project.id
        _append_via_db(db, pid, _user_event("one"))
        _append_via_db(db, pid, _assistant_event("two"))
        audit = audit_conversation(db, pid)
        assert audit["healthy"] is True
        assert audit["foldCount"] == 2
        assert rebuild_fold(db, pid)["eventCount"] == 2
    finally:
        db.close()
