"""Review loop: Plan->Execute->Review->Critique->Revise->Approve->Archive."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

ReviewStage = Literal[
    "plan",
    "execute",
    "review",
    "critique",
    "revise",
    "approve",
    "archive",
]

REVIEW_ORDER: tuple[ReviewStage, ...] = (
    "plan",
    "execute",
    "review",
    "critique",
    "revise",
    "approve",
    "archive",
)

REVIEW_FLOW = "Plan->Execute->Review->Critique->Revise->Approve->Archive"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class ReviewLoopState:
    loop_id: str
    project_id: str
    scene_id: Optional[str]
    stage: ReviewStage = "plan"
    history: list[dict[str, Any]] = field(default_factory=list)
    pending_approvals: list[dict[str, Any]] = field(default_factory=list)
    archived: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "loopId": self.loop_id,
            "projectId": self.project_id,
            "sceneId": self.scene_id,
            "stage": self.stage,
            "flow": REVIEW_FLOW,
            "history": list(self.history),
            "pendingApprovals": list(self.pending_approvals),
            "archived": self.archived,
            "notes": list(self.notes),
        }


_LOOPS: dict[str, ReviewLoopState] = {}


class ReviewLoopService:
    @staticmethod
    def start(project_id: str, scene_id: Optional[str] = None) -> ReviewLoopState:
        state = ReviewLoopState(
            loop_id=str(uuid.uuid4()),
            project_id=project_id,
            scene_id=scene_id,
            stage="plan",
        )
        state.history.append({"stage": "plan", "at": _now(), "event": "started"})
        _LOOPS[state.loop_id] = state
        return state

    @staticmethod
    def get(loop_id: str) -> ReviewLoopState | None:
        return _LOOPS.get(loop_id)

    @staticmethod
    def advance(
        loop_id: str,
        *,
        action: str = "next",
        note: str = "",
        approval: Optional[dict[str, Any]] = None,
    ) -> ReviewLoopState:
        state = _LOOPS.get(loop_id)
        if state is None:
            raise KeyError(loop_id)
        if state.archived:
            return state

        if action == "critique":
            state.stage = "critique"
        elif action == "revise":
            state.stage = "revise"
        elif action == "approve":
            state.stage = "approve"
            if approval:
                state.pending_approvals.append(approval)
        elif action == "archive":
            state.stage = "archive"
            state.archived = True
        else:
            idx = REVIEW_ORDER.index(state.stage)
            if idx < len(REVIEW_ORDER) - 1:
                state.stage = REVIEW_ORDER[idx + 1]
                if state.stage == "archive":
                    state.archived = True

        if note:
            state.notes.append(note)
        state.history.append(
            {"stage": state.stage, "at": _now(), "event": action, "note": note}
        )
        return state

    @staticmethod
    def list_for_project(project_id: str) -> list[dict[str, Any]]:
        return [s.to_dict() for s in _LOOPS.values() if s.project_id == project_id]
