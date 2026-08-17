"""Generate missing storyboard panels via existing image_product enqueue.

Caption is not a generation prompt. Empty slots with no shot description are skipped.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from ..db import SessionLocal
from ..script_storyboard import ScriptSegmentRow, StoryboardPanelRow, ensure_script_tables
from .documents import hydrate_panels, pad_empty_slots

GenerateFamily = Literal["qwen2512", "imagen"]

SKIP_NEEDS_SHOT = "This panel needs a shot description before an image can be generated."


def _usable_generation_prompt(row: StoryboardPanelRow, meta: dict[str, Any], db) -> str:
    prompt = (row.prompt or "").strip()
    if prompt:
        return prompt
    notes = (row.notes or "").strip()
    if notes:
        return notes
    action = str(meta.get("shotDescription") or meta.get("action") or "").strip()
    if action:
        return action
    # Only use script action when this panel is explicitly linked to it.
    if meta.get("scriptwriterActionId") and row.segment_id:
        seg = db.get(ScriptSegmentRow, row.segment_id)
        if seg:
            for candidate in (seg.action, seg.text):
                text = (candidate or "").strip()
                if text and text.lower() not in {"storyboard beat"}:
                    return text
    return ""


def generate_missing_panels(
    project_id: str,
    *,
    family: GenerateFamily = "qwen2512",
    document_id: str | None = None,
    page_index: int | None = None,
    allow_draft: bool = False,
) -> dict[str, Any]:
    if family not in {"qwen2512", "imagen"}:
        return {"ok": False, "error": "family must be qwen2512 or imagen"}
    pad_empty_slots(project_id, document_id)
    workspace = hydrate_panels(project_id, document_id)
    doc = workspace.get("document") or {}
    panels = list(workspace.get("panels") or [])
    if page_index is not None:
        panels = [p for p in panels if int(p.get("pageIndex") or 0) == int(page_index)]

    skipped: list[dict[str, Any]] = []
    queued: list[dict[str, Any]] = []
    filled_skipped = 0

    from ..image_product.service import generate_images

    ensure_script_tables()
    with SessionLocal() as db:
        for panel in panels:
            if panel.get("assetId"):
                filled_skipped += 1
                continue
            panel_id = str(panel.get("panelId") or "")
            row = db.get(StoryboardPanelRow, panel_id)
            if not row or row.project_id != project_id:
                skipped.append({"panelId": panel_id, "reason": "Panel not found."})
                continue
            try:
                meta = json.loads(row.meta_json or "{}")
            except Exception:
                meta = {}
            prompt = _usable_generation_prompt(row, meta if isinstance(meta, dict) else {}, db)
            if not prompt:
                skipped.append({"panelId": panel_id, "reason": SKIP_NEEDS_SHOT})
                continue
            body: dict[str, Any] = {
                "projectId": project_id,
                "prompt": prompt,
                "purpose": "storyboard",
                "modelFamilyPreference": family,
                "lockModelFamily": True,
                "panelId": panel_id,
                "batchSize": 1,
                "cinematic": {"category": "storyboard"},
            }
            if family == "imagen":
                body["providerId"] = "gpt-image-2-kie"
                body["modelId"] = "gpt-image-2-kie"
            if allow_draft:
                body["allowDraft"] = True
            try:
                result = generate_images(db, project_id=project_id, body=body)
            except Exception as exc:
                skipped.append({"panelId": panel_id, "reason": str(exc)})
                continue
            job_id = result.get("jobId") or ((result.get("jobs") or [{}])[0].get("jobId"))
            queued.append(
                {
                    "panelId": panel_id,
                    "jobId": job_id,
                    "family": family,
                }
            )

    creator_note = ""
    if skipped:
        n = len(skipped)
        creator_note = (
            f"{n} empty panel{'s' if n != 1 else ''} need a shot description before an image can be generated."
        )
    if queued:
        creator_note = (
            (creator_note + " " if creator_note else "")
            + f"Queued {len(queued)} missing panel{'s' if len(queued) != 1 else ''}."
        )
    if not queued and not skipped:
        creator_note = "No empty panels to generate."

    return {
        "ok": True,
        "documentId": doc.get("id"),
        "family": family,
        "queued": queued,
        "skipped": skipped,
        "filledSkipped": filled_skipped,
        "message": creator_note.strip(),
    }
