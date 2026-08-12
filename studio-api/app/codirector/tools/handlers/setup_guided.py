from __future__ import annotations

from typing import Any

from app.setup.lifecycle import service as lifecycle

from ..definitions import ToolContext, ToolPreview


def _component(args: dict[str, Any]) -> str:
    return str(args.get("componentId") or args.get("component_id") or "").strip()


def _recipe(args: dict[str, Any]) -> str:
    return str(args.get("recipeId") or "").strip()


async def search_components(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.search_components(
        query=str(args.get("query") or ""),
        group=str(args.get("group") or "").strip() or None,
    )


async def inspect_component(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.inspect_component(_component(args))


async def compare_components(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    raw = args.get("componentIds") or []
    if isinstance(raw, str):
        values = [item.strip() for item in raw.split(",") if item.strip()]
    else:
        values = list(raw)
    return lifecycle.compare_components(values)


async def inspect_hardware(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.inspect_hardware()


async def inspect_dependencies(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.inspect_dependencies(_component(args))


async def inspect_license(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.inspect_license(_component(args))


async def inspect_source(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.inspect_source(_component(args))


async def build_install_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    action = str(args.get("action") or "install")
    return lifecycle.build_install_plan(
        _component(args),
        action=action,
        destination_root=str(args.get("destinationRoot") or "").strip() or None,
    ).model_dump(mode="json")


async def get_install_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    component_id = _component(args)
    return lifecycle.lifecycle_state(component_id).model_dump(mode="json")


async def diagnose_failure(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.diagnose_failure(_component(args))


async def list_repair_options(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.list_repair_options(_component(args))


async def list_recipes(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return {"recipes": [item.model_dump(mode="json") for item in lifecycle.list_certified_recipes()]}


async def inspect_recipe(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    recipe = lifecycle.get_recipe(_recipe(args))
    return recipe.model_dump(mode="json") if recipe else {"recipeId": _recipe(args), "found": False}


async def get_certification(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    component_id = _component(args)
    record = lifecycle.get_certification(component_id)
    return record.model_dump(mode="json") if record else {"componentId": component_id, "certified": False}


async def check_updates(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.check_updates(_component(args))


async def get_monitor_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    if _component(args):
        component_id = _component(args)
        state = lifecycle.lifecycle_state(component_id)
        return {
            "componentId": component_id,
            "statusLabel": state.statusLabel,
            "findings": [item.model_dump(mode="json") for item in state.monitorFindings],
        }
    return lifecycle.get_monitor_status()


def preview_approve_source(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    component_id = _component(args)
    return ToolPreview(
        summary=f"Approve verified source for {component_id}.",
        lines=[
            "Verify source URL through Source Manager",
            "Save normalized source record",
            "Assign source to component",
        ],
        resourceKind="setup_component",
        resourceId=component_id,
    )


def apply_approve_source(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.approve_source(component_id=_component(args), url=str(args.get("url") or ""), revision=args.get("revision"))


def preview_create_install_job(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    component_id = _component(args)
    plan = lifecycle.build_install_plan(component_id, action=str(args.get("action") or "install"))
    return ToolPreview(
        summary=f"Create trusted install job for {component_id}.",
        lines=plan.steps,
        resourceKind="setup_component",
        resourceId=component_id,
        warnings=plan.warnings,
    )


def apply_create_install_job(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.create_install_job(
        _component(args),
        confirm=bool(args.get("confirm", True)),
        confirm_download_models=bool(args.get("confirmDownloadModels", False)),
        destination_root=str(args.get("destinationRoot") or "").strip() or None,
    )


def preview_install_component(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    component_id = _component(args)
    plan = lifecycle.build_install_plan(component_id, action="install")
    return ToolPreview(
        summary=f"Install {component_id} through Source Manager.",
        lines=plan.steps,
        resourceKind="setup_component",
        resourceId=component_id,
        warnings=plan.warnings,
    )


def apply_install_component(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.install_component(
        _component(args),
        confirm=bool(args.get("confirm", True)),
        confirm_download_models=bool(args.get("confirmDownloadModels", False)),
        destination_root=str(args.get("destinationRoot") or "").strip() or None,
    )


def preview_install_recipe(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    recipe_id = _recipe(args)
    recipe = lifecycle.get_recipe(recipe_id)
    lines = [
        "Resolve certified recipe",
        "Create trusted install job",
        "Run install with confirmation gates",
        "Calibrate and certify after verification",
    ]
    return ToolPreview(
        summary=f"Install certified recipe {recipe_id}.",
        lines=lines,
        resourceKind="setup_recipe",
        resourceId=recipe_id,
        warnings=list(recipe.notes) if recipe else [],
    )


def apply_install_recipe(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.install_recipe(
        _recipe(args),
        confirm=bool(args.get("confirm", True)),
        confirm_download_models=bool(args.get("confirmDownloadModels", False)),
    )


def preview_link_existing_runtime(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    component_id = _component(args)
    return ToolPreview(
        summary=f"Link an existing runtime for {component_id}.",
        lines=[
            "Review selected install location",
            "Use existing trusted setup component flow",
            "Verify linked files before marking ready",
        ],
        resourceKind="setup_component",
        resourceId=component_id,
    )


def apply_link_existing_runtime(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.move_installation(_component(args), str(args.get("destinationRoot") or ""))


def preview_repair_component(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    component_id = _component(args)
    return ToolPreview(
        summary=f"Repair {component_id} with trusted actions.",
        lines=[
            "Inspect latest install job and monitor findings",
            "Run trusted repair action",
            "Re-verify install state",
        ],
        resourceKind="setup_component",
        resourceId=component_id,
    )


def apply_repair_component(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    state = lifecycle.lifecycle_state(_component(args))
    if not state.installJobId:
        raise ValueError("No install job is available to repair.")
    return lifecycle.repair_install_job(state.installJobId, str(args.get("action") or "repair"))


def preview_restart_runtime(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    component_id = _component(args)
    return ToolPreview(
        summary=f"Restart runtime for {component_id}.",
        lines=["Run trusted runtime restart action", "Probe required nodes or service health"],
        resourceKind="setup_component",
        resourceId=component_id,
    )


def apply_restart_runtime(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.restart_runtime(_component(args))


def preview_verify_component(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    component_id = _component(args)
    return ToolPreview(
        summary=f"Verify {component_id}.",
        lines=["Run existing component verifier", "Record latest health summary"],
        resourceKind="setup_component",
        resourceId=component_id,
    )


def apply_verify_component(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.verify_component_action(_component(args))


def preview_calibrate_component(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    component_id = _component(args)
    return ToolPreview(
        summary=f"Calibrate {component_id}.",
        lines=[
            "Read machine profile",
            "Record safe precision and resolution",
            "Persist calibration profile",
        ],
        resourceKind="setup_component",
        resourceId=component_id,
    )


def apply_calibrate_component(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.calibrate_component(_component(args)).model_dump(mode="json")


def preview_certify_component(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    component_id = _component(args)
    return ToolPreview(
        summary=f"Certify {component_id}.",
        lines=[
            "Verify component health",
            "Persist calibration profile",
            "Record certification against trusted recipe",
        ],
        resourceKind="setup_component",
        resourceId=component_id,
    )


def apply_certify_component(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.certify_component(_component(args)).model_dump(mode="json")


def preview_update_component(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    component_id = _component(args)
    plan = lifecycle.build_update_plan(component_id)
    return ToolPreview(
        summary=f"Update {component_id} to the latest certified recipe.",
        lines=plan.steps,
        resourceKind="setup_component",
        resourceId=component_id,
        warnings=plan.warnings,
    )


def apply_update_component(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.install_component(
        _component(args),
        confirm=bool(args.get("confirm", True)),
        confirm_download_models=bool(args.get("confirmDownloadModels", False)),
        destination_root=str(args.get("destinationRoot") or "").strip() or None,
    )


def preview_remove_component(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    component_id = _component(args)
    return ToolPreview(
        summary=f"Review removal proposal for {component_id}.",
        lines=[
            "Do not silently delete files",
            "Keep review-gated Source Manager boundary",
            "Preserve audit trail",
        ],
        resourceKind="setup_component",
        resourceId=component_id,
        warnings=["Removal remains review-gated and does not auto-delete installed files."],
    )


def apply_remove_component(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.remove_component(_component(args))


def preview_archive_component(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    component_id = _component(args)
    return ToolPreview(
        summary=f"Archive lifecycle record for {component_id}.",
        lines=["Mark certification archived", "Preserve install history and provenance"],
        resourceKind="setup_component",
        resourceId=component_id,
    )


def apply_archive_component(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.archive_component(_component(args)).model_dump(mode="json")


def preview_move_installation(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    component_id = _component(args)
    return ToolPreview(
        summary=f"Review move proposal for {component_id}.",
        lines=["Review destination", "Keep move in trusted Source Manager boundary"],
        resourceKind="setup_component",
        resourceId=component_id,
    )


def apply_move_installation(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return lifecycle.move_installation(_component(args), str(args.get("destinationRoot") or ""))

