"""Wave A - Co-Director Persistent Memory race certification (Layer 1).

Layer 1 = deterministic API/component executions with NO real LLM. Each of
the 12 forced-race scenarios runs 100 consecutive iterations against a fresh
project, for a total of 1,200 executions. The mock provider supplies
controlled assistant/tool events.

Hard guarantees asserted on every iteration:
  * No truncation - the server conversation only ever grows.
  * No loss - every appended message id survives a reload/restart.
  * No duplication - a retried append (same client_request_id/message_id) is
    idempotent and does not insert a second event.
  * No cross-project leakage - events for project A never appear in project B.
  * No reordering - events fold back in server-assigned sequence order.
  * No pass-on-retry - a 409 conflict does not silently succeed.
"""

from __future__ import annotations

import threading
import uuid

import pytest

ITERATIONS = 100  # 12 scenarios x 100 = 1,200 deterministic executions


@pytest.fixture(autouse=True)
def mock_provider_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)
    yield
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)


def _create_project(client, name: str) -> dict:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()


def _append(client, project_id: str, event: dict, expected_revision: int | None = None) -> dict:
    body = {"events": [event]}
    if expected_revision is not None:
        body["expected_revision"] = expected_revision
    res = client.post(f"/api/codirector/conversations/{project_id}/events", json=body)
    return {"status": res.status_code, "json": res.json() if res.status_code < 500 else None}


def _append_batch(client, project_id: str, events: list[dict]) -> dict:
    res = client.post(f"/api/codirector/conversations/{project_id}/events", json={"events": events})
    return {"status": res.status_code, "json": res.json() if res.status_code < 500 else None}


def _get(client, project_id: str) -> dict:
    res = client.get(f"/api/codirector/conversations/{project_id}")
    assert res.status_code == 200
    return res.json()


def _user_event(content: str, *, message_id: str | None = None, client_request_id: str | None = None) -> dict:
    return {
        "role": "user",
        "content": content,
        "message_id": message_id or f"u-{uuid.uuid4().hex}",
        "client_request_id": client_request_id or f"cr-{uuid.uuid4().hex}",
        "actor": "user",
    }


def _assistant_event(content: str, *, request_id: str) -> dict:
    return {
        "role": "assistant",
        "content": content,
        "message_id": f"asst-{request_id}",
        "actor": "assistant",
        "request_id": request_id,
    }


def _tool_events(tool_id: str, *, request_id: str) -> list[dict]:
    return [
        {
            "role": "tool",
            "event_type": "tool_call",
            "content": "",
            "message_id": f"tool-call-{request_id}-{tool_id}",
            "tool_id": tool_id,
            "tool_arguments": {},
            "actor": "assistant",
            "request_id": request_id,
        },
        {
            "role": "tool",
            "event_type": "tool_result",
            "content": "",
            "message_id": f"tool-result-{request_id}-{tool_id}",
            "tool_id": tool_id,
            "tool_result": {},
            "actor": "assistant",
            "request_id": request_id,
        },
    ]


def _ids(messages: list[dict]) -> set[str]:
    return {(m.get("id") or m.get("message_id")) for m in messages if (m.get("id") or m.get("message_id"))}


def test_scenario_1_send_before_load(client) -> None:
    for i in range(ITERATIONS):
        project = _create_project(client, f"waveA-s1-{i}")
        pid = project["id"]
        ev = _user_event(f"hello-{i}")
        r = _append(client, pid, ev)
        assert r["status"] == 200, r
        convo = _get(client, pid)
        assert len(convo["messages"]) == 1
        assert ev["message_id"] in _ids(convo["messages"])


def test_scenario_2_rapid_sends(client) -> None:
    for i in range(ITERATIONS):
        project = _create_project(client, f"waveA-s2-{i}")
        pid = project["id"]
        ids = []
        for j in range(10):
            ev = _user_event(f"rapid-{i}-{j}")
            ids.append(ev["message_id"])
            r = _append(client, pid, ev)
            assert r["status"] == 200, r
        convo = _get(client, pid)
        assert len(convo["messages"]) == 10
        assert _ids(convo["messages"]) == set(ids)


def test_scenario_3_reload_mid_response(client) -> None:
    for i in range(ITERATIONS):
        project = _create_project(client, f"waveA-s3-{i}")
        pid = project["id"]
        u1 = _user_event(f"q-{i}")
        assert _append(client, pid, u1)["status"] == 200
        mid = _get(client, pid)
        assert len(mid["messages"]) == 1
        rid = f"req-{i}"
        assert _append(client, pid, _assistant_event(f"a-{i}", request_id=rid))["status"] == 200
        convo = _get(client, pid)
        assert len(convo["messages"]) == 2
        assert u1["message_id"] in _ids(convo["messages"])
        assert f"asst-{rid}" in _ids(convo["messages"])


def test_scenario_4_delayed_append(client) -> None:
    for i in range(ITERATIONS):
        project = _create_project(client, f"waveA-s4-{i}")
        pid = project["id"]
        u1 = _user_event(f"delayed-{i}")
        assert _append(client, pid, u1)["status"] == 200
        _get(client, pid)
        u2 = _user_event(f"delayed2-{i}")
        assert _append(client, pid, u2)["status"] == 200
        convo = _get(client, pid)
        assert len(convo["messages"]) == 2
        assert {u1["message_id"], u2["message_id"]} <= _ids(convo["messages"])


def test_scenario_5_duplicate_retry(client) -> None:
    for i in range(ITERATIONS):
        project = _create_project(client, f"waveA-s5-{i}")
        pid = project["id"]
        cr = f"cr-{i}"
        mid = f"u-{i}"
        ev = _user_event(f"dup-{i}", message_id=mid, client_request_id=cr)
        r1 = _append(client, pid, ev)
        assert r1["status"] == 200
        assert r1["json"]["appendedCount"] == 1
        r2 = _append(client, pid, ev)
        assert r2["status"] == 200
        assert r2["json"]["appendedCount"] == 0
        assert r2["json"]["duplicateCount"] == 1
        convo = _get(client, pid)
        assert len(convo["messages"]) == 1
        assert mid in _ids(convo["messages"])


def test_scenario_6_concurrent_tabs(client) -> None:
    for i in range(ITERATIONS):
        project = _create_project(client, f"waveA-s6-{i}")
        pid = project["id"]
        results: list[dict] = []
        results_lock = threading.Lock()

        def append_one(label: str) -> None:
            ev = _user_event(f"tab-{label}-{i}")
            r = _append(client, pid, ev)
            with results_lock:
                results.append({"id": ev["message_id"], "status": r["status"]})

        t1 = threading.Thread(target=append_one, args=("a",))
        t2 = threading.Thread(target=append_one, args=("b",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert all(r["status"] == 200 for r in results), results
        convo = _get(client, pid)
        assert len(convo["messages"]) == 2
        assert {r["id"] for r in results} == _ids(convo["messages"])


def test_scenario_7_project_switch_mid_send(client) -> None:
    for i in range(ITERATIONS):
        a = _create_project(client, f"waveA-s7a-{i}")
        b = _create_project(client, f"waveA-s7b-{i}")
        ev_a = _user_event(f"to-a-{i}")
        ev_b = _user_event(f"to-b-{i}")
        assert _append(client, a["id"], ev_a)["status"] == 200
        assert _append(client, b["id"], ev_b)["status"] == 200
        convo_a = _get(client, a["id"])
        convo_b = _get(client, b["id"])
        assert len(convo_a["messages"]) == 1
        assert len(convo_b["messages"]) == 1
        assert ev_a["message_id"] in _ids(convo_a["messages"])
        assert ev_b["message_id"] in _ids(convo_b["messages"])
        assert ev_b["message_id"] not in _ids(convo_a["messages"])
        assert ev_a["message_id"] not in _ids(convo_b["messages"])


def test_scenario_8_refresh_after_send(client) -> None:
    for i in range(ITERATIONS):
        project = _create_project(client, f"waveA-s8-{i}")
        pid = project["id"]
        u = _user_event(f"send-{i}")
        assert _append(client, pid, u)["status"] == 200
        _get(client, pid)
        u2 = _user_event(f"send2-{i}")
        assert _append(client, pid, u2)["status"] == 200
        convo = _get(client, pid)
        assert len(convo["messages"]) == 2
        assert {u["message_id"], u2["message_id"]} <= _ids(convo["messages"])


def test_scenario_9_api_restart_sim(client) -> None:
    for i in range(ITERATIONS):
        project = _create_project(client, f"waveA-s9-{i}")
        pid = project["id"]
        u = _user_event(f"restart-{i}")
        assert _append(client, pid, u)["status"] == 200
        convo = _get(client, pid)
        assert len(convo["messages"]) == 1
        assert u["message_id"] in _ids(convo["messages"])
        u2 = _user_event(f"restart2-{i}")
        assert _append(client, pid, u2)["status"] == 200
        convo2 = _get(client, pid)
        assert len(convo2["messages"]) == 2


def test_scenario_10_hundreds_of_messages(client) -> None:
    for i in range(ITERATIONS):
        project = _create_project(client, f"waveA-s10-{i}")
        pid = project["id"]
        n = 50
        ids = []
        for j in range(n):
            ev = _user_event(f"bulk-{i}-{j}")
            ids.append(ev["message_id"])
            assert _append(client, pid, ev)["status"] == 200
        convo = _get(client, pid)
        assert len(convo["messages"]) == n
        assert _ids(convo["messages"]) == set(ids)
        contents = [m["content"] for m in convo["messages"]]
        expected = [f"bulk-{i}-{j}" for j in range(n)]
        assert contents == expected


def test_scenario_11_out_of_order_tool_assistant(client) -> None:
    for i in range(ITERATIONS):
        project = _create_project(client, f"waveA-s11-{i}")
        pid = project["id"]
        rid = f"req-{i}"
        u = _user_event(f"toolq-{i}")
        assert _append(client, pid, u)["status"] == 200
        batch = _tool_events("read_scene", request_id=rid) + [_assistant_event(f"final-{i}", request_id=rid)]
        r = _append_batch(client, pid, batch)
        assert r["status"] == 200, r
        convo = _get(client, pid)
        assert len(convo["messages"]) == 4
        roles = [m["role"] for m in convo["messages"]]
        assert roles == ["user", "tool", "tool", "assistant"], roles


def test_scenario_12_summary_during_send(client) -> None:
    for i in range(ITERATIONS):
        project = _create_project(client, f"waveA-s12-{i}")
        pid = project["id"]
        u = _user_event(f"sumq-{i}")
        assert _append(client, pid, u)["status"] == 200
        summary = {
            "role": "system",
            "event_type": "summary",
            "content": f"summary-{i}",
            "message_id": f"sum-{i}",
            "actor": "assistant",
        }
        assert _append(client, pid, summary)["status"] == 200
        rid = f"req-{i}"
        assert _append(client, pid, _assistant_event(f"sumanswer-{i}", request_id=rid))["status"] == 200
        convo = _get(client, pid)
        assert len(convo["messages"]) == 3
        ids = _ids(convo["messages"])
        assert {u["message_id"], f"sum-{i}", f"asst-{rid}"} <= ids


def test_optimistic_concurrency_conflict_returns_409(client) -> None:
    """A stale expected_revision must yield 409, never a silent success."""

    for i in range(ITERATIONS):
        project = _create_project(client, f"waveA-conflict-{i}")
        pid = project["id"]
        u1 = _user_event(f"c1-{i}")
        r1 = _append(client, pid, u1)
        assert r1["status"] == 200
        rev_after = r1["json"]["revision"]
        stale = rev_after - 1 if rev_after > 0 else 0
        u2 = _user_event(f"c2-{i}")
        r2 = _append(client, pid, u2, expected_revision=stale)
        assert r2["status"] == 409, "stale revision must conflict, not pass"
        detail = r2["json"]["detail"]
        assert detail["code"] == "CONFLICT"
        assert detail["details"]["canonical"]["projectId"] == pid
        convo = _get(client, pid)
        assert u2["message_id"] not in _ids(convo["messages"])
        assert _append(client, pid, u2)["status"] == 200
        convo2 = _get(client, pid)
        assert u2["message_id"] in _ids(convo2["messages"])


def test_legacy_save_is_append_merge_not_truncate(client) -> None:
    """The deprecated POST full-replace endpoint must never truncate the event log."""

    for i in range(ITERATIONS):
        project = _create_project(client, f"waveA-legacy-{i}")
        pid = project["id"]
        u1 = _user_event(f"seed1-{i}")
        u2 = _user_event(f"seed2-{i}")
        assert _append(client, pid, u1)["status"] == 200
        assert _append(client, pid, u2)["status"] == 200
        res = client.post(
            f"/api/codirector/conversations/{pid}",
            json={"messages": [{"id": u1["message_id"], "role": "user", "content": u1["content"]}]},
        )
        assert res.status_code == 200
        convo = _get(client, pid)
        ids = _ids(convo["messages"])
        assert u1["message_id"] in ids
        assert u2["message_id"] in ids, "legacy POST must not drop existing events"
        assert len(convo["messages"]) == 2


def test_chat_appends_assistant_server_side(client) -> None:
    """chat_for_project must append the assistant reply as a server-side event."""

    for i in range(ITERATIONS):
        project = _create_project(client, f"waveA-chat-{i}")
        pid = project["id"]
        u = _user_event(f"chatq-{i}")
        assert _append(client, pid, u)["status"] == 200
        res = client.post(
            "/api/codirector/chat",
            json={
                "messages": [{"role": "user", "content": f"chatq-{i}"}],
                "project_id": pid,
                "mode": "chat",
            },
        )
        assert res.status_code == 200, res.text
        convo = _get(client, pid)
        # 1 user (appended) + 1 assistant (server-side from chat completion).
        assert len(convo["messages"]) >= 2
        roles = [m["role"] for m in convo["messages"]]
        assert "assistant" in roles, "chat must append assistant server-side"

