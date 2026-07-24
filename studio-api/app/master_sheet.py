"""Scene Master Sheet persistence and CRUD.

Master Sheet = what exists; Spatial = where; Storyboard = how framed; Director = assembled.
Ingredients Render is one OUTPUT of structured source — never collage language in prompts.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base, Project, Scene, engine, get_db

router = APIRouter(tags=["master-sheet"])


class MasterSheetRow(Base):
    __tablename__ = "scene_master_sheets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    scene_id: Mapped[str] = mapped_column(String(36), index=True)
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    approved_authority: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[str] = mapped_column(String(32), default="v1")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


def ensure_master_sheet_tables() -> None:
    Base.metadata.create_all(bind=engine, tables=[MasterSheetRow.__table__])


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _empty(project_id: str, scene_id: str, title: str) -> dict[str, Any]:
    now = _now()
    return {
        "id": f"ms-{scene_id}",
        "project_id": project_id,
        "scene_id": scene_id,
        "title": title,
        "approved_authority": False,
        "state_id": "A",
        "states": [{"id": "A", "label": "Primary"}],
        "version": "v1",
        "versions": [],
        "ingredients": [],
        "prompt": "",
        "negative_prompt": (
            "collage, mood board, reference sheet, character sheet, grid layout, "
            "multi-panel, storyboard panels, white background, identity drift, "
            "inconsistent faces, split screen, contact sheet, blurry, low quality, watermark"
        ),
        "links": {},
        "created_at": now,
        "updated_at": now,
    }


def _build_prompts(data: dict[str, Any]) -> tuple[str, str]:
    ings = data.get("ingredients") or []
    chars = [i for i in ings if i.get("kind") == "character" and i.get("priority") != "Exclude"]
    env = [i for i in ings if i.get("kind") == "environment" and i.get("priority") != "Exclude"]
    action = [i for i in ings if i.get("kind") == "action" and i.get("priority") != "Exclude"]
    light = [i for i in ings if i.get("kind") == "lighting" and i.get("priority") != "Exclude"]
    cam = [i for i in ings if i.get("kind") == "camera" and i.get("priority") != "Exclude"]
    parts: list[str] = []
    if action:
        parts.append("; ".join(i.get("description") or i.get("label", "") for i in action))
    if chars:
        parts.append("; ".join(i.get("description") or i.get("label", "") for i in chars))
    if env:
        parts.append("in " + ", ".join(i.get("description") or i.get("label", "") for i in env))
    if light:
        parts.append(", ".join(i.get("description") or i.get("label", "") for i in light))
    if cam:
        parts.append(", ".join(i.get("description") or i.get("label", "") for i in cam))
    prompt = (data.get("prompt") or "").strip() or (
        ". ".join(p for p in parts if p) or "A complete cinematic scene with coherent characters, environment, and lighting."
    )
    neg = (data.get("negative_prompt") or "").strip() or (
        "collage, mood board, reference sheet, grid layout, white background, identity drift, blurry"
    )
    return prompt, neg


def _validate(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    ings = data.get("ingredients") or []
    if not any(i.get("kind") == "character" and i.get("priority") == "Required" for i in ings):
        issues.append({"level": "warn", "text": "No Required character ingredient"})
    if not any(i.get("kind") == "environment" for i in ings):
        issues.append({"level": "warn", "text": "No environment ingredient"})
    if not ings and not (data.get("prompt") or "").strip():
        issues.append({"level": "bad", "text": "Empty master sheet"})
    prompt = data.get("prompt") or ""
    if any(w in prompt.lower() for w in ("collage", "mood board", "reference sheet", "white background")):
        issues.append({"level": "bad", "text": "Prompt mentions collage/mood-board language"})
    return issues


class AuthorityBody(BaseModel):
    approved_authority: bool = True


@router.get("/projects/{project_id}/scenes/{scene_id}/master-sheet")
def get_master_sheet(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    row = (
        db.query(MasterSheetRow)
        .filter(MasterSheetRow.project_id == project_id, MasterSheetRow.scene_id == scene_id)
        .first()
    )
    if not row:
        data = _empty(project_id, scene_id, f"{scene.name} Master Sheet")
        if scene.prompt:
            data["prompt"] = scene.prompt
        return data
    try:
        return json.loads(row.data_json)
    except Exception:
        return _empty(project_id, scene_id, f"{scene.name} Master Sheet")


@router.put("/projects/{project_id}/scenes/{scene_id}/master-sheet")
def put_master_sheet(project_id: str, scene_id: str, body: dict[str, Any], db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")

    row = (
        db.query(MasterSheetRow)
        .filter(MasterSheetRow.project_id == project_id, MasterSheetRow.scene_id == scene_id)
        .first()
    )
    if row:
        try:
            data = json.loads(row.data_json)
        except Exception:
            data = _empty(project_id, scene_id, f"{scene.name} Master Sheet")
    else:
        data = _empty(project_id, scene_id, f"{scene.name} Master Sheet")
        row = MasterSheetRow(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scene_id=scene_id,
            data_json="{}",
        )
        db.add(row)

    if body.get("bootstrap"):
        if scene.prompt and not data.get("prompt"):
            data["prompt"] = scene.prompt
        if not data.get("ingredients"):
            data["ingredients"] = [
                {
                    "id": f"ing-{uuid.uuid4().hex[:8]}",
                    "kind": "character",
                    "label": "Lead",
                    "priority": "Required",
                    "description": "",
                },
                {
                    "id": f"ing-{uuid.uuid4().hex[:8]}",
                    "kind": "environment",
                    "label": "Location",
                    "priority": "Required",
                    "description": "",
                },
            ]
    elif body.get("patch_ingredient"):
        p = body["patch_ingredient"]
        iid = p.get("id")
        data["ingredients"] = [
            {**i, **{k: v for k, v in p.items() if k != "id"}} if i.get("id") == iid else i
            for i in data.get("ingredients") or []
        ]
    elif body.get("translate_to_spatial"):
        data.setdefault("links", {})["spatial_map_id"] = f"spatial-{scene_id}"
        data["notes_spatial"] = "Stub: positions uncertain — review in Spatial Map"
        for ing in data.get("ingredients") or []:
            if ing.get("kind") in ("character", "prop", "camera"):
                ing["uncertain"] = True
    elif body.get("sync_from_spatial"):
        data.setdefault("links", {})["spatial_sync_pending"] = True
        data["notes_spatial"] = "Sync Spatial → Master Sheet needs review"
    else:
        # Full replace of known fields
        for key in (
            "title",
            "ingredients",
            "prompt",
            "negative_prompt",
            "states",
            "state_id",
            "links",
            "version",
            "approved_authority",
        ):
            if key in body:
                data[key] = body[key]

    prompt, neg = _build_prompts(data)
    if not (data.get("prompt") or "").strip():
        data["prompt"] = prompt
    if not (data.get("negative_prompt") or "").strip():
        data["negative_prompt"] = neg
    data["updated_at"] = _now()
    data["project_id"] = project_id
    data["scene_id"] = scene_id

    row.data_json = json.dumps(data)
    row.approved_authority = 1 if data.get("approved_authority") else 0
    row.version = str(data.get("version") or "v1")
    row.updated_at = data["updated_at"]
    db.commit()
    return data


@router.get("/projects/{project_id}/master-sheets")
def list_master_sheets(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    rows = db.query(MasterSheetRow).filter(MasterSheetRow.project_id == project_id).all()
    out = []
    for row in rows:
        try:
            data = json.loads(row.data_json)
        except Exception:
            data = {"id": row.id, "scene_id": row.scene_id, "title": "Master Sheet"}
        out.append(
            {
                "id": data.get("id") or row.id,
                "scene_id": row.scene_id,
                "title": data.get("title"),
                "version": row.version,
                "approved_authority": bool(row.approved_authority),
                "updated_at": row.updated_at,
            }
        )
    return out


@router.post("/projects/{project_id}/scenes/{scene_id}/master-sheet/validate")
def validate_master_sheet(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    data = get_master_sheet(project_id, scene_id, db)
    issues = _validate(data)
    return {"ok": not any(i["level"] == "bad" for i in issues), "issues": issues}


@router.post("/projects/{project_id}/scenes/{scene_id}/master-sheet/authority")
def set_authority(project_id: str, scene_id: str, body: AuthorityBody, db: Session = Depends(get_db)):
    data = get_master_sheet(project_id, scene_id, db)
    data["approved_authority"] = body.approved_authority
    return put_master_sheet(project_id, scene_id, data, db)
