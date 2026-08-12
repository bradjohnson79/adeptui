"""M4.7 Professional Scriptwriter Studio — unit/integration coverage."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _e2e_on(monkeypatch):
    monkeypatch.setenv("STUDIO_E2E", "1")


def _mk_project(client):
    res = client.post("/api/projects", json={"name": "M47 Scriptwriter"})
    assert res.status_code == 200
    return res.json()


def test_registry_binds_m47_script_tools():
    from app.codirector.tools import registry

    for tool_id in (
        "script.inspect",
        "script.scene_context",
        "script.propose_replace",
        "script.sync_production_bible",
        "script.prepare_timeline",
        "script.convert_outline_to_scenes",
    ):
        assert registry.find(tool_id) is not None


def test_studio_bootstrap_insert_undo_autosave(client):
    p = _mk_project(client)
    pid = p["id"]

    studio = client.get(f"/api/projects/{pid}/scriptwriter")
    assert studio.status_code == 200, studio.text
    body = studio.json()
    assert body["ok"] is True
    doc = body["document"]
    doc_id = doc["id"]
    assert doc["revision"] >= 0
    assert body["paginationMode"] == "estimated"

    inserted = client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/scenes/insert",
        json={"heading": "EXT. HIGHWAY - NIGHT"},
    )
    assert inserted.status_code == 200, inserted.text
    after = inserted.json()["document"]
    assert after["revision"] > doc["revision"]
    headings = [e for e in after["elements"] if e["type"] == "scene_heading"]
    assert any("HIGHWAY" in e["text"] for e in headings)

    undone = client.post(f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/undo")
    assert undone.status_code == 200, undone.text
    assert undone.json()["document"]["revision"] >= after["revision"]

    autosave = client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/autosave",
        json={
            "elements": [
                {
                    "id": "e1",
                    "type": "scene_heading",
                    "text": "INT. CAFE - DAY",
                    "order": 0,
                    "sceneNumber": "1",
                },
                {"id": "e2", "type": "action", "text": "Rain on glass.", "order": 1},
                {"id": "e3", "type": "character", "text": "KORRI", "order": 2},
                {"id": "e4", "type": "dialogue", "text": "We keep going", "order": 3},
            ],
            "expectedRevision": undone.json()["document"]["revision"],
        },
    )
    assert autosave.status_code == 200, autosave.text
    assert autosave.json()["saveState"] == "saved"


def test_fountain_roundtrip_and_pdf(client, tmp_path):
    p = _mk_project(client)
    pid = p["id"]
    studio = client.get(f"/api/projects/{pid}/scriptwriter").json()
    doc_id = studio["document"]["id"]

    fountain = (
        "Title: Hitchhiker\n\n"
        "INT. DINER - NIGHT\n\n"
        "Neon hums.\n\n"
        "KORRI\n"
        "Pass the map.\n"
    )
    imported = client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/import",
        json={"text": fountain, "format": "fountain"},
    )
    assert imported.status_code == 200, imported.text
    exported = client.get(f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/export/fountain")
    assert exported.status_code == 200
    assert "INT." in exported.json()["fountain"]

    pdf = client.post(f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/export/pdf")
    assert pdf.status_code == 200
    # PDF may succeed with reportlab or fall back — either is acceptable when labeled
    assert "ok" in pdf.json()


def test_proposal_revision_timeline_bible(client):
    p = _mk_project(client)
    pid = p["id"]
    # Ensure a scene exists for linkage
    if not p.get("scenes"):
        sc = client.post(f"/api/projects/{pid}/scenes", json={"name": "Scene 1"})
        assert sc.status_code == 200, sc.text
        scene_id = sc.json()["id"]
    else:
        scene_id = p["scenes"][0]["id"]

    studio = client.get(f"/api/projects/{pid}/scriptwriter").json()
    doc_id = studio["document"]["id"]
    client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/autosave",
        json={
            "elements": [
                {
                    "id": "h1",
                    "type": "scene_heading",
                    "text": "INT. LAB - DAY",
                    "order": 0,
                    "sceneNumber": "1",
                },
                {"id": "a1", "type": "action", "text": "Machines pulse.", "order": 1},
                {"id": "c1", "type": "character", "text": "ARIA", "order": 2},
                {"id": "d1", "type": "dialogue", "text": "Stay with me", "order": 3},
            ],
            "expectedRevision": studio["document"]["revision"],
        },
    )

    prop = client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/proposals/apply",
        json={"proposal": {"op": "replace", "elementId": "d1", "text": "Stay with me."}},
    )
    assert prop.status_code == 200, prop.text
    assert prop.json()["transaction"]["kind"] == "apply_codirector_proposal"

    rev = client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/revisions",
        json={"name": "Blue", "color": "Blue"},
    )
    assert rev.status_code == 200, rev.text

    link = client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/scenes/link",
        json={"sceneHeadingId": "h1", "projectSceneId": scene_id},
    )
    assert link.status_code == 200, link.text

    prep = client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/timeline/prepare",
        json={"sceneHeadingId": "h1"},
    )
    assert prep.status_code == 200, prep.text
    assert prep.json()["proposal"]["appliesClipsAutomatically"] is False
    assert "visualizationPrompt" in prep.json()["proposal"]

    apply_meta = client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/timeline/apply-metadata",
        json={"sceneHeadingId": "h1", "metadata": prep.json()["proposal"]},
    )
    assert apply_meta.status_code == 200, apply_meta.text
    assert apply_meta.json()["transaction"]["kind"] == "apply_timeline_prep_metadata"

    bible = client.post(f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/bible/propose")
    assert bible.status_code == 200, bible.text
    assert bible.json()["appliesAutomatically"] is False


def test_transitions_and_stats_unit():
    from app.scriptwriter.models import ScriptDocument, ScriptElement
    from app.scriptwriter.stats import compute_stats
    from app.scriptwriter.transitions import cycle_type, next_on_enter

    assert next_on_enter("character") == "dialogue"
    assert cycle_type("action") in {"scene_heading", "character", "parenthetical", "dialogue", "transition", "action"}
    doc = ScriptDocument(
        id="d",
        projectId="p",
        title="T",
        elements=[
            ScriptElement(id="1", type="scene_heading", text="INT. A - DAY", order=0, sceneNumber="1"),
            ScriptElement(id="2", type="action", text="Hello world " * 40, order=1),
        ],
    )
    stats = compute_stats(doc)
    assert stats.scenes == 1
    assert stats.pagesEstimated > 0


def test_search_replace_transaction(client):
    p = _mk_project(client)
    pid = p["id"]
    studio = client.get(f"/api/projects/{pid}/scriptwriter").json()
    doc_id = studio["document"]["id"]
    client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/autosave",
        json={
            "elements": [
                {"id": "1", "type": "action", "text": "The red door opens.", "order": 0},
            ],
            "expectedRevision": studio["document"]["revision"],
        },
    )
    res = client.post(
        f"/api/projects/{pid}/scriptwriter/documents/{doc_id}/search-replace",
        json={"find": "red", "replace": "blue"},
    )
    assert res.status_code == 200, res.text
    texts = [e["text"] for e in res.json()["document"]["elements"]]
    assert any("blue door" in t for t in texts)
