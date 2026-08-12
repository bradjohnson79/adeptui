"""Router context assembly — Phase 3 Agent D.

Assembles the full router input context from Phase 2 Production State, stage
evidence, workspace state, and conversation focus (§5 of the Phase 3 contract).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from app.codirector.routing.contracts import RouteActionClass, RouteDecision

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_WORKSPACES: frozenset[str] = frozenset({
    "script_writer", "timeline", "audiostudio", "voicestudio",
    "magi", "continuity", "bible", "posecraft", "runtime_manager",
    "references", "characters", "casting", "editor",
})

# ---------------------------------------------------------------------------
# RouterContext
# ---------------------------------------------------------------------------


@dataclass
class RouterContext:
    """Full router input context assembled from Phase 2 infrastructure.

    Fields correspond to §5 of the Phase 3 router implementation contract.
    """

    message: str
    derived_stage: Optional[str] = None
    stage_evidence: Optional[list[dict]] = None
    conversation_focus: Optional[str] = None
    active_workspace: Optional[str] = None
    recent_operator_actions: Optional[list[str]] = None
    pending_proposal_ids: Optional[list[str]] = None
    available_workspaces: frozenset[str] = field(
        default_factory=lambda: _DEFAULT_WORKSPACES,
    )
    available_action_classes: list[str] = field(
        default_factory=lambda: [m.value for m in RouteActionClass],
    )
    available_targets: Optional[list[str]] = None


# ---------------------------------------------------------------------------
# build_router_context
# ---------------------------------------------------------------------------


def build_router_context(
    message: str,
    db: Any,
    project_id: str,
    *,
    active_workspace: Optional[str] = None,
    session_context: Optional[dict] = None,
    conversation_focus: Optional[str] = None,
) -> RouterContext:
    """Assemble a :class:`RouterContext` from Phase 2 infrastructure.

    Each external dependency is loaded with ``try/except`` so the module
    works even when Phase 2 modules are missing.
    """
    # --- derived_stage ---
    derived_stage: Optional[str] = None
    stage_evidence_raw: Optional[list] = None
    try:
        from app.codirector.production_state.stage_evidence import (
            collect_stage_evidence,
            get_authoritative_stage,
        )

        derived_stage = get_authoritative_stage(db, project_id)
        evidence = collect_stage_evidence(db, project_id)
        stage_evidence_raw = [e.model_dump() for e in evidence]
    except Exception:
        logger.debug("Could not load stage evidence from production_state", exc_info=True)
        derived_stage = None
        stage_evidence_raw = None

    # --- active_workspace ---
    resolved_active_workspace: Optional[str] = active_workspace
    if resolved_active_workspace is None and session_context is not None:
        resolved_active_workspace = session_context.get("activeWorkspace")

    # --- pending_proposal_ids ---
    pending_ids: Optional[list[str]] = None
    try:
        from app.codirector.bible.proposals import ProposalService

        pending = ProposalService.list(db, project_id, status="pending")
        pending_ids = [p.id for p in pending]
    except Exception:
        logger.debug("Could not load pending proposals from bible.proposals", exc_info=True)
        pending_ids = None

    # --- available_targets ---
    available_targets: list[str] = sorted(_DEFAULT_WORKSPACES)

    return RouterContext(
        message=message,
        derived_stage=derived_stage,
        stage_evidence=stage_evidence_raw,
        conversation_focus=conversation_focus,
        active_workspace=resolved_active_workspace,
        recent_operator_actions=None,
        pending_proposal_ids=pending_ids,
        available_targets=available_targets,
    )


# ---------------------------------------------------------------------------
# Stage-Sensitive matching helpers
# ---------------------------------------------------------------------------

_CREATE_SHOTS_PATTERN = re.compile(
    r"create shots|shot list|plan shots",
    re.IGNORECASE,
)

_EDIT_DIALOGUE_PATTERN = re.compile(
    r"(let's change|let's edit|modify|update).*(line|dialogue|scene|page)",
    re.IGNORECASE,
)

_SCRIPT_LIKE_STAGES: frozenset[str] = frozenset({"story", "script", "writing"})
_IMAGE_PLANNING_LIKE_STAGES: frozenset[str] = frozenset({
    "production", "timeline_assembly", "image_planning",
})


def _stage_matches_any(stage: str | None, candidates: frozenset[str]) -> bool:
    if stage is None:
        return False
    cf = stage.casefold()
    return cf in candidates or any(c in cf or cf in c for c in candidates)


def _focus_is_script_or_dialogue(focus: str | None) -> bool:
    if focus is None:
        return False
    lower = focus.casefold()
    return any(kw in lower for kw in ("script", "dialogue", "line", "scene", "page"))


# ---------------------------------------------------------------------------
# StageSensitiveRouter
# ---------------------------------------------------------------------------


class StageSensitiveRouter:
    """Applies stage-sensitive routing rules (contract §7).

    If deterministic routing returned a stage-dependent result,
    this class adjusts it based on derivedStage.
    """

    @staticmethod
    def adjust_for_stage(
        decision: RouteDecision,
        context: RouterContext,
    ) -> RouteDecision:
        """Apply §7 rules and return a (possibly adjusted) RouteDecision."""

        message = context.message or ""
        derived_stage = context.derived_stage
        conversation_focus = context.conversation_focus

        # ── §7.1: "create shots" + SCRIPT-like stage → block execution ──
        if _CREATE_SHOTS_PATTERN.search(message) and _stage_matches_any(
            derived_stage, _SCRIPT_LIKE_STAGES,
        ):
            return RouteDecision(
                actionClass=RouteActionClass.PROPOSE_CREATIVE_CHANGE,
                target="shot_planning",
                writeAllowed=False,
                executionLane="discuss",
                evidence=[
                    "stage-sensitive: script-stage 'create shots' blocked from execution",
                ],
                confidence=0.9,
                classifierSource=decision.classifierSource,
            )

        # ── §7.1: "create shots" + IMAGE_PLANNING-like stage → allow execution ──
        if _CREATE_SHOTS_PATTERN.search(message) and _stage_matches_any(
            derived_stage, _IMAGE_PLANNING_LIKE_STAGES,
        ):
            decision.evidence = [
                *decision.evidence,
                "stage-sensitive: image-planning stage allows shot execution",
            ]
            return decision

        # ── §7.2: conversationFocus overrides stage default for target ──
        if (
            _EDIT_DIALOGUE_PATTERN.search(message)
            and _focus_is_script_or_dialogue(conversation_focus)
        ):
            decision.evidence = [
                *decision.evidence,
                "conversationFocus overrode default stage target",
            ]
            if decision.target is None:
                decision.target = "script"
            else:
                tl = decision.target.casefold()
                if not any(kw in tl for kw in ("script", "dialogue", "line")):
                    decision.target = "script"
            return decision

        return decision


# ---------------------------------------------------------------------------
# CapabilityGate
# ---------------------------------------------------------------------------


class CapabilityGate:
    """Checks whether the target capability is available (§7.3).

    If the route decision requires an unavailable capability, sets
    ``capabilityAvailable=False`` and adds ``supportedAlternative``.
    """

    @staticmethod
    def check(
        decision: RouteDecision,
        context: RouterContext,
    ) -> RouteDecision:
        """Validate capability availability and mutate decision if needed."""

        if decision.actionClass == RouteActionClass.NAVIGATE and decision.targetWorkspace is not None:
            if decision.targetWorkspace not in context.available_workspaces:
                decision.capabilityAvailable = False
                decision.executionLane = "unavailable"
                suggestion = ", ".join(sorted(context.available_workspaces))
                decision.supportedAlternative = (
                    f"'{decision.targetWorkspace}' is not available. "
                    f"Try one of: {suggestion}"
                )

        return decision
