"""HTTP API for Director Visual References / IC-LoRA Ingredients."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..db import Asset, Project, get_db
from ..setup.state import load_state
from . import store
from .capabilities import reference_capabilities
from .ic_lora_status import public_resource_card
from .models import resolve_strength
from .sheet_builder import SheetPanel, build_reference_sheet
from .static_video import still_to_static_video
from .validation import validate_generation_ready

router = APIRouter(tags=["references"])


class IngredientBody(BaseModel):
    id: str | None = None
    asset_id: str
    role: str = "other"
    subject_name: str | None = None
    description: str | None = None
    priority: str = "primary"
    include: bool = True
    crop_preference: str | None = "contain"
    label: str | None = None


class BuildSheetBody(BaseModel):
    ingredient_ids: list[str] = Field(default_factory=list)
    layout: str = "auto"
    width: int = 768
    height: int = 448
    fps: int = 24
    frames: int = 121
    scene_id: str | None = None


class PresetBody(BaseModel):
    id: str | None = None
    name: str
    sheet_id: str | None = None
    reference_sheet_asset_id: str | None = None
    source_reference_ids: list[str] = Field(default_factory=list)
    subjects: list[dict[str, Any]] = Field(default_factory=list)
    strength_preset: str = "balanced"
    strength_value: float | None = None


class ReplaceIngredientBody(BaseModel):
    asset_id: str
    role: str | None = None
    subject_name: str | None = None
    rebuild_sheet: bool = True
    layout: str = "auto"


def _project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _asset_path(db: Session, asset_id: str) -> Path:
    asset = db.get(Asset, asset_id)
    if not asset or not asset.path:
        raise HTTPException(400, f"Asset not found: {asset_id}")
    path = Path(asset.path)
    if not path.is_file():
        raise HTTPException(400, f"Asset file missing: {asset_id}")
    return path


def _configured_ic_lora_path() -> str | None:
    state = load_state()
    return (state.get("model_locations") or {}).get("ltx23_ic_lora_ingredients")


@router.get("/reference-models/ltx23_ic_lora_ingredients")
def get_ingredients_model_card():
    return public_resource_card(_configured_ic_lora_path())


@router.get("/projects/{project_id}/references/capabilities")
def get_capabilities(project_id: str, db: Session = Depends(get_db)):
    project = _project(db, project_id)
    return reference_capabilities(
        configured_model_path=_configured_ic_lora_path(),
        vram_gb=getattr(project, "vram_gb", None),
    )


@router.get("/projects/{project_id}/references/ingredients")
def get_ingredients(project_id: str, db: Session = Depends(get_db)):
    _project(db, project_id)
    return {"items": store.list_ingredients(project_id)}


@router.post("/projects/{project_id}/references/ingredients")
def post_ingredient(project_id: str, body: IngredientBody, db: Session = Depends(get_db)):
    _project(db, project_id)
    _asset_path(db, body.asset_id)
    row = store.upsert_ingredient(project_id, body.model_dump())
    return row


@router.post("/projects/{project_id}/references/sheets/build")
def build_sheet(project_id: str, body: BuildSheetBody, db: Session = Depends(get_db)):
    project = _project(db, project_id)
    ingredients = store.list_ingredients(project_id)
    selected = [i for i in ingredients if i.get("id") in set(body.ingredient_ids) and i.get("include", True)]
    if not selected:
        selected = [i for i in ingredients if i.get("include", True)]
    if not selected:
        raise HTTPException(400, "No reference ingredients selected")

    panels: list[SheetPanel] = []
    source_meta = []
    for ing in selected:
        path = _asset_path(db, ing["asset_id"])
        panels.append(
            SheetPanel(
                path=path,
                role=str(ing.get("role") or "other"),
                subject_name=str(ing.get("subject_name") or ing.get("label") or ""),
                priority=str(ing.get("priority") or "primary"),
            )
        )
        source_meta.append(
            {
                "asset_id": ing["asset_id"],
                "role": ing.get("role"),
                "subject_name": ing.get("subject_name"),
                "priority": ing.get("priority") or "primary",
            }
        )

    sheet_id = str(uuid.uuid4())
    root = store.project_refs_root(project_id) / "sheets" / sheet_id
    root.mkdir(parents=True, exist_ok=True)
    png_path = root / "composite.png"
    built = build_reference_sheet(
        panels,
        layout=body.layout,
        width=body.width,
        height=body.height,
        out_path=png_path,
    )
    video_path = root / "composite_static.mp4"
    try:
        still_to_static_video(
            png_path,
            video_path,
            fps=body.fps,
            frames=body.frames,
            width=body.width,
            height=body.height,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Failed to build static reference video: {exc}") from exc

    # Persist as Assets for Library / upload path
    png_asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project.id,
        filename="reference_sheet.png",
        path=str(png_path),
        kind="image",
        tag="reference_sheet",
    )
    vid_asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project.id,
        filename="reference_sheet_static.mp4",
        path=str(video_path),
        kind="video",
        tag="reference_sheet_video",
    )
    db.add(png_asset)
    db.add(vid_asset)
    db.commit()

    sheet = {
        "id": sheet_id,
        "version": 1,
        "layout": built["layout"],
        "composite_path": str(png_path),
        "static_video_path": str(video_path),
        # Aliases consumed by queue_worker ingredients path
        "image_path": str(png_path),
        "video_path": str(video_path),
        "image_asset_id": png_asset.id,
        "video_asset_id": vid_asset.id,
        "composite_asset_id": png_asset.id,
        "static_video_asset_id": vid_asset.id,
        "source_ingredient_ids": [i["id"] for i in selected],
        "source_asset_ids": [i["asset_id"] for i in selected],
        "source_references": source_meta,
        "panels": built.get("panels") or [],
        "width": body.width,
        "height": body.height,
        "fps": body.fps,
        "frames": max(121, body.frames),
        "preview_url": f"/api/assets/{png_asset.id}/file",
    }
    return store.save_sheet(project_id, sheet)


@router.get("/projects/{project_id}/references/sheets/{sheet_id}")
def get_sheet(project_id: str, sheet_id: str, db: Session = Depends(get_db)):
    _project(db, project_id)
    sheet = store.get_sheet(project_id, sheet_id)
    if not sheet:
        raise HTTPException(404, "Sheet not found")
    return sheet


@router.post("/projects/{project_id}/references/sheets/{sheet_id}/validate")
def validate_sheet(project_id: str, sheet_id: str, db: Session = Depends(get_db)):
    _project(db, project_id)
    sheet = store.get_sheet(project_id, sheet_id)
    if not sheet:
        raise HTTPException(404, "Sheet not found")
    paths = []
    for ref in sheet.get("source_references") or []:
        try:
            paths.append(_asset_path(db, ref["asset_id"]))
        except HTTPException:
            paths.append(Path("__missing__"))
    caps = reference_capabilities(configured_model_path=_configured_ic_lora_path())
    chars = sum(1 for r in (sheet.get("source_references") or []) if r.get("role") == "character")
    return validate_generation_ready(
        sheet=sheet,
        source_paths=paths,
        model_configured_path=_configured_ic_lora_path(),
        nodes_ok=bool(caps.get("nodes_available")),
        character_count=chars,
    )


@router.get("/projects/{project_id}/references/presets")
def get_presets(project_id: str, db: Session = Depends(get_db)):
    _project(db, project_id)
    return {"items": store.list_presets(project_id)}


@router.post("/projects/{project_id}/references/presets")
def post_preset(project_id: str, body: PresetBody, db: Session = Depends(get_db)):
    _project(db, project_id)
    preset, value = resolve_strength(body.strength_preset, body.strength_value)
    payload = body.model_dump()
    payload["strength_preset"] = preset
    payload["strength_value"] = value
    return store.save_preset(project_id, payload)


@router.post("/projects/{project_id}/references/presets/{preset_id}/reuse")
def reuse_preset(project_id: str, preset_id: str, db: Session = Depends(get_db)):
    _project(db, project_id)
    try:
        cloned = store.reuse_preset(project_id, preset_id)
    except KeyError:
        raise HTTPException(404, "Preset not found")
    sheet = store.get_sheet(project_id, str(cloned.get("sheet_id") or "")) if cloned.get("sheet_id") else None
    return {
        "preset": cloned,
        "sheet": sheet,
        "reference_method": "ingredients_ic_lora",
        "strength_preset": cloned.get("strength_preset"),
        "strength_value": cloned.get("strength_value"),
        "reused_from": preset_id,
    }


@router.post("/projects/{project_id}/references/ingredients/{ing_id}/replace")
def replace_ingredient(
    project_id: str,
    ing_id: str,
    body: ReplaceIngredientBody,
    db: Session = Depends(get_db),
):
    _project(db, project_id)
    _asset_path(db, body.asset_id)
    items = store.list_ingredients(project_id)
    current = next((i for i in items if i.get("id") == ing_id), None)
    if not current:
        raise HTTPException(404, "Ingredient not found")
    old_sheet_id = current.get("sheet_id")
    old_sheet = store.get_sheet(project_id, old_sheet_id) if old_sheet_id else None
    old_snapshot = dict(old_sheet) if old_sheet else None

    updated = store.upsert_ingredient(
        project_id,
        {
            **current,
            "asset_id": body.asset_id,
            "role": body.role or current.get("role"),
            "subject_name": body.subject_name or current.get("subject_name"),
            "previous_sheet_id": old_sheet_id,
        },
    )
    new_sheet = None
    if body.rebuild_sheet:
        build = BuildSheetBody(
            ingredient_ids=[i["id"] for i in store.list_ingredients(project_id) if i.get("include", True)],
            layout=body.layout,
        )
        new_sheet = build_sheet(project_id, build, db)
        new_sheet["version"] = int((old_sheet or {}).get("version") or 0) + 1
        new_sheet["replaces_ingredient_id"] = ing_id
        new_sheet["replaces_sheet_id"] = old_sheet_id
        store.save_sheet(project_id, new_sheet)
        updated = store.upsert_ingredient(
            project_id, {**updated, "sheet_id": new_sheet["id"], "previous_sheet_id": old_sheet_id}
        )
    previous_now = store.get_sheet(project_id, old_sheet_id) if old_sheet_id else None
    return {
        "ingredient": updated,
        "sheet": new_sheet,
        "previous_sheet": previous_now,
        "previous_unchanged": bool(old_snapshot and previous_now == old_snapshot),
    }


@router.get("/projects/{project_id}/assets/{asset_id}/references-used")
def references_used(project_id: str, asset_id: str, db: Session = Depends(get_db)):
    _project(db, project_id)
    asset = db.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        raise HTTPException(404, "Asset not found")
    meta = {}
    try:
        import json

        meta = json.loads(asset.prompt_meta_json or "{}")
    except Exception:  # noqa: BLE001
        meta = {}
    refs = meta.get("ingredients_reference") or meta.get("references") or {}
    return {
        "asset_id": asset_id,
        "references": refs,
        "actions": {
            "view_references_used": True,
            "reuse_reference_setup": bool(refs.get("sheet_id") or refs.get("preset_id")),
            "open_reference_sheet": bool(refs.get("reference_sheet_asset_id")),
        },
    }
