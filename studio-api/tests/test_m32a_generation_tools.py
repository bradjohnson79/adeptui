"""M3.2a generation tools — catalog, chroma, scriptwriter, lineage, delight block."""

from __future__ import annotations

import io

import pytest
from PIL import Image


@pytest.fixture(autouse=True)
def _e2e_on(monkeypatch):
    monkeypatch.setenv("STUDIO_E2E", "1")


def _mk_project(client):
    res = client.post("/api/projects", json={"name": "M32a Tools"})
    assert res.status_code == 200
    return res.json()


def _upload_green(client, project_id: str) -> str:
    im = Image.new("RGB", (64, 64), (0, 220, 0))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    buf.seek(0)
    res = client.post(
        f"/api/projects/{project_id}/assets",
        files={"file": ("green.png", buf, "image/png")},
        data={"tag": "green_screen", "kind": "image"},
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_catalog_and_categories(client):
    res = client.get("/api/generation-tools/catalog")
    assert res.status_code == 200
    body = res.json()
    assert body["categories"]
    ids = {t["id"] for t in body["tools"]}
    assert "image.upscale" in ids
    assert "image.delighting" in ids
    assert "scriptwriter" in ids
    assert "brand.studio" not in ids


def test_delighting_blocked(client):
    p = _mk_project(client)
    st = client.get("/api/generation-tools/image.delighting/status")
    assert st.json()["status"] == "BLOCKED"
    run = client.post(
        f"/api/projects/{p['id']}/generation-tools/run",
        json={"toolId": "image.delighting", "sourceAssetId": "x"},
    )
    assert run.status_code == 503


def test_chroma_key_non_destructive(client):
    p = _mk_project(client)
    src = _upload_green(client, p["id"])
    run = client.post(
        f"/api/projects/{p['id']}/generation-tools/run",
        json={"toolId": "image.chroma_key", "sourceAssetId": src, "keyColor": "green"},
    )
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["ok"] is True
    assert body["parentAssetId"] == src
    assert body["assetId"] != src
    lib = client.get(f"/api/projects/{p['id']}/library")
    ids = {a["id"] for a in lib.json().get("items", [])}
    assert src in ids
    assert body["assetId"] in ids


def test_scriptwriter_treatment(client):
    p = _mk_project(client)
    run = client.post(
        f"/api/projects/{p['id']}/generation-tools/run",
        json={
            "toolId": "scriptwriter",
            "documentType": "treatment",
            "prompt": "A hitchhiker finds a portal",
            "title": "Portal Hitch",
        },
    )
    assert run.status_code == 200, run.text
    body = run.json()
    assert "TREATMENT" in body["text"]
    assert body["assetId"]


def test_image_upscale_e2e_lineage(client):
    p = _mk_project(client)
    src = _upload_green(client, p["id"])
    run = client.post(
        f"/api/projects/{p['id']}/generation-tools/run",
        json={"toolId": "image.upscale", "sourceAssetId": src},
    )
    assert run.status_code == 200, run.text
    body = run.json()
    assert body.get("jobId") or body.get("assetId")
    assert body.get("parentAssetId") == src


def test_codirector_generation_tools_bound():
    from app.codirector.tools.registry import _READ_HANDLERS, _MUTATION_HANDLERS

    assert "get_generation_tools_catalog" in _READ_HANDLERS
    assert "propose_script_document" in _MUTATION_HANDLERS
    assert "propose_music_generate" in _MUTATION_HANDLERS


def test_brand_studio_is_retired_from_generation_tools(client):
    catalog = client.get("/api/generation-tools/catalog")
    assert catalog.status_code == 200, catalog.text
    ids = [tool["id"] for tool in catalog.json().get("tools", [])]
    assert "brand.studio" not in ids
    p = _mk_project(client)
    run = client.post(
        f"/api/projects/{p['id']}/generation-tools/run",
        json={"toolId": "brand.studio", "prompt": "retired"},
    )
    assert run.status_code == 410, run.text
