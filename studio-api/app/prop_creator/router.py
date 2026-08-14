"""REST router for Co-Director Prop Creator Express.

Mounted at ``/api/prop-creator``. Operates on existing PropEntity records.
Does not create a second prop registry.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import Project, get_db
from .service import (
    PropCreatorError,
    approve_candidate,
    create_or_update_prop,
    delete_prop,
    generate_candidates,
    get_prop,
    list_props,
    retry_candidate,
    workspace,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prop-creator", tags=["prop-creator"])


class UpsertBody(BaseModel):
    prop_id: str = ""
    name: str = ""
    visual_style: str = ""
    description: str = ""
    reference_asset_id: str | None = None
    clear_reference: bool = False
    generator: dict[str, Any] | None = None


class GenerateBody(BaseModel):
    local_enabled: bool = True
    api_enabled: bool = False
    local_family: str = ""
    api_model: str = ""
    candidate_count: int = 4


class ApproveBody(BaseModel):
    candidate_id: str


def _project(db: Session, project_id: str) -> None:
    row = db.get(Project, project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found.")


def _err(exc: PropCreatorError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/projects/{project_id}/workspace")
def get_workspace(project_id: str, prop_id: str = "", db: Session = Depends(get_db)):
    _project(db, project_id)
    try:
        return workspace(db, project_id, prop_id=prop_id)
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.get("/projects/{project_id}/props")
def get_props(project_id: str, approved_only: bool = False, db: Session = Depends(get_db)):
    _project(db, project_id)
    return {"props": [p.model_dump() for p in list_props(db, project_id, approved_only=approved_only)]}


@router.post("/projects/{project_id}/props")
def post_prop(project_id: str, body: UpsertBody, db: Session = Depends(get_db)):
    _project(db, project_id)
    try:
        prop = create_or_update_prop(
            db,
            project_id,
            prop_id=body.prop_id,
            name=body.name,
            visual_style=body.visual_style,
            description=body.description,
            reference_asset_id=body.reference_asset_id,
            clear_reference=body.clear_reference,
            generator=body.generator,
        )
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.get("/projects/{project_id}/props/{prop_id}")
def get_one(project_id: str, prop_id: str, db: Session = Depends(get_db)):
    _project(db, project_id)
    try:
        return {"prop": get_prop(db, project_id, prop_id).model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.post("/projects/{project_id}/props/{prop_id}/generate")
def post_generate(project_id: str, prop_id: str, body: GenerateBody, db: Session = Depends(get_db)):
    _project(db, project_id)
    try:
        prop = generate_candidates(
            db,
            project_id,
            prop_id,
            local_enabled=body.local_enabled,
            api_enabled=body.api_enabled,
            local_family=body.local_family,
            api_model=body.api_model,
            candidate_count=body.candidate_count,
        )
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{project_id}/props/{prop_id}/approve")
def post_approve(project_id: str, prop_id: str, body: ApproveBody, db: Session = Depends(get_db)):
    _project(db, project_id)
    try:
        return {"prop": approve_candidate(db, project_id, prop_id, body.candidate_id).model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.post("/projects/{project_id}/props/{prop_id}/candidates/{candidate_id}/retry")
def post_retry(project_id: str, prop_id: str, candidate_id: str, db: Session = Depends(get_db)):
    _project(db, project_id)
    try:
        return {"prop": retry_candidate(db, project_id, prop_id, candidate_id).model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/projects/{project_id}/props/{prop_id}")
def delete_one(project_id: str, prop_id: str, db: Session = Depends(get_db)):
    _project(db, project_id)
    try:
        return delete_prop(db, project_id, prop_id)
    except PropCreatorError as exc:
        raise _err(exc) from exc
