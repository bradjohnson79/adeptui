from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import service

router = APIRouter(prefix="/setup/lifecycle", tags=["setup-lifecycle"])


class CompareBody(BaseModel):
    componentIds: list[str]


class PlanBody(BaseModel):
    componentId: str
    action: str = "install"
    destinationRoot: str | None = None


class SourceApproveBody(BaseModel):
    url: str
    revision: str | None = None


class InstallBody(BaseModel):
    confirm: bool = True
    confirmDownloadModels: bool = False
    destinationRoot: str | None = None


class RecipeInstallBody(InstallBody):
    recipeId: str


class MoveBody(BaseModel):
    destinationRoot: str


@router.get("/components")
def lifecycle_components(query: str = "", group: str | None = None):
    return service.search_components(query=query, group=group)


@router.get("/components/{component_id}")
def lifecycle_component(component_id: str):
    try:
        return service.inspect_component(component_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/compare")
def lifecycle_compare(body: CompareBody):
    return service.compare_components(body.componentIds)


@router.get("/recipes")
def lifecycle_recipes():
    return {"recipes": [item.model_dump(mode="json") for item in service.list_certified_recipes()]}


@router.get("/recipes/{recipe_id}")
def lifecycle_recipe(recipe_id: str):
    recipe = service.get_recipe(recipe_id)
    if recipe is None:
        raise HTTPException(404, f"Unknown recipe: {recipe_id}")
    return recipe.model_dump(mode="json")


@router.post("/install-plan")
def lifecycle_install_plan(body: PlanBody):
    try:
        if body.action == "update":
            return service.build_update_plan(body.componentId).model_dump(mode="json")
        return service.build_install_plan(
            body.componentId,
            action=body.action,
            destination_root=body.destinationRoot,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/hardware")
def lifecycle_hardware():
    return service.inspect_hardware()


@router.get("/components/{component_id}/dependencies")
def lifecycle_dependencies(component_id: str):
    try:
        return service.inspect_dependencies(component_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/components/{component_id}/license")
def lifecycle_license(component_id: str):
    try:
        return service.inspect_license(component_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/components/{component_id}/source")
def lifecycle_source(component_id: str):
    try:
        return service.inspect_source(component_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/components/{component_id}/source/approve")
def lifecycle_approve_source(component_id: str, body: SourceApproveBody):
    try:
        return service.approve_source(component_id, body.url, revision=body.revision)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/components/{component_id}/install-job")
def lifecycle_create_install_job(component_id: str, body: InstallBody):
    try:
        return service.create_install_job(
            component_id,
            confirm=body.confirm,
            confirm_download_models=body.confirmDownloadModels,
            destination_root=body.destinationRoot,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/components/{component_id}/install")
def lifecycle_install_component(component_id: str, body: InstallBody):
    try:
        return service.install_component(
            component_id,
            confirm=body.confirm,
            confirm_download_models=body.confirmDownloadModels,
            destination_root=body.destinationRoot,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/recipes/install")
def lifecycle_install_recipe(body: RecipeInstallBody):
    try:
        return service.install_recipe(
            body.recipeId,
            confirm=body.confirm,
            confirm_download_models=body.confirmDownloadModels,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/components/{component_id}/restart")
def lifecycle_restart_runtime(component_id: str):
    try:
        return service.restart_runtime(component_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/components/{component_id}/verify")
def lifecycle_verify_component(component_id: str):
    try:
        return service.verify_component_action(component_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/components/{component_id}/calibrate")
def lifecycle_calibrate_component(component_id: str):
    try:
        return service.calibrate_component(component_id).model_dump(mode="json")
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/components/{component_id}/certify")
def lifecycle_certify_component(component_id: str):
    try:
        return service.certify_component(component_id).model_dump(mode="json")
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/components/{component_id}/certification")
def lifecycle_certification(component_id: str):
    record = service.get_certification(component_id)
    return record.model_dump(mode="json") if record else {"componentId": component_id, "certified": False}


@router.get("/components/{component_id}/updates")
def lifecycle_updates(component_id: str):
    return service.check_updates(component_id)


@router.get("/components/{component_id}/repairs")
def lifecycle_repairs(component_id: str):
    return service.list_repair_options(component_id)


@router.get("/components/{component_id}/diagnose")
def lifecycle_diagnose(component_id: str):
    return service.diagnose_failure(component_id)


@router.get("/monitor")
def lifecycle_monitor():
    return service.get_monitor_status()


@router.post("/components/{component_id}/archive")
def lifecycle_archive(component_id: str):
    return service.archive_component(component_id).model_dump(mode="json")


@router.post("/components/{component_id}/remove")
def lifecycle_remove(component_id: str):
    return service.remove_component(component_id)


@router.post("/components/{component_id}/move")
def lifecycle_move(component_id: str, body: MoveBody):
    return service.move_installation(component_id, body.destinationRoot)


@router.get("/cloud-providers")
def lifecycle_cloud_providers():
    return service.list_cloud_providers()

