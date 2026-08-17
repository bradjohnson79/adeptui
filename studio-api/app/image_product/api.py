"""FastAPI routes for M42 Wave 3/4 Image Product."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import Project, get_db
from . import collections as collections_mod
from . import history as history_mod
from . import kontext as kontext_mod
from . import masks as masks_mod
from . import presets as presets_mod
from . import recipes as recipes_mod
from . import references as references_mod
from . import versions as versions_mod
from .compile import compile_image_request
from .edit_compile import compile_edit_request
from .edit_recommend import recommend_edit
from .edit_service import enqueue_edit, enqueue_edit_batch
from .production_gate import evaluate_image_wave3_gate, evaluate_image_wave4_gate
from .prompt_intel import expand_prompt
from .recommend import recommend_image_family
from .service import generate_images

router = APIRouter(prefix="/image-product", tags=["image-product"])


def _require_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("/gate")
def wave3_gate() -> dict[str, Any]:
    return evaluate_image_wave3_gate()


@router.get("/gate/wave4")
def wave4_gate() -> dict[str, Any]:
    return evaluate_image_wave4_gate()


@router.post("/recommend")
def recommend(body: dict[str, Any]) -> dict[str, Any]:
    return recommend_image_family(
        prompt=str(body.get("prompt") or ""),
        purpose=str(body.get("purpose") or ""),
        operation=str(body.get("operation") or "image.generate"),
        model_family_preference=body.get("modelFamilyPreference") or body.get("model"),
        quality=str(body.get("quality") or "standard"),
        style=body.get("style") or body.get("visualStyle"),
    )


@router.post("/expand-prompt")
def expand_prompt_route(body: dict[str, Any]) -> dict[str, Any]:
    return expand_prompt(
        str(body.get("prompt") or ""),
        purpose=str(body.get("purpose") or ""),
        style_hints=dict(body.get("style") or {}),
        continuity_constraints=list(body.get("continuityConstraints") or []),
        cinematography=dict(body.get("cinematography") or {}),
        lighting=dict(body.get("lighting") or {}),
        visual_language=dict(body.get("visualLanguage") or body.get("visual_language") or {}),
    )


@router.post("/compile")
def compile_route(body: dict[str, Any]) -> dict[str, Any]:
    project_id = str(body.get("projectId") or "")
    if not project_id:
        raise HTTPException(400, "projectId required")
    return compile_image_request(project_id, body)


@router.post("/generate")
def generate(body: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    project_id = str(body.get("projectId") or "")
    if not project_id:
        raise HTTPException(400, "projectId required")
    _require_project(db, project_id)
    try:
        return generate_images(db, project_id=project_id, body=body)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/projects/{project_id}/generate")
def generate_for_project(
    project_id: str, body: dict[str, Any], db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    payload = dict(body or {})
    payload["projectId"] = project_id
    try:
        return generate_images(db, project_id=project_id, body=payload)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/projects/{project_id}/presets")
def list_presets(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    return {"presets": presets_mod.list_presets(project_id)}


@router.post("/projects/{project_id}/presets")
def create_preset(project_id: str, body: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    return presets_mod.create_preset(project_id, body)


@router.patch("/projects/{project_id}/presets/{preset_id}")
def patch_preset(
    project_id: str, preset_id: str, body: dict[str, Any], db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    updated = presets_mod.update_preset(project_id, preset_id, body)
    if not updated:
        raise HTTPException(404, "Preset not found")
    return updated


@router.delete("/projects/{project_id}/presets/{preset_id}")
def delete_preset(project_id: str, preset_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    try:
        if not presets_mod.delete_preset(project_id, preset_id):
            raise HTTPException(404, "Preset not found")
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "deleted": preset_id}


@router.get("/projects/{project_id}/collections")
def list_collections(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    return {"collections": collections_mod.list_collections(project_id)}


@router.post("/projects/{project_id}/collections")
def create_collection(
    project_id: str, body: dict[str, Any], db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    return collections_mod.create_collection(
        project_id, str(body.get("name") or "Untitled"), body.get("assetIds")
    )


@router.patch("/projects/{project_id}/collections/{collection_id}")
def patch_collection(
    project_id: str, collection_id: str, body: dict[str, Any], db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    updated = collections_mod.update_collection(project_id, collection_id, body)
    if not updated:
        raise HTTPException(404, "Collection not found")
    return updated


@router.delete("/projects/{project_id}/collections/{collection_id}")
def delete_collection(
    project_id: str, collection_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    if not collections_mod.delete_collection(project_id, collection_id):
        raise HTTPException(404, "Collection not found")
    return {"ok": True, "deleted": collection_id}


@router.post("/projects/{project_id}/collections/{collection_id}/assets")
def add_collection_assets(
    project_id: str, collection_id: str, body: dict[str, Any], db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    updated = collections_mod.add_assets(project_id, collection_id, list(body.get("assetIds") or []))
    if not updated:
        raise HTTPException(404, "Collection not found")
    return updated


@router.get("/projects/{project_id}/references")
def list_refs(
    project_id: str,
    type: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    return {"references": references_mod.list_references(project_id, type=type)}


@router.post("/projects/{project_id}/references")
def create_ref(project_id: str, body: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    return references_mod.create_reference(
        project_id,
        type=str(body.get("type") or "style"),
        display_name=str(body.get("displayName") or ""),
        source_images=list(body.get("sourceImages") or body.get("source_images") or []),
        continuity_tags=list(body.get("continuityTags") or []),
        identity_registry_ref=body.get("identityRegistryRef"),
        metadata=dict(body.get("metadata") or {}),
    )


@router.patch("/projects/{project_id}/references/{reference_id}")
def patch_ref(
    project_id: str, reference_id: str, body: dict[str, Any], db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    updated = references_mod.update_reference(project_id, reference_id, body)
    if not updated:
        raise HTTPException(404, "Reference not found")
    return updated


@router.delete("/projects/{project_id}/references/{reference_id}")
def delete_ref(
    project_id: str, reference_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    if not references_mod.delete_reference(project_id, reference_id):
        raise HTTPException(404, "Reference not found")
    return {"ok": True, "deleted": reference_id}


@router.post("/projects/{project_id}/references/bridge")
def bridge_ref(project_id: str, body: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    """Bridge character_identity / library asset into ReferenceAsset."""
    _require_project(db, project_id)
    return references_mod.bridge_from_asset(
        project_id,
        asset_id=str(body.get("assetId") or ""),
        role=str(body.get("role") or body.get("type") or "style"),
        display_name=str(body.get("displayName") or ""),
        identity_registry_ref=body.get("identityRegistryRef"),
    )


@router.get("/projects/{project_id}/history")
def project_history(
    project_id: str, limit: int = 50, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    return history_mod.list_history(project_id, limit=limit)


@router.get("/projects/{project_id}/prompt-history")
def prompt_history(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    return {"prompts": history_mod.list_prompt_history(project_id)}


# --- Wave 4: Edit routes ---


@router.post("/edit/recommend")
def edit_recommend(body: dict[str, Any]) -> dict[str, Any]:
    return recommend_edit(
        operation=str(body.get("operation") or "image.inpaint"),
        prompt=str(body.get("prompt") or ""),
        purpose=str(body.get("purpose") or ""),
        model_family_preference=body.get("modelFamilyPreference") or body.get("model"),
        source_asset_ids=list(body.get("sourceAssetIds") or []),
        has_masks=bool(body.get("masks")),
        has_references=bool(body.get("referenceAssetIds") or body.get("referenceIds")),
        quality=str(body.get("quality") or "standard"),
    )


@router.post("/edit/compile")
def edit_compile(body: dict[str, Any]) -> dict[str, Any]:
    project_id = str(body.get("projectId") or "")
    if not project_id:
        raise HTTPException(400, "projectId required")
    try:
        return compile_edit_request(project_id, body)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/edit/enqueue")
def edit_enqueue(body: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    project_id = str(body.get("projectId") or "")
    if not project_id:
        raise HTTPException(400, "projectId required")
    _require_project(db, project_id)
    try:
        return enqueue_edit(db, project_id, body)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/edit/batch")
def edit_batch(body: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    project_id = str(body.get("projectId") or "")
    if not project_id:
        raise HTTPException(400, "projectId required")
    _require_project(db, project_id)
    try:
        return enqueue_edit_batch(db, project_id, body)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/projects/{project_id}/recipes")
def list_recipes(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    return {"recipes": recipes_mod.list_recipes(project_id)}


@router.post("/projects/{project_id}/recipes")
def create_recipe(project_id: str, body: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    return recipes_mod.create_recipe(project_id, body)


@router.patch("/projects/{project_id}/recipes/{recipe_id}")
def patch_recipe(
    project_id: str, recipe_id: str, body: dict[str, Any], db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    try:
        updated = recipes_mod.update_recipe(project_id, recipe_id, body)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not updated:
        raise HTTPException(404, "Recipe not found")
    return updated


@router.delete("/projects/{project_id}/recipes/{recipe_id}")
def delete_recipe(project_id: str, recipe_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    try:
        if not recipes_mod.delete_recipe(project_id, recipe_id):
            raise HTTPException(404, "Recipe not found")
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "deleted": recipe_id}


@router.post("/projects/{project_id}/masks")
def create_mask(project_id: str, body: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    source_asset_id = str(body.get("sourceAssetId") or "")
    if not source_asset_id:
        raise HTTPException(400, "sourceAssetId required")
    try:
        return masks_mod.save_mask(
            project_id,
            source_asset_id=source_asset_id,
            png_bytes=body.get("pngBytes"),
            png_base64=body.get("pngBase64") or body.get("data"),
            path=body.get("path"),
            role=str(body.get("role") or "include"),
            dimensions=body.get("dimensions"),
            creator=str(body.get("creator") or "user"),
            metadata=dict(body.get("metadata") or {}),
        )
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/projects/{project_id}/masks")
def list_masks(
    project_id: str,
    sourceAssetId: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    return {"masks": masks_mod.list_masks(project_id, source_asset_id=sourceAssetId)}


@router.get("/projects/{project_id}/masks/{mask_id}")
def get_mask(project_id: str, mask_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    rec = masks_mod.get_mask(project_id, mask_id)
    if not rec:
        raise HTTPException(404, "Mask not found")
    return rec


@router.delete("/projects/{project_id}/masks/{mask_id}")
def delete_mask(project_id: str, mask_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    if not masks_mod.delete_mask(project_id, mask_id):
        raise HTTPException(404, "Mask not found")
    return {"ok": True, "deleted": mask_id}


@router.get("/projects/{project_id}/versions")
def get_versions(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    return versions_mod.get_tree(project_id)


@router.post("/projects/{project_id}/versions")
def create_version(project_id: str, body: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    source_asset_id = str(body.get("sourceAssetId") or "")
    if not source_asset_id:
        raise HTTPException(400, "sourceAssetId required")
    try:
        if body.get("branchFromVersionId"):
            return versions_mod.branch(
                project_id,
                str(body["branchFromVersionId"]),
                name=str(body.get("name") or "Branch"),
                state=str(body.get("state") or "Draft"),
            )
        return versions_mod.create_version(
            project_id,
            source_asset_id=source_asset_id,
            parent_version_id=body.get("parentVersionId"),
            image_edit_intent_id=body.get("imageEditIntentId"),
            output_asset_id=body.get("outputAssetId"),
            name=str(body.get("name") or "Edit"),
            state=str(body.get("state") or "Draft"),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/projects/{project_id}/versions/{version_id}")
def patch_version(
    project_id: str, version_id: str, body: dict[str, Any], db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    try:
        if body.get("markMaster"):
            updated = versions_mod.mark_master(project_id, version_id)
        elif body.get("reviewNote"):
            note = dict(body["reviewNote"])
            updated = versions_mod.add_review_note(
                project_id,
                version_id,
                author=str(note.get("author") or "user"),
                text=str(note.get("text") or ""),
            )
        elif body.get("state"):
            updated = versions_mod.set_state(project_id, version_id, str(body["state"]))
        else:
            raise HTTPException(400, "state, reviewNote, or markMaster required")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not updated:
        raise HTTPException(404, "Version not found")
    return updated


@router.post("/projects/{project_id}/kontext/session")
def kontext_create_session(
    project_id: str, body: dict[str, Any], db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    source_asset_id = str(body.get("sourceAssetId") or "")
    if not source_asset_id:
        raise HTTPException(400, "sourceAssetId required")
    return kontext_mod.create_session(
        project_id, source_asset_id=source_asset_id, metadata=dict(body.get("metadata") or {})
    )


@router.post("/projects/{project_id}/kontext/session/{session_id}/turn")
def kontext_add_turn(
    project_id: str,
    session_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    try:
        return kontext_mod.add_turn(
            project_id,
            session_id,
            role=str(body.get("role") or "user"),
            text=str(body.get("text") or ""),
            edit_intent_id=body.get("editIntentId"),
            output_asset_id=body.get("outputAssetId"),
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/families")
def families() -> dict[str, Any]:
    """Family readiness for Generate Studio selector (includes qwen2512)."""
    try:
        from ..image_studio.providers import family_catalog

        return {"families": family_catalog()}
    except Exception:
        from .recommend import _family_status, _estimates, _executable

        out = []
        for fam in ("qwen2512", "zimage", "flux", "qwen", "imagen"):
            status = _family_status(fam)
            out.append(
                {
                    "family": fam,
                    "status": status,
                    "executable": _executable(fam),
                    "estimates": _estimates(fam),
                    "label": {
                        "qwen2512": "Qwen-Image-2512",
                        "zimage": "ZImage",
                        "flux": "FLUX",
                        "qwen": "Qwen (legacy)",
                        "imagen": "Imagen",
                    }.get(fam, fam),
                }
            )
        return {"families": out}
