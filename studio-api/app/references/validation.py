"""Validate Ingredients reference sheets and generation readiness."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from .ic_lora_status import ingredients_status
from .models import WORKFLOW_KEY


MIN_DIM = 256
MAX_SOURCES = 12
MAX_PIXEL_AREA = 4096 * 4096


def validate_image_file(path: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not path.is_file():
        return [{"level": "error", "code": "reference_sheet_missing", "message": f"Missing image: {path.name}"}]
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            w, h = img.size
            fmt = (img.format or "").lower()
    except Exception as exc:  # noqa: BLE001
        return [{"level": "error", "code": "reference_sheet_invalid", "message": f"Cannot decode image: {exc}"}]
    if fmt not in {"png", "jpeg", "jpg", "webp"}:
        issues.append({"level": "error", "code": "reference_sheet_invalid", "message": f"Unsupported format: {fmt or 'unknown'}"})
    if w < MIN_DIM or h < MIN_DIM:
        issues.append(
            {
                "level": "warning",
                "code": "reference_dimension_low",
                "message": f"{path.name} is only {w}×{h} px and may produce weak identity retention.",
            }
        )
    if w * h > MAX_PIXEL_AREA:
        issues.append(
            {
                "level": "error",
                "code": "reference_sheet_invalid",
                "message": f"{path.name} exceeds safe pixel area limits.",
            }
        )
    return issues


def validate_generation_ready(
    *,
    sheet: dict[str, Any] | None,
    source_paths: list[Path],
    model_configured_path: str | None = None,
    nodes_ok: bool = False,
    character_count: int = 0,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    status = ingredients_status(model_configured_path)
    if status.get("status") != "ready":
        code = status.get("issue_code") or "ic_lora_model_missing"
        errors.append({"level": "error", "code": code, "message": status.get("message") or "IC-LoRA model not ready"})

    if not nodes_ok:
        errors.append(
            {
                "level": "error",
                "code": "ic_lora_nodes_missing",
                "message": "Required ComfyUI IC-LoRA nodes are not available. Update ComfyUI / LTXVideo nodes.",
            }
        )

    if not sheet:
        errors.append({"level": "error", "code": "reference_sheet_missing", "message": "No reference sheet selected."})
    else:
        composite = sheet.get("composite_path") or sheet.get("composite_asset_path")
        if composite:
            for issue in validate_image_file(Path(composite)):
                (errors if issue["level"] == "error" else warnings).append(issue)
        else:
            errors.append({"level": "error", "code": "reference_sheet_invalid", "message": "Reference sheet has no composite image."})
        if not sheet.get("static_video_path") and not sheet.get("static_video_asset_id"):
            warnings.append(
                {
                    "level": "warning",
                    "code": "reference_static_video_missing",
                    "message": "Static reference video is missing; compiler will regenerate when possible.",
                }
            )

    if len(source_paths) > MAX_SOURCES:
        errors.append(
            {
                "level": "error",
                "code": "reference_sheet_invalid",
                "message": f"Too many references ({len(source_paths)}). Limit is {MAX_SOURCES}.",
            }
        )
    for path in source_paths:
        for issue in validate_image_file(path):
            (errors if issue["level"] == "error" else warnings).append(issue)
        if not path.exists():
            errors.append(
                {
                    "level": "error",
                    "code": "reference_sheet_invalid",
                    "message": f"Source asset missing: {path}",
                }
            )

    if character_count >= 7:
        warnings.append(
            {
                "level": "warning",
                "code": "reference_character_count_high",
                "message": "Seven or more character references are selected. Consider reducing to principal subjects for stronger consistency.",
            }
        )

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "workflow_key": WORKFLOW_KEY,
        "model_status": status,
    }
