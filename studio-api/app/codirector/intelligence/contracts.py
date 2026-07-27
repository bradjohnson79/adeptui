"""Specialist contracts for M2.11 Production Intelligence (advise-only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SpecialistContract:
    specialist_id: str
    product_role: str
    responsibilities: tuple[str, ...]
    input_keys: tuple[str, ...]
    output_keys: tuple[str, ...]
    confidence_required: bool = True
    reasoning_required: bool = True
    approval_required: bool = False
    escalation_path: str = ""
    aliases: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "specialistId": self.specialist_id,
            "productRole": self.product_role,
            "responsibilities": list(self.responsibilities),
            "structuredIO": {
                "input": list(self.input_keys),
                "output": list(self.output_keys),
            },
            "confidenceRequired": self.confidence_required,
            "reasoningRequired": self.reasoning_required,
            "approvalRequired": self.approval_required,
            "escalationPath": self.escalation_path,
            "aliases": list(self.aliases),
        }


_SHARED_INPUT = ("bible", "memory", "scene", "userBrief")

CONTRACTS: dict[str, SpecialistContract] = {
    "story-analyst": SpecialistContract(
        specialist_id="story-analyst",
        product_role="Story Analyst",
        responsibilities=(
            "Extract dramatic beats and narrative intent",
            "Identify stakes and suspense levers",
            "Flag story holes without mutating Bible",
        ),
        input_keys=_SHARED_INPUT,
        output_keys=("storyBeats", "characterGoals", "suspenseLevers", "risks", "openQuestions"),
        escalation_path="Canon conflicts → Bible Manager; feasibility → Pipeline Manager",
    ),
    "bible-manager": SpecialistContract(
        specialist_id="bible-manager",
        product_role="Production Bible Manager",
        responsibilities=(
            "Assess Bible completeness",
            "Propose entity/canon updates via approval paths only",
            "Never silently mutate Bible or timeline",
        ),
        input_keys=_SHARED_INPUT,
        output_keys=("bibleGaps", "proposedEntities", "canonNotes", "missingAssets"),
        approval_required=True,
        escalation_path="Locked conflicts → User Review; continuity clashes → Continuity Supervisor",
    ),
    "continuity-analyst": SpecialistContract(
        specialist_id="continuity-analyst",
        product_role="Continuity Supervisor",
        responsibilities=(
            "Detect continuity risks and handoff mismatches",
            "Bridge specialist conflicts into conflict_record",
            "Advise only; mutations via proposals",
        ),
        input_keys=_SHARED_INPUT + ("previous_shot", "next_shot"),
        output_keys=("continuityRisks", "handoffs", "wardrobeNotes", "conflicts"),
        approval_required=True,
        aliases=("continuity-supervisor",),
        escalation_path="Unresolved conflicts → Bible Manager + User Review",
    ),
    "director": SpecialistContract(
        specialist_id="director",
        product_role="Director",
        responsibilities=("Scene intention", "Blocking", "Coverage strategy"),
        input_keys=_SHARED_INPUT,
        output_keys=("sceneIntention", "blocking", "coverageStrategy", "risks"),
        escalation_path="Canon → Bible Manager; QA blockers → QA Reviewer",
    ),
    "cinematographer": SpecialistContract(
        specialist_id="cinematographer",
        product_role="Camera Supervisor",
        responsibilities=("Shot plan", "Camera / lens language", "Coverage"),
        input_keys=_SHARED_INPUT + ("shot",),
        output_keys=("shotPlan", "cameraNotes", "lensLanguage", "coverage"),
        aliases=("camera-supervisor",),
        escalation_path="Lighting → Lighting Supervisor; capability gaps → Pipeline Manager",
    ),
    "sound-designer": SpecialistContract(
        specialist_id="sound-designer",
        product_role="Sound Supervisor",
        responsibilities=("SFX plan", "Ambience", "Dialogue notes"),
        input_keys=_SHARED_INPUT + ("audio",),
        output_keys=("sfxPlan", "ambience", "dialogueNotes", "risks"),
        aliases=("sound-supervisor",),
        escalation_path="Music clashes → Music Supervisor; missing audio caps → Pipeline Manager",
    ),
    "music-supervisor": SpecialistContract(
        specialist_id="music-supervisor",
        product_role="Music Supervisor",
        responsibilities=("Music cues", "Tempo / mood", "Stingers"),
        input_keys=_SHARED_INPUT,
        output_keys=("musicCues", "tempoMood", "stingerNotes", "risks"),
        escalation_path="SFX conflicts → Sound Designer; capability gaps → Pipeline Manager",
    ),
    "editor": SpecialistContract(
        specialist_id="editor",
        product_role="Editor",
        responsibilities=("Edit beats", "Cut points", "Pacing"),
        input_keys=_SHARED_INPUT + ("previous_shot", "next_shot"),
        output_keys=("editBeats", "cutPoints", "pacingNotes", "risks"),
        escalation_path="Continuity cuts → Continuity Supervisor; timeline mutations → approval paths",
    ),
    "qa-reviewer": SpecialistContract(
        specialist_id="qa-reviewer",
        product_role="QA Reviewer",
        responsibilities=("QA checklist", "Acceptance criteria", "Blockers"),
        input_keys=_SHARED_INPUT,
        output_keys=("checklist", "blockers", "confidence", "acceptanceCriteria"),
        approval_required=True,
        escalation_path="Unresolved blockers → User Review",
    ),
    "animation-supervisor": SpecialistContract(
        specialist_id="animation-supervisor",
        product_role="Animation Supervisor",
        responsibilities=("Motion language", "Performance timing", "Animation continuity"),
        input_keys=_SHARED_INPUT,
        output_keys=("motionNotes", "timingBeats", "continuityRisks"),
        escalation_path="Capability gaps → Pipeline Manager",
    ),
    "compositing-supervisor": SpecialistContract(
        specialist_id="compositing-supervisor",
        product_role="Compositing Supervisor",
        responsibilities=("Layer plan", "Plate needs", "Comp risks"),
        input_keys=_SHARED_INPUT + ("vfx",),
        output_keys=("layerPlan", "plateNeeds", "compRisks", "missingAssets"),
        escalation_path="Render gaps → Pipeline Manager",
    ),
    "lighting-supervisor": SpecialistContract(
        specialist_id="lighting-supervisor",
        product_role="Lighting Supervisor",
        responsibilities=("Lighting intent", "Mood", "Exposure continuity"),
        input_keys=_SHARED_INPUT,
        output_keys=("lightingIntent", "keyFillRatio", "continuityRisks"),
        escalation_path="Camera exposure → Cinematographer",
    ),
    "asset-manager": SpecialistContract(
        specialist_id="asset-manager",
        product_role="Asset Manager",
        responsibilities=("Required assets", "Missing references", "Readiness"),
        input_keys=_SHARED_INPUT + ("references",),
        output_keys=("requiredAssets", "missingAssets", "readyAssets", "blockers"),
        approval_required=True,
        escalation_path="Missing locked refs → User Review",
    ),
    "pipeline-manager": SpecialistContract(
        specialist_id="pipeline-manager",
        product_role="Pipeline Manager",
        responsibilities=("Pipeline feasibility", "Stage ordering", "Capability routing"),
        input_keys=_SHARED_INPUT + ("capabilities",),
        output_keys=("pipelinePlan", "capabilityGaps", "stageOrder", "blockers"),
        escalation_path="Missing capabilities → User; mutations → proposal paths",
    ),
    "code-director": SpecialistContract(
        specialist_id="code-director",
        product_role="Code Director",
        responsibilities=("Integration boundaries", "Schema contracts", "Platform awareness"),
        input_keys=("capabilities", "project_overview"),
        output_keys=("integrationNotes", "contractIssues", "platformAwareness", "risks"),
        escalation_path="Schema breaks → Pipeline Manager; never fake CONNECTED integrations",
    ),
    "vision-reviewer": SpecialistContract(
        specialist_id="vision-reviewer",
        product_role="Vision QA",
        responsibilities=("Visual criteria", "Defects", "Confidence"),
        input_keys=_SHARED_INPUT + ("references",),
        output_keys=("visualCriteria", "defects", "confidence", "blockers"),
        approval_required=True,
        escalation_path="Unresolved defects → QA Reviewer / User Review",
    ),
    "screenwriter": SpecialistContract(
        specialist_id="screenwriter",
        product_role="Screenwriter",
        responsibilities=("Story structure", "Dialogue", "Pacing"),
        input_keys=_SHARED_INPUT,
        output_keys=("sceneText", "dialogueNotes", "pacingNotes", "risks"),
        escalation_path="Canon → Bible Manager",
    ),
    "story-editor": SpecialistContract(
        specialist_id="story-editor",
        product_role="Story Editor",
        responsibilities=("Story coherence", "Arc integrity"),
        input_keys=_SHARED_INPUT,
        output_keys=("arcNotes", "coherenceRisks", "recommendations"),
        escalation_path="Story Analyst for beat conflicts",
    ),
    "producer": SpecialistContract(
        specialist_id="producer",
        product_role="Producer",
        responsibilities=("Production decisions", "Priority tradeoffs"),
        input_keys=_SHARED_INPUT + ("production_decisions", "capabilities"),
        output_keys=("priorities", "tradeoffs", "decisions"),
        approval_required=True,
        escalation_path="Budget/capability blockers → User Review",
    ),
    "technical-director": SpecialistContract(
        specialist_id="technical-director",
        product_role="Technical Director",
        responsibilities=("Technical feasibility", "Capability checks"),
        input_keys=_SHARED_INPUT + ("capabilities",),
        output_keys=("techRisks", "capabilityNotes", "blockers"),
        escalation_path="Missing capabilities → Pipeline Manager",
    ),
    "production-designer": SpecialistContract(
        specialist_id="production-designer",
        product_role="Production Designer",
        responsibilities=("Locations", "Set dressing", "Object language"),
        input_keys=_SHARED_INPUT,
        output_keys=("locationNotes", "setDressing", "objectNeeds"),
        escalation_path="Asset gaps → Asset Manager",
    ),
    "art-director": SpecialistContract(
        specialist_id="art-director",
        product_role="Art Director",
        responsibilities=("Visual language", "Look consistency"),
        input_keys=_SHARED_INPUT + ("visual_language", "references"),
        output_keys=("lookNotes", "palette", "risks"),
        escalation_path="Lighting → Lighting Supervisor",
    ),
    "prompt-architect": SpecialistContract(
        specialist_id="prompt-architect",
        product_role="Prompt Architect",
        responsibilities=("Generation prompt packages", "Reference binding notes"),
        input_keys=_SHARED_INPUT + ("shot", "references"),
        output_keys=("promptPackage", "referenceNotes", "risks"),
        escalation_path="Missing refs → Asset Manager",
    ),
    "script-supervisor": SpecialistContract(
        specialist_id="script-supervisor",
        product_role="Script Supervisor",
        responsibilities=("Script continuity", "Coverage notes"),
        input_keys=_SHARED_INPUT,
        output_keys=("scriptNotes", "coverageGaps", "risks"),
        escalation_path="Continuity → Continuity Supervisor",
    ),
    "vfx-supervisor": SpecialistContract(
        specialist_id="vfx-supervisor",
        product_role="VFX Supervisor",
        responsibilities=("VFX needs", "Plate/pass advice"),
        input_keys=_SHARED_INPUT + ("vfx", "capabilities"),
        output_keys=("vfxNeeds", "passList", "risks"),
        escalation_path="Comp → Compositing Supervisor",
    ),
    "choreographer": SpecialistContract(
        specialist_id="choreographer",
        product_role="Choreographer",
        responsibilities=("Blocking motion", "Action timing"),
        input_keys=_SHARED_INPUT,
        output_keys=("choreographyNotes", "timingBeats", "risks"),
        escalation_path="Animation → Animation Supervisor",
    ),
    "performance-director": SpecialistContract(
        specialist_id="performance-director",
        product_role="Performance Director",
        responsibilities=("Performance intent", "Emotional beats"),
        input_keys=_SHARED_INPUT,
        output_keys=("performanceNotes", "emotionalBeats", "risks"),
        escalation_path="Story conflicts → Story Analyst",
    ),
    "casting-director": SpecialistContract(
        specialist_id="casting-director",
        product_role="Casting Director",
        responsibilities=("Casting notes", "Identity references"),
        input_keys=("characters", "references", "wardrobe"),
        output_keys=("castingNotes", "identityRefs", "risks"),
        escalation_path="Missing identity refs → Asset Manager",
    ),
}


# Product role → specialist id (aliases resolve to canonical ids)
PRODUCT_ROLE_MAP: dict[str, str] = {
    "Story Analyst": "story-analyst",
    "Production Bible Manager": "bible-manager",
    "Continuity Supervisor": "continuity-analyst",
    "Camera Supervisor": "cinematographer",
    "Animation Supervisor": "animation-supervisor",
    "Compositing Supervisor": "compositing-supervisor",
    "Lighting Supervisor": "lighting-supervisor",
    "Asset Manager": "asset-manager",
    "QA Reviewer": "qa-reviewer",
    "Pipeline Manager": "pipeline-manager",
    "Code Director": "code-director",
    "Director": "director",
    "Sound Supervisor": "sound-designer",
    "Music Supervisor": "music-supervisor",
    "Editor": "editor",
    "Cinematographer": "cinematographer",

    "virtual-production-coordinator": SpecialistContract(
        specialist_id="virtual-production-coordinator",
        product_role="Virtual Production Coordinator",
        responsibilities=(
            "Coordinate A-Z scene production plans",
            "Track readiness GO/NO-GO, blockers, and dependencies",
            "Enforce persisted approval gates across VE pipelines",
            "Label fixture/mock vs real generation honestly",
        ),
        input_keys=("sceneProductionPlan", "virtualEnvironment", "approvals", "blockers"),
        output_keys=("stageAdvice", "readiness", "blockers", "dependencyRegister", "dashboardCategories", "honestyNotes"),
        confidence_required=True,
        reasoning_required=True,
        approval_required=True,
        escalation_path="continuity-analyst",
        aliases=("vpc", "virtual_production_coordinator"),
    ),

}


def get_contract(specialist_id: str) -> SpecialistContract | None:
    return CONTRACTS.get(specialist_id)


def resolve_role(role_or_id: str) -> str | None:
    if role_or_id in CONTRACTS:
        return role_or_id
    mapped = PRODUCT_ROLE_MAP.get(role_or_id)
    if mapped:
        return mapped
    for contract in CONTRACTS.values():
        if role_or_id in contract.aliases:
            return contract.specialist_id
        if contract.product_role.lower() == role_or_id.lower():
            return contract.specialist_id
    return None


def all_contracts() -> list[SpecialistContract]:
    return list(CONTRACTS.values())
