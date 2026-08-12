"""M4.8–M4.9 certification blocker unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.image_studio.providers import providers_for_mode
from app.storyboard_studio.add_from_image import (
    add_image_to_next_panel,
    replace_panel_image,
    undo_replace_panel,
)
from app.storyboard_studio.documents import ensure_document
from app.storyboard_studio.export import export_pdf_bytes
from app.storyboard_studio.timeline_prep import (
    confirm_timeline_proposal,
    prepare_timeline_from_storyboard,
)


@pytest.fixture()
def project_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    from app import config as cfg
    from app.db import Base, engine
    from app.script_storyboard import ensure_script_tables

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(cfg.settings, "data_dir", data)
    # Ensure SQL tables for panels/scenes
    Base.metadata.create_all(bind=engine)
    ensure_script_tables()
    return f"proj-m48-cert-{tmp_path.name}"


def test_replace_panel_and_undo(project_id: str) -> None:
    ensure_document(project_id, page_size=9)
    added = add_image_to_next_panel(
        project_id,
        asset_id="asset-a",
        prompt="frame one",
        scene_id="scene-12",
    )
    panel_id = added["panelId"]
    assert added.get("scriptwriterSceneId") == "scene-12"
    replaced = replace_panel_image(
        project_id,
        panel_id=panel_id,
        asset_id="asset-b",
        prompt="frame two",
        scene_id="scene-12",
    )
    assert replaced["ok"] is True
    assert replaced["assetId"] == "asset-b"
    undone = undo_replace_panel(project_id, panel_id)
    assert undone["ok"] is True
    assert undone.get("assetId") == "asset-a"


def test_timeline_confirm_creates_payload(project_id: str) -> None:
    # Need a Project row for confirm
    from app.db import Project, SessionLocal

    with SessionLocal() as db:
        if not db.get(Project, project_id):
            db.add(Project(id=project_id, name="Cert", engine_default="wan"))
            db.commit()

    ensure_document(project_id)
    add_image_to_next_panel(project_id, asset_id="asset-tl", prompt="shot", label="P1")
    proposal = prepare_timeline_from_storyboard(project_id, approved_only=False)
    assert proposal.status == "draft"
    result = confirm_timeline_proposal(project_id, proposal.id)
    assert result["ok"] is True
    assert result["createdSceneIds"]
    assets = {row["assetId"] for row in result["timelinePayload"]}
    assert "asset-tl" in assets
    assert result["proposal"]["status"] == "applied"


def test_export_pdf_returns_bytes(project_id: str) -> None:
    ensure_document(project_id)
    add_image_to_next_panel(project_id, asset_id="a1", prompt="p")
    pdf, name = export_pdf_bytes(project_id)
    assert name.endswith(".pdf")
    assert pdf[:4] == b"%PDF" or pdf[:5] == b"%PDF-"


def test_all_models_mode_lists_providers() -> None:
    result = providers_for_mode("all_models")
    assert result["mode"] == "all_models"
    assert "providers" in result
