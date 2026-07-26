"""Default M2.11 specialist orchestration DAG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DagNode:
    stage_id: str
    specialist_id: str
    label: str
    approval_boundary: bool = False
    optional: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "stageId": self.stage_id,
            "specialistId": self.specialist_id,
            "label": self.label,
            "approvalBoundary": self.approval_boundary,
            "optional": self.optional,
        }


# Default pipeline:
# Story Analyst → Bible Manager → Continuity → Director → Cinematographer
# → Sound → Music → Editor → QA → User Review
DEFAULT_PIPELINE: tuple[DagNode, ...] = (
    DagNode("story", "story-analyst", "Story Analyst"),
    DagNode("bible", "bible-manager", "Production Bible Manager", approval_boundary=True),
    DagNode("continuity", "continuity-analyst", "Continuity Supervisor", approval_boundary=True),
    DagNode("director", "director", "Director"),
    DagNode("camera", "cinematographer", "Camera Supervisor"),
    DagNode("sound", "sound-designer", "Sound Supervisor"),
    DagNode("music", "music-supervisor", "Music Supervisor"),
    DagNode("editor", "editor", "Editor"),
    DagNode("qa", "qa-reviewer", "QA Reviewer", approval_boundary=True),
    DagNode("user_review", "qa-reviewer", "User Review", approval_boundary=True),
)


def default_stage_order() -> list[str]:
    return [n.stage_id for n in DEFAULT_PIPELINE]


def specialist_graph() -> list[dict[str, Any]]:
    nodes = [n.to_dict() for n in DEFAULT_PIPELINE]
    edges = [
        {"from": DEFAULT_PIPELINE[i].stage_id, "to": DEFAULT_PIPELINE[i + 1].stage_id}
        for i in range(len(DEFAULT_PIPELINE) - 1)
    ]
    return [{"nodes": nodes, "edges": edges}]
