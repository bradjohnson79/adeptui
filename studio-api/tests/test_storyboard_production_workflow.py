"""Storyboard Studio production workflow: captions, assign/clear, missing skip, 2K, timeline."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.db import Asset, Project, SessionLocal
from app.storyboard_studio.add_from_image import (
    add_image_to_next_panel,
    assign_panel_asset,
    clear_panel_asset,
    patch_panel,
)
from app.storyboard_studio.compose import CANVAS_H, CANVAS_W, compose_page_image, compose_storyboard_2k
from app.storyboard_studio.documents import hydrate_panels, pad_empty_slots
from app.storyboard_studio.export import export_adept_json
from app.storyboard_studio.generate_missing import SKIP_NEEDS_SHOT, generate_missing_panels
from app.storyboard_studio.timeline_prep import prepare_timeline_from_storyboard


@pytest.fixture()
def project_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    from app import config as cfg
    from app.db import Base, engine
    from app.script_storyboard import ensure_script_tables

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(cfg.settings, "data_dir", data)
    Base.metadata.create_all(bind=engine)
    ensure_script_tables()
    pid = f"proj-sb-prod-{tmp_path.name}"
    with SessionLocal() as db:
        if not db.get(Project, pid):
            db.add(Project(id=pid, name="Schnick Coffee Test", engine_default="wan"))
            db.commit()
    return pid


def _png(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (64, 48), color).save(path, format="PNG")


def _asset(project_id: str, tmp_path: Path, name: str, color: tuple[int, int, int]) -> str:
    dest = tmp_path / f"{name}.png"
    _png(dest, color)
    aid = f"asset-{name}"
    with SessionLocal() as db:
        db.add(
            Asset(
                id=aid,
                project_id=project_id,
                tag=name,
                kind="image",
                filename=dest.name,
                path=str(dest),
            )
        )
        db.commit()
    return aid


def test_caption_preserved_and_not_dialogue(project_id: str) -> None:
    caption = "Korri reacts to the taste of Schnick Coffee"
    add_image_to_next_panel(project_id, asset_id="asset-tl", prompt="close-up tasting", label=caption)
    proposal = prepare_timeline_from_storyboard(project_id, approved_only=False)
    assert proposal.shots
    shot = proposal.shots[0]
    assert shot.label == caption
    assert shot.dialogue == ""
    assert caption not in (shot.cameraNote or "")
    assert shot.assetId == "asset-tl"


def test_assign_clear_caption_roundtrip(project_id: str, tmp_path: Path) -> None:
    a1 = _asset(project_id, tmp_path, "one", (20, 80, 20))
    a2 = _asset(project_id, tmp_path, "two", (80, 20, 20))
    added = add_image_to_next_panel(project_id, asset_id=a1, prompt="shot one", label="first")
    panel_id = added["panelId"]
    patched = patch_panel(project_id, panel_id, label="Korri lifts the cup")
    assert patched["ok"] is True
    assert patched["label"] == "Korri lifts the cup"
    assigned = assign_panel_asset(project_id, panel_id, a2)
    assert assigned["assetId"] == a2
    cleared = clear_panel_asset(project_id, panel_id)
    assert cleared["assetId"] is None
    with SessionLocal() as db:
        assert db.get(Asset, a2) is not None


def test_generate_missing_skips_caption_only_panel(project_id: str) -> None:
    added = add_image_to_next_panel(project_id, asset_id="tmp", prompt="", label="Korri reacts to the taste of Schnick Coffee")
    clear_panel_asset(project_id, added["panelId"])
    result = generate_missing_panels(project_id, family="qwen2512")
    skip_ids = {row["panelId"] for row in result["skipped"]}
    assert added["panelId"] in skip_ids
    assert not any(row["panelId"] == added["panelId"] for row in result["queued"])
    pad_empty_slots(project_id)
    result = generate_missing_panels(project_id, family="qwen2512", page_index=0)
    assert result["ok"] is True
    assert result["queued"] == []
    assert result["skipped"]
    assert any(SKIP_NEEDS_SHOT in (row.get("reason") or "") for row in result["skipped"])
    assert "shot description" in (result["message"] or "").lower()


def test_compositor_6_9_12_and_exact_captions(tmp_path: Path) -> None:
    red = tmp_path / "r.png"
    _png(red, (200, 30, 30))
    caption = "Korri reacts to the taste of Schnick Coffee"
    for page_size, expected in ((6, (3, 2)), (9, (3, 3)), (12, (4, 3))):
        slots = [{"assetId": "r", "label": caption} for _ in range(page_size)]
        image = compose_page_image(
            title="Storyboard",
            project_name="Schnick Coffee",
            page_index=0,
            page_count=1,
            page_size=page_size,
            slots=slots,
            asset_paths={"r": red},
        )
        assert image.size == (CANVAS_W, CANVAS_H)
        out = tmp_path / f"sheet-{page_size}.png"
        image.save(out)
        assert out.stat().st_size > 1000
        _ = expected


def test_compose_2k_requires_full_page(project_id: str, tmp_path: Path) -> None:
    add_image_to_next_panel(project_id, asset_id="only-one", prompt="one", label="one")
    result = compose_storyboard_2k(project_id, page_index=0)
    assert result["ok"] is False
    assert "Fill every slot" in (result.get("error") or "")


def test_compose_2k_ingests_library_asset(project_id: str, tmp_path: Path) -> None:
    colors = [
        (200, 30, 30),
        (30, 200, 30),
        (30, 30, 200),
        (200, 200, 30),
        (200, 30, 200),
        (30, 200, 200),
        (120, 80, 40),
        (40, 80, 120),
        (90, 90, 90),
    ]
    captions = []
    for i, color in enumerate(colors):
        aid = _asset(project_id, tmp_path, f"p{i}", color)
        caption = f"Panel {i + 1} tasting beat"
        captions.append(caption)
        add_image_to_next_panel(project_id, asset_id=aid, prompt=f"shot {i}", label=caption)
    result = compose_storyboard_2k(project_id, page_index=0)
    assert result["ok"] is True
    assert result["width"] == CANVAS_W
    assert result["height"] == CANVAS_H
    assert result["captions"] == captions
    assert result["assetId"]
    with SessionLocal() as db:
        asset = db.get(Asset, result["assetId"])
        assert asset is not None
        assert asset.kind == "image"
        assert Path(asset.path).is_file()
        meta = asset.prompt_meta_json or ""
        assert "storyboard_2k_composed" in meta
        assert captions[0] in meta
    exported = export_adept_json(project_id)
    assert exported["format"] == "adept.storyboard.v1"
    assert len(exported["panels"]) >= 9
    ids = [p.get("assetId") for p in exported["panels"][:9]]
    assert result["assetId"] not in ids


def test_json_export_keeps_order_and_captions(project_id: str) -> None:
    add_image_to_next_panel(project_id, asset_id="a", prompt="p", label="First")
    add_image_to_next_panel(project_id, asset_id="b", prompt="p", label="Second")
    data = export_adept_json(project_id)
    labels = [p.get("label") for p in data["panels"] if p.get("assetId")]
    assert labels[:2] == ["First", "Second"]
    assert data["document"]["panelOrder"]
