"""Assemble advise-only production intelligence context packs."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..bible import service as bible_service
from ..bible.context_retrieval import ContextRetrievalService
from .memory import ProductionMemoryStore


def build_context_pack(
    db: Session,
    project_id: str,
    scene_id: Optional[str],
    user_brief: str,
) -> dict[str, Any]:
    """Load bible, memory, and scene context with safe fallbacks."""

    bible_payload: dict[str, Any] | None = None
    try:
        bible_out = bible_service.get_bible_out(db, project_id)
        if bible_out is not None:
            bible_payload = bible_out.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        bible_payload = {"error": str(exc)[:200], "found": False}

    memory_items: list[dict[str, Any]] = []
    try:
        memory_items = ProductionMemoryStore.search(
            db,
            project_id=project_id,
            query=user_brief[:120] if user_brief else "",
            scene_id=scene_id,
            limit=40,
        )
    except Exception as exc:  # noqa: BLE001
        memory_items = [{"error": str(exc)[:200]}]

    scene_payload: dict[str, Any] = {"found": False, "sceneId": scene_id}
    if scene_id:
        try:
            scene_payload = ContextRetrievalService.scene_context(db, project_id, scene_id)
        except Exception as exc:  # noqa: BLE001
            scene_payload = {
                "found": False,
                "sceneId": scene_id,
                "error": str(exc)[:200],
            }

    return {
        "projectId": project_id,
        "sceneId": scene_id,
        "userBrief": user_brief,
        "bible": bible_payload,
        "memory": memory_items,
        "scene": scene_payload,
        "mutationPolicy": {
            "mode": "advise-only",
            "mayMutateBible": False,
            "mayMutateTimeline": False,
            "requiresApprovalForMutations": True,
            "notes": (
                "M2.11 specialists advise only; bible/timeline mutations "
                "stay behind approval boundaries."
            ),
        },
    }
