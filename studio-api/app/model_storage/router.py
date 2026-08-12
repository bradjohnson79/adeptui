"""HTTP API — Setup → Model Storage."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import classify, store, validate

router = APIRouter(prefix="/model-storage", tags=["model-storage"])


class RootBody(BaseModel):
    category: str
    path: str


class RegisterBody(BaseModel):
    path: str = Field(..., min_length=1)
    runtimeType: Optional[str] = None
    label: Optional[str] = None
    category: str = "llm"
    importIntoLibrary: bool = False
    metadata: Optional[dict[str, Any]] = None


class ValidateBody(BaseModel):
    path: str
    runtimeType: Optional[str] = None


@router.get("")
def get_storage():
    data = store.load_model_storage()
    return {"ok": True, "mock": False, **data, "categories": list(store.ROOT_CATEGORIES)}


@router.get("/roots")
def get_roots():
    return {"ok": True, "roots": store.get_roots(), "preferredRoot": store.load_model_storage()["preferredRoot"], "mock": False}


@router.put("/roots")
def put_root(body: RootBody):
    try:
        state = store.set_root(body.category, body.path)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "mock": False, **state}


@router.get("/folders")
def list_folders():
    return {"ok": True, "folders": store.get_registered_folders(), "mock": False}


@router.post("/folders/register")
def register(body: RegisterBody):
    try:
        entry = store.register_folder(
            path=body.path,
            runtime_type=body.runtimeType,
            label=body.label,
            category=body.category,
            metadata=body.metadata,
            import_into_library=body.importIntoLibrary,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "folder": entry, "copied": bool(entry.get("imported")), "mock": False}


@router.post("/folders/{folder_id}/refresh")
def refresh(folder_id: str):
    entry = store.refresh_registration(folder_id)
    if not entry:
        raise HTTPException(404, "Registration not found")
    return {"ok": True, "folder": entry, "mock": False}


@router.delete("/folders/{folder_id}")
def unregister(folder_id: str):
    if not store.unregister_folder(folder_id):
        raise HTTPException(404, "Registration not found")
    return {"ok": True, "mock": False}


@router.post("/classify")
def classify_path(body: ValidateBody):
    return {"ok": True, "classification": classify.classify_folder(body.path), "mock": False}


@router.post("/validate")
def validate_path(body: ValidateBody):
    result = validate.validate_registration(body.path, runtime_type=body.runtimeType or "unknown")
    return {"ok": True, "validation": result, "mock": False}


@router.post("/probe")
def probe(body: ValidateBody):
    result = validate.probe_availability(body.path)
    return {"ok": True, "probe": result, "mock": False}
