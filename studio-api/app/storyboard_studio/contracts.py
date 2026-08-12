"""M4.9 storyboard document / page / panel link contracts."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

StoryboardPageSize = Literal[6, 9, 12]
ScriptLinkStatus = Literal[
    "linked",
    "script_updated",
    "override",
    "conflict",
    "unlinked",
]


class StoryboardPanelLink(BaseModel):
    """Panel slot on a page — wraps existing storyboard_panels row."""

    panelId: str
    pageIndex: int = 0
    slotIndex: int = 0
    assetId: Optional[str] = None
    label: str = ""
    prompt: str = ""
    lens: str = ""
    shotSize: str = ""
    approval: str = "draft"
    status: str = "missing"
    scriptLinkStatus: ScriptLinkStatus = "unlinked"
    segmentId: Optional[str] = None
    scriptwriterSceneId: Optional[str] = None
    scriptwriterActionId: Optional[str] = None
    scriptwriterDialogueId: Optional[str] = None
    continuitySessionId: Optional[str] = None
    spatialMapId: Optional[str] = None
    spatialMapVersion: Optional[str] = None
    durationEst: float = 3.0
    meta: dict[str, Any] = Field(default_factory=dict)


class StoryboardPage(BaseModel):
    pageIndex: int = 0
    pageSize: StoryboardPageSize = 9
    panelIds: list[str] = Field(default_factory=list)
    title: str = ""


class StoryboardDocument(BaseModel):
    id: str
    projectId: str
    title: str = "Storyboard"
    pageSize: StoryboardPageSize = 9
    pages: list[StoryboardPage] = Field(default_factory=list)
    panelOrder: list[str] = Field(default_factory=list)
    legacyDocId: Optional[str] = None
    continuitySessionId: Optional[str] = None
    createdAt: str = ""
    updatedAt: str = ""


class TimelinePrepShotProposal(BaseModel):
    panelId: str
    assetId: Optional[str] = None
    label: str = ""
    prompt: str = ""
    dialogue: str = ""
    cameraNote: str = ""
    durationEst: float = 3.0
    sceneId: Optional[str] = None
    continuitySessionId: Optional[str] = None
    spatialMapId: Optional[str] = None
    spatialMapVersion: Optional[str] = None


class TimelinePrepProposal(BaseModel):
    id: str
    projectId: str
    documentId: str
    shots: list[TimelinePrepShotProposal] = Field(default_factory=list)
    status: Literal["draft", "approved", "applied", "rejected"] = "draft"
    createdAt: str = ""
    note: str = "Reviewable proposal only — no silent clip generation."
