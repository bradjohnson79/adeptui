"""Co-Director tools for Scene Prompt Template Library (same store as REST/UI).

Rules:
- list / save / load against server SQLite store (never browser).
- load returns template text and an applyProposal — NEVER silently writes Timed Prompt / scene.
- Do not conflate with set_scene_prompt (scene.prompt only).
- Exact preserve of prompt_text bytes.
"""

from __future__ import annotations

from typing import Any

from ..definitions import ToolContext, ToolPreview
from ....scene_prompt_templates import store


def _ensure() -> None:
    store.ensure_scene_prompt_template_tables()


async def list_scene_prompt_templates(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Read: list project-scoped Scene Prompt Templates (metadata + lengths; text on get/load)."""
    _ensure()
    try:
        rows = store.list_templates(ctx.db, ctx.project_id)
    except LookupError:
        return {"ok": False, "error": "PROJECT_NOT_FOUND", "templates": []}
    include_text = bool(args.get("includeText"))
    templates = [store.row_to_dict(r, include_text=include_text) for r in rows]
    return {
        "ok": True,
        "projectId": ctx.project_id,
        "count": len(templates),
        "templates": templates,
        "note": "Scene Prompt Templates are named Timed Prompt text snapshots. Independent of set_scene_prompt.",
    }


def preview_save_scene_prompt_template(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    name = str(args.get("name") or "").strip() or "Untitled template"
    prompt = args.get("promptText")
    if prompt is None:
        prompt = args.get("prompt") or ""
    prompt_text = prompt if isinstance(prompt, str) else str(prompt)
    warnings = []
    if not prompt_text:
        warnings.append("promptText is empty — template will store an empty snapshot.")
    return ToolPreview(
        summary=f'Save Scene Prompt Template "{name}" ({len(prompt_text)} chars).',
        lines=[
            f"Project: {ctx.project_id}",
            f"Name: {name}",
            f"sourceSceneId: {str(args.get('sourceSceneId') or args.get('sceneId') or '') or '(none)'}",
            f"promptText length: {len(prompt_text)} (exact preserve; no rewrite).",
            "Creates a library snapshot only — does not change the live Timed Prompt working copy.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=warnings,
    )


def apply_save_scene_prompt_template(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _ensure()
    name = str(args.get("name") or "").strip() or "Untitled template"
    prompt = args.get("promptText")
    if prompt is None:
        prompt = args.get("prompt") or ""
    prompt_text = prompt if isinstance(prompt, str) else str(prompt)
    family = str(
        args.get("generatorFamily")
        or args.get("generatorFamilyUsed")
        or ""
    )
    source_scene_id = str(args.get("sourceSceneId") or args.get("sceneId") or "")
    try:
        row = store.create_template(
            ctx.db,
            ctx.project_id,
            name=name,
            prompt_text=prompt_text,
            generator_family=family,
            generator_id=str(args.get("generatorId") or ""),
            source_scene_id=source_scene_id,
        )
    except LookupError:
        return {"ok": False, "error": "PROJECT_NOT_FOUND"}
    return {
        "ok": True,
        "created": store.row_to_dict(row, include_text=True),
        "note": "Library entry saved. Live Timed Prompt working copy was not modified.",
    }


async def load_scene_prompt_template(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Read: return template text + applyProposal. NEVER mutates the scene / Timed Prompt."""
    _ensure()
    template_id = str(args.get("templateId") or "").strip()
    if not template_id:
        return {"ok": False, "error": "TEMPLATE_ID_REQUIRED", "applied": False}
    row = store.get_template(ctx.db, ctx.project_id, template_id)
    if not row:
        return {"ok": False, "error": "TEMPLATE_NOT_FOUND", "applied": False}
    text = row.prompt_text if row.prompt_text is not None else ""
    return {
        "ok": True,
        "applied": False,
        "template": store.row_to_dict(row, include_text=True),
        "promptText": text,
        "applyProposal": {
            "action": "apply_timed_prompt_text",
            "requiresExplicitApproval": True,
            "silentApply": False,
            "summary": (
                f'Proposed apply of template "{row.name}" ({len(text)} chars) into the '
                "selected Timed Prompt working copy. Not applied by this tool."
            ),
            "promptText": text,
            "templateId": row.id,
            "templateName": row.name,
            "note": (
                "Co-Director must not silently overwrite Timed Prompt. "
                "Operator/UI applies via Inspector Load or an explicit approved mutation. "
                "Do not use set_scene_prompt for Timed Prompt segments."
            ),
        },
    }
