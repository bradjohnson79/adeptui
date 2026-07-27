# -*- coding: utf-8 -*-
"""Emit M2.14 unified experience core (UTF-8 via Path.write_text)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "studio-api" / "app" / "codirector" / "m214"
MIG = ROOT / "studio-api" / "app" / "migrations"
PROMPTS = ROOT / "studio-api" / "app" / "codirector" / "prompts" / "specialists"
DOCS = ROOT / "docs" / "codirector" / "m2.14"


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", path.relative_to(ROOT))


INIT = r'''"""Co-Director M2.14 Unified Experience package."""
from __future__ import annotations

from .flags import FLAG_ENV, FLAG_NAME, unified_experience_enabled

__all__ = ["FLAG_ENV", "FLAG_NAME", "unified_experience_enabled"]
'''

FLAGS = r'''"""M2.14 feature-flag helpers (default OFF)."""
from __future__ import annotations

from ... import feature_flags as feature_flags_mod

FLAG_NAME = "codirector_unified_experience_v1"
FLAG_ENV = "STUDIO_FEATURE_CODIRECTOR_UNIFIED_EXPERIENCE_V1"


def unified_experience_enabled() -> bool:
    return bool(getattr(feature_flags_mod.feature_flags, FLAG_NAME, False))
'''

SAFETY = r'''"""M2.14 safety: Manifest lock + hard bans."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

EXPECTED_MANIFEST_SHA256: Final[str] = (
    "cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc"
)
MANIFEST_RELATIVE: Final[str] = "config/capabilities/adept-ui-v1.0-provider-manifest.json"


class UnifiedExperienceSafetyError(RuntimeError):
    """Raised when M2.14 safety invariants are violated."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def assert_manifest_unchanged(root: Path | None = None) -> str:
    base = root or repo_root()
    path = base / MANIFEST_RELATIVE
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != EXPECTED_MANIFEST_SHA256:
        raise UnifiedExperienceSafetyError(
            f"Provider Manifest sha256 mismatch: got {digest}, expected {EXPECTED_MANIFEST_SHA256}"
        )
    return digest


def safety_contract() -> dict:
    return {
        "noNewProviders": True,
        "noManifestOrLockChanges": True,
        "noSilentBibleOrTimelineMutation": True,
        "noFineTuning": True,
        "noAutonomousCodeRewrite": True,
        "noSystemLessonAutoActivate": True,
        "extendM211DoNotForkOrchestration": True,
        "labelMockedVsReal": True,
        "manifestSha256": EXPECTED_MANIFEST_SHA256,
        "flagDefaultOff": True,
        "apis404WhenOff": True,
    }
'''

KINDS = r'''"""M2.14 Product section 50 capability IDs (honest registration)."""
from __future__ import annotations

# Product section 50 capability IDs — registered as partially_wired scaffolds.
CAPABILITY_IDS: tuple[tuple[str, str, str], ...] = (
    ("codirector.attachment.classify", "Classify attachment by content", "partially_wired"),
    ("codirector.attachment.interpret", "Interpret attachment proposal", "partially_wired"),
    ("codirector.attachment.confirm", "Confirm attachment interpretation", "partially_wired"),
    ("codirector.project.propose", "Propose project from idea/attachment", "partially_wired"),
    ("codirector.project.resume", "Resume unified session", "partially_wired"),
    ("codirector.media.list", "List media cards", "partially_wired"),
    ("codirector.media.select", "Select media item", "partially_wired"),
    ("codirector.media.compare", "Compare media items", "partially_wired"),
    ("codirector.media.review", "Review media item", "partially_wired"),
    ("codirector.media.approve", "Approve media item", "partially_wired"),
    ("codirector.media.reject", "Reject media item", "partially_wired"),
    ("codirector.media.request_revision", "Request media revision", "partially_wired"),
    ("storyteller.scene.analyze", "Storyteller scene analyze", "partially_wired"),
    ("storyteller.scene.identify_unknowns", "Identify scene unknowns", "partially_wired"),
    ("storyteller.scene.ask_questions", "Ask 2-4 high-impact questions", "partially_wired"),
    ("storyteller.scene.propose_direction", "Propose scene direction", "partially_wired"),
    ("storyteller.scene.generate_variations", "Generate scene variations", "partially_wired"),
    ("storyteller.scene.define_emotional_arc", "Define emotional arc", "partially_wired"),
    ("storyteller.scene.define_subtext", "Define subtext", "partially_wired"),
    ("storyteller.character.interpret", "Interpret character", "partially_wired"),
    ("storyteller.environment.interpret", "Interpret environment story", "partially_wired"),
    ("storyteller.media.review", "Storyteller media review", "partially_wired"),
    ("storyteller.handoff.create", "Create Storyteller production handoff", "partially_wired"),
    ("sound_producer.concept.create", "Create SonicConcept", "partially_wired"),
    ("sound_producer.score_brief.create", "Create score brief", "partially_wired"),
    ("sound_producer.ambience.plan", "Plan ambience", "partially_wired"),
    ("sound_producer.cue.plan", "Plan sound cues", "partially_wired"),
    ("sound_producer.dialogue.plan", "Plan dialogue treatment", "partially_wired"),
    ("sound_producer.mix_intent.create", "Create mix intent", "partially_wired"),
    ("production_team.message.send", "Send specialist message", "partially_wired"),
    ("production_team.message.respond", "Respond to specialist message", "partially_wired"),
    ("production_team.handoff.create", "Create department handoff", "partially_wired"),
    ("production_team.meeting.convene", "Convene production meeting", "partially_wired"),
    ("production_team.meeting.synthesize", "Synthesize meeting for user", "partially_wired"),
    ("production_team.conflict.detect", "Detect production conflicts", "partially_wired"),
    ("production_team.conflict.resolve", "Resolve/synthesize conflicts", "partially_wired"),
    ("production_team.decision.propagate", "Propagate decision impact", "partially_wired"),
    ("production_team.impact.calculate", "Calculate decision impact", "partially_wired"),
    ("production_team.state.revalidate", "Revalidate approvals after impact", "partially_wired"),
    ("production_team.brief.update", "Update UnifiedSceneBrief", "partially_wired"),
    ("production_team.readiness.evaluate", "Evaluate production readiness", "partially_wired"),
    ("production_team.final_review", "Final production review", "partially_wired"),
)

PROJECT_STAGES: tuple[str, ...] = (
    "idea",
    "discovery",
    "treatment",
    "screenplay",
    "previs",
    "production",
    "post",
    "delivery",
)

ATTACHMENT_KINDS: tuple[str, ...] = (
    "treatment",
    "screenplay",
    "storyboard",
    "sketch",
    "reference_image",
    "audio_reference",
    "video_reference",
    "notes",
    "unknown",
)

MEDIA_KINDS: tuple[str, ...] = (
    "image",
    "video",
    "audio",
    "storyboard",
    "environment_preview",
)

SPECIALIST_IDS: tuple[str, ...] = (
    "storyteller",
    "sound-producer",
)
'''

CONTRACTS = r'''"""M2.14 domain contracts (versioned, approval-aware)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional
from uuid import uuid4


def _id() -> str:
    return str(uuid4())


@dataclass
class EmotionalSceneProfile:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    version: int = 1
    emotional_arc: str = ""
    subtext: str = ""
    tone: str = ""
    stakes: str = ""
    character_beats: list[dict[str, Any]] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    mode: str = "guided"  # guided | creative | variation
    honesty: str = "mocked"  # mocked | real
    approved: bool = False
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StorytellerHandoff:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    version: int = 1
    profile_id: str = ""
    direction_summary: str = ""
    format_guidance: str = ""
    progressive_depth: str = "shallow"
    approved: bool = False
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SonicConcept:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    version: int = 1
    score_brief: str = ""
    ambience: str = ""
    cues: list[str] = field(default_factory=list)
    dialogue_plan: str = ""
    mix_intent: str = ""
    mode: str = "guided"
    honesty: str = "mocked"
    approved: bool = False
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SpecialistMessage:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    from_specialist: str = ""
    to_specialist: str = ""
    kind: str = "note"  # note | question | handoff | conflict | decision
    body: str = ""
    requires_response: bool = False
    responded: bool = False
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UnifiedSceneBrief:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    revision: int = 1
    title: str = ""
    logline: str = ""
    emotional_profile_id: Optional[str] = None
    sonic_concept_id: Optional[str] = None
    storyteller_handoff_id: Optional[str] = None
    departments: dict[str, Any] = field(default_factory=dict)
    primary_next_action: str = ""
    approved_keys: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProductionMeeting:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    topic: str = ""
    participants: list[str] = field(default_factory=list)
    exchanges: list[dict[str, Any]] = field(default_factory=list)
    synthesis: str = ""
    primary_next_action: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProductionDecisionImpact:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    decision_id: str = ""
    decision_summary: str = ""
    affected_departments: list[str] = field(default_factory=list)
    revalidate_keys: list[str] = field(default_factory=list)
    preserved_approvals: list[str] = field(default_factory=list)
    impact_summary: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProductionMotif:
    id: str = field(default_factory=_id)
    project_id: str = ""
    scene_id: str = ""
    name: str = ""
    kind: str = "visual"  # visual | sonic | narrative
    description: str = ""
    linked_media_ids: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AttachmentInterpretation:
    id: str = field(default_factory=_id)
    project_id: str = ""
    attachment_id: str = ""
    classified_kind: str = "unknown"
    confidence: float = 0.0
    summary: str = ""
    proposals: list[dict[str, Any]] = field(default_factory=list)
    status: str = "proposed"  # proposed | approved | corrected | provisional | cancelled
    content_signals: list[str] = field(default_factory=list)
    honesty: str = "mocked"
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
'''


def main() -> None:
    w(PKG / "__init__.py", INIT)
    w(PKG / "flags.py", FLAGS)
    w(PKG / "safety.py", SAFETY)
    w(PKG / "kinds.py", KINDS)
    w(PKG / "contracts.py", CONTRACTS)
    print("core emit complete")


if __name__ == "__main__":
    main()
