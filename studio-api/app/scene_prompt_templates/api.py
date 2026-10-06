"""REST CRUD for project-scoped Scene Prompt Templates."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from . import store

router = APIRouter(prefix="/projects/{project_id}/scene-prompt-templates", tags=["scene-prompt-templates"])


class CreateTemplateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    promptText: str = Field(default="")
    generatorFamily: str = Field(default="", max_length=64)
    # Mission alias accepted on write (same column as generatorFamily).
    generatorFamilyUsed: Optional[str] = Field(default=None, max_length=64)
    generatorId: str = Field(default="", max_length=128)
    sourceSceneId: str = Field(default="", max_length=36)


class UpdateTemplateBody(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    promptText: Optional[str] = None
    generatorFamily: Optional[str] = Field(default=None, max_length=64)
    generatorFamilyUsed: Optional[str] = Field(default=None, max_length=64)
    generatorId: Optional[str] = Field(default=None, max_length=128)
    sourceSceneId: Optional[str] = Field(default=None, max_length=36)


class RenameTemplateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


def _ensure() -> None:
    store.ensure_scene_prompt_template_tables()


def _family_from_body(generator_family: Optional[str], generator_family_used: Optional[str]) -> Optional[str]:
    if generator_family is not None and str(generator_family) != "":
        return str(generator_family)
    if generator_family_used is not None:
        return str(generator_family_used)
    return generator_family


@router.get("")
def list_templates(project_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    _ensure()
    try:
        rows = store.list_templates(db, project_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Project not found")
    # List includes promptText for exact Load; clients may ignore for dropdown labels.
    return [store.row_to_dict(r, include_text=True) for r in rows]


@router.get("/{template_id}")
def get_template(project_id: str, template_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _ensure()
    row = store.get_template(db, project_id, template_id)
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    return store.row_to_dict(row, include_text=True)


@router.post("", status_code=201)
def create_template(project_id: str, body: CreateTemplateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _ensure()
    family = _family_from_body(body.generatorFamily, body.generatorFamilyUsed) or ""
    try:
        # Exact preserve: body.promptText assigned verbatim (no enhance/strip).
        row = store.create_template(
            db,
            project_id,
            name=body.name,
            prompt_text=body.promptText,
            generator_family=family,
            generator_id=body.generatorId,
            source_scene_id=body.sourceSceneId,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Project not found")
    return store.row_to_dict(row, include_text=True)


@router.put("/{template_id}")
def update_template(project_id: str, template_id: str, body: UpdateTemplateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _ensure()
    family = _family_from_body(body.generatorFamily, body.generatorFamilyUsed)
    row = store.update_template(
        db,
        project_id,
        template_id,
        name=body.name,
        prompt_text=body.promptText,
        generator_family=family,
        generator_id=body.generatorId,
        source_scene_id=body.sourceSceneId,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    return store.row_to_dict(row, include_text=True)


@router.post("/{template_id}/rename")
def rename_template(project_id: str, template_id: str, body: RenameTemplateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _ensure()
    row = store.rename_template(db, project_id, template_id, body.name)
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    return store.row_to_dict(row, include_text=True)


@router.delete("/{template_id}")
def delete_template(project_id: str, template_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _ensure()
    ok = store.delete_template(db, project_id, template_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"ok": True}
