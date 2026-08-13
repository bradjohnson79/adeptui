"""M4.7 ScriptDocument / ScriptElement / ScriptTransaction models."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

SCRIPT_DOCUMENT_SCHEMA = "script-document@1"
SCRIPT_REVISION_SCHEMA = "script-revision@1"
SCRIPT_TRANSACTION_SCHEMA = "script-transaction@1"

ScriptFormat = Literal[
    "feature",
    "television",
    "web-series",
    "short",
    "documentary",
    "commercial",
    "audio-drama",
    "custom",
]
DraftStatus = Literal["outline", "first-draft", "revision", "locked", "production"]
ScriptElementType = Literal[
    "scene_heading",
    "action",
    "character",
    "parenthetical",
    "dialogue",
    "transition",
    "shot",
    "general",
    "act_break",
    "section",
    "note",
    "lyric",
]
TransactionSource = Literal["creator", "codirector", "migration", "import", "system"]
SceneSyncStatus = Literal[
    "unlinked",
    "linked",
    "script_changed",
    "scene_changed",
    "conflict",
    "synced",
]
SaveState = Literal[
    "saved",
    "saving",
    "unsaved",
    "offline",
    "conflict",
    "recovery_available",
    "save_failed",
]

TRANSACTION_KINDS = (
    "insert_scene",
    "delete_scene",
    "move_scene",
    "apply_codirector_proposal",
    "restore_revision",
    "import_document",
    "convert_outline_to_scenes",
    "apply_timeline_prep_metadata",
    "edit_elements",
    "autosave_batch",
    "autosave_html",
    "migration",
)


class ScriptElement(BaseModel):
    id: str
    type: ScriptElementType
    text: str = ""
    order: int = 0
    sceneId: Optional[str] = None
    characterId: Optional[str] = None
    sceneNumber: Optional[str] = None
    revisionColor: Optional[str] = None
    locked: bool = False
    omitted: bool = False
    legacySegmentId: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScriptDocument(BaseModel):
    id: str
    projectId: str
    title: str = "Untitled Script"
    format: ScriptFormat = "feature"
    draftStatus: DraftStatus = "first-draft"
    elements: list[ScriptElement] = Field(default_factory=list)
    contentHtml: Optional[str] = None
    contentType: Literal["html", "elements"] = "elements"
    revision: int = 1
    revisionSetId: Optional[str] = None
    activeRevision: Optional[str] = None
    productionNumbersLocked: bool = False
    sceneSync: dict[str, SceneSyncStatus] = Field(default_factory=dict)
    legacyDocId: Optional[str] = None
    createdAt: str = ""
    updatedAt: str = ""
    schemaVersion: str = SCRIPT_DOCUMENT_SCHEMA


class ScriptTransaction(BaseModel):
    id: str
    documentId: str
    kind: str
    source: TransactionSource = "creator"
    beforeRevision: int
    afterRevision: int
    affectedElementIds: list[str] = Field(default_factory=list)
    createdAt: str = ""
    reversible: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)
    schemaVersion: str = SCRIPT_TRANSACTION_SCHEMA


class ScriptRevisionSnapshot(BaseModel):
    id: str
    documentId: str
    revisionSetId: str
    name: str
    color: str = "White"
    note: str = ""
    revision: int
    elements: list[ScriptElement] = Field(default_factory=list)
    createdAt: str = ""
    schemaVersion: str = SCRIPT_REVISION_SCHEMA


class ScriptNote(BaseModel):
    id: str
    documentId: str
    elementId: Optional[str] = None
    sceneKey: Optional[str] = None
    kind: str = "document"
    text: str = ""
    status: str = "open"
    author: str = "creator"
    createdAt: str = ""


class ScriptStats(BaseModel):
    pagesEstimated: float = 0.0
    scenes: int = 0
    words: int = 0
    characters: int = 0
    dialoguePercent: float = 0.0
    actionPercent: float = 0.0
    runtimeMinutesEstimated: float = 0.0
    paginationMode: str = "estimated"


DEFAULT_REVISION_COLORS = [
    "White",
    "Blue",
    "Pink",
    "Yellow",
    "Green",
    "Goldenrod",
    "Buff",
    "Salmon",
    "Cherry",
    "Tan",
    "Gray",
    "Ivory",
]
