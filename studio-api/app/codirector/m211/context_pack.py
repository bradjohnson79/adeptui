"""Assemble advise-only production intelligence context packs."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..bible import service as bible_service
from ..bible.context_retrieval import ContextRetrievalService
from .memory import ProductionMemoryStore

try:
    from ..m212.flags import adaptive_learning_enabled
    from ..m212.lessons import LessonStore
    from ..m212.bridge import active_lessons_as_learning_block
    from ..m212 import strategy as m212_strategy
except Exception:  # pragma: no cover
    adaptive_learning_enabled = lambda: False  # type: ignore
    LessonStore = None  # type: ignore
    active_lessons_as_learning_block = None  # type: ignore
    m212_strategy = None  # type: ignore


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

    active_lessons: list = []
    strategy_pack = None
    lessons_block = ""
    if adaptive_learning_enabled() and LessonStore is not None:
        try:
            active_lessons = LessonStore.list_active_for_context(
                db, project_id=project_id, limit=40
            )
            if active_lessons_as_learning_block is not None:
                lessons_block = active_lessons_as_learning_block(active_lessons)
            if m212_strategy is not None:
                strategy_pack = m212_strategy.get_active_pack(db)
        except Exception as exc:  # noqa: BLE001
            active_lessons = [{"error": str(exc)[:200]}]

    return {
        "projectId": project_id,
        "sceneId": scene_id,
        "userBrief": user_brief,
        "bible": bible_payload,
        "memory": memory_items,
        "scene": scene_payload,
        "activeLessons": active_lessons,
        "activeLessonsBlock": lessons_block,
        "strategyPack": strategy_pack,
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
