"""Specialist execution policy — subordinate departments under Co-Director."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .specialist_registry import SpecialistRegistry

ExecutionMode = Literal["FOREGROUND_REQUIRED", "FOREGROUND_OPTIONAL", "BACKGROUND_ONLY"]


class CoDirectorSpecialistContract(BaseModel):
    specialistId: str
    displayName: str
    domain: str = "general"
    purpose: str = ""
    supportedIntents: list[str] = Field(default_factory=list)
    forbiddenIntents: list[str] = Field(default_factory=list)
    executionMode: ExecutionMode = "FOREGROUND_OPTIONAL"
    inputSchemaId: str = "specialist-task-v1"
    outputSchemaId: str = "specialist-finding-v1"
    requiredContextSources: list[str] = Field(default_factory=list)
    optionalContextSources: list[str] = Field(default_factory=list)
    forbiddenContextSources: list[str] = Field(default_factory=lambda: ["full_marketing_plan", "full_tool_registry"])
    maximumContextTokens: int = 4000
    maximumLatencyMs: int = 5000
    cacheable: bool = True
    cacheTtlSeconds: int = 600
    mayProposeWikiWrites: bool = False
    mayCreateDrafts: bool = False
    mayExecuteTools: bool = False
    requiresCreatorApproval: bool = False
    creatorFacingAllowed: bool = False  # always false — Core Law


class SpecialistSelectionDecision(BaseModel):
    specialistId: str
    selected: bool
    reason: str
    expectedValue: float = 0.0
    expectedLatencyMs: int = 0
    executionMode: Literal["FOREGROUND", "BACKGROUND", "SKIP"] = "SKIP"


# Domains that must never auto-run on TINY/SMALL onboarding narration.
_HEAVY_IDS = {
    "producer",
    "pipeline-manager",
    "screenwriter",
    "continuity-analyst",
    "cinematographer",
    "music-supervisor",
    "sound-designer",
    "sound-producer",
    "vfx-supervisor",
    "animation-supervisor",
}


def build_contract(definition) -> CoDirectorSpecialistContract:  # noqa: ANN001
    from ..wiki_intelligence.contracts import WIKI_WRITE_SPECIALIST_IDS

    allowed = list(getattr(definition, "allowed_context", ()) or [])
    contract = CoDirectorSpecialistContract(
        specialistId=definition.id,
        displayName=definition.display_name,
        domain=definition.id.split("-")[0] if "-" in definition.id else definition.id,
        purpose=(definition.description or "")[:240],
        supportedIntents=[],
        forbiddenIntents=["onboarding_ack", "tiny_rename"],
        executionMode="BACKGROUND_ONLY" if definition.id in _HEAVY_IDS else "FOREGROUND_OPTIONAL",
        outputSchemaId=definition.output_schema_id or "specialist-finding-v1",
        requiredContextSources=allowed[:4],
        optionalContextSources=allowed[4:],
        maximumLatencyMs=int(getattr(definition, "timeout_ms", 5000) or 5000),
        # Orchestrator applies writes; specialists may propose structured Wiki findings only.
        mayProposeWikiWrites=definition.id in WIKI_WRITE_SPECIALIST_IDS,
        mayCreateDrafts=definition.id in {"screenwriter", "story-editor", "storyteller"},
        mayExecuteTools=False,
        requiresCreatorApproval=bool(getattr(definition, "may_propose_tools", False)),
        creatorFacingAllowed=False,
    )
    enforce_specialist_permissions(definition.id, contract)
    return contract


def enforce_specialist_permissions(specialist_id: str, contract: CoDirectorSpecialistContract) -> None:
    """Runtime enforcement — defense-in-depth for specialist permissions.

    Called at runner entry point BEFORE the specialist generates any output.
    Raises ValueError if any hard constraint is violated.

    Hard constraints (frozen contract §5):
    - mayExecuteTools MUST be False for ALL specialists
    - mayProposeWikiWrites gates whether wiki writes can be proposed
    - requiresCreatorApproval gates whether output requires creator approval before effect
    - escalation_path is surfaced but not enforced here
    """
    if contract.mayExecuteTools:
        raise ValueError(
            f"Specialist '{specialist_id}': mayExecuteTools must be False. "
            "Specialists never execute tools directly. "
            "This is already enforced at registry build and prompt validation."
        )


def assert_runner_permissions(contract: CoDirectorSpecialistContract) -> None:
    """Assert runner may execute with this contract. Called at specialist_runner entry."""
    enforce_specialist_permissions(contract.specialistId, contract)


def authoritative_roster(registry: SpecialistRegistry | None = None) -> list[CoDirectorSpecialistContract]:
    reg = registry or SpecialistRegistry()
    return [build_contract(d) for d in reg.all_enabled()]


def select_specialists_for_turn(
    *,
    complexity: str,
    allow_specialists: bool,
    primary_intent: str,
    selected_ids: list[str] | None = None,
) -> list[SpecialistSelectionDecision]:
    """Gate specialist work by complexity — never inflate ordinary TTFT."""
    roster = authoritative_roster()
    decisions: list[SpecialistSelectionDecision] = []
    if not allow_specialists or complexity in {"TINY", "SMALL"}:
        for c in roster:
            decisions.append(
                SpecialistSelectionDecision(
                    specialistId=c.specialistId,
                    selected=False,
                    reason=f"Skipped for complexity={complexity} (budget)",
                    executionMode="SKIP",
                )
            )
        return decisions

    wanted = set(selected_ids or [])
    for c in roster:
        if c.specialistId in wanted:
            mode = "BACKGROUND" if c.executionMode == "BACKGROUND_ONLY" else "FOREGROUND"
            decisions.append(
                SpecialistSelectionDecision(
                    specialistId=c.specialistId,
                    selected=True,
                    reason=f"Selected for intent={primary_intent}",
                    expectedValue=0.7,
                    expectedLatencyMs=min(c.maximumLatencyMs, 5000),
                    executionMode=mode,  # type: ignore[arg-type]
                )
            )
        else:
            decisions.append(
                SpecialistSelectionDecision(
                    specialistId=c.specialistId,
                    selected=False,
                    reason="Not required for this turn",
                    executionMode="SKIP",
                )
            )
    return decisions


# Domain hard rules (prompt/routing fine-tunes — not weight training).
_DOMAIN_HARD_RULES: dict[str, str] = {
    "continuity-analyst": "Never mutate canon; report conflicts only; mayProposeWikiWrites=false.",
    "bible-manager": "Never mutate canon without creator approval; propose only.",
    "project-bible-steward": (
        "Organize Project Bible; simplify headings; attach Why It Matters; "
        "never transcript-dump; never mutate locked canon; creatorFacingAllowed=false."
    ),
    "screenwriter": "Respect ownership and locked scripts; draft only when authorized.",
    "story-editor": "Respect ownership; do not overwrite locked script sections.",
    "producer": "Destination-aware planning; do not force commercialization.",
    "pipeline-manager": "Technical workflow only; never invent marketing pressure.",
    "casting-director": "Character casting notes only; no creator-facing voice.",
    "cinematographer": "Visual/shot guidance only; subordinate synthesis by Co-Director.",
    "performance-director": "Performance notes only; never speak as Co-Director.",
    "music-supervisor": "Audio guidance only; destination-aware.",
    "sound-designer": "Audio design only; no forced commercialization.",
    "story-analyst": "Research-like analysis stays permission-aware; no web unless allowed.",
}

# Wishlist domains absent from current-release prompt library — do not fake-GO.
UNSUPPORTED_SPECIALIST_DOMAINS: list[dict[str, str]] = [
    {"id": "treatment-writer", "status": "UNSUPPORTED", "note": "Covered partially by screenwriter/story-editor"},
    {"id": "dialogue-specialist", "status": "UNSUPPORTED", "note": "Covered partially by screenwriter/story-editor"},
    {"id": "comparables-analyst", "status": "UNSUPPORTED", "note": "Absent from prompt library"},
    {"id": "distribution-festival-youtube", "status": "UNSUPPORTED", "note": "Absent from current release"},
]


def domain_hard_rules_for(specialist_id: str) -> str:
    return _DOMAIN_HARD_RULES.get(specialist_id, "Subordinate only; creatorFacingAllowed=false; structured finding only.")


def roster_artifact() -> dict:
    contracts = authoritative_roster()
    return {
        "version": 1,
        "count": len(contracts),
        "creatorFacingAllowed": False,
        "domainHardRules": _DOMAIN_HARD_RULES,
        "unsupportedDomains": UNSUPPORTED_SPECIALIST_DOMAINS,
        "specialists": [
            {**c.model_dump(mode="json"), "hardRules": domain_hard_rules_for(c.specialistId)}
            for c in contracts
        ],
    }
