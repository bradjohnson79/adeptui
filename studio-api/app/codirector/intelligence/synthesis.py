"""Conflict resolution and response compression for synthesis."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from .schemas import IntentClassification, ProposedToolAction, SpecialistFinding, SynthesisResult

_PRIORITY_ORDER = (
    "continuity-analyst",
    "script-supervisor",
    "director",
    "producer",
    "technical-director",
    "cinematographer",
    "prompt-architect",
    "art-director",
    "vision-reviewer",
)


class SynthesisEngine:
    def classify_conflicts(self, findings: Iterable[SpecialistFinding]) -> list[str]:
        """Classify disagreement among specialist findings into typed categories.

        Returns a list of human-readable conflict descriptions.
        """
        conflicts: list[str] = []
        seen_texts: dict[str, list[str]] = {}

        for finding in findings:
            specialist_id = finding.specialistId
            text = finding.recommendation or finding.summary
            if not text:
                continue
            key = text.strip().lower()[:80]
            if key in seen_texts:
                seen_texts[key].append(specialist_id)
            else:
                seen_texts[key] = [specialist_id]

        for finding in findings:
            text = finding.recommendation or finding.summary
            if not text:
                continue
            lower = text.lower()

            if any(w in lower for w in ["should we", "could also", "alternatively", "option"]):
                label = "stylistic"
            elif any(w in lower for w in ["cannot", "not possible", "capability", "blocked"]):
                label = "feasibility"
            elif any(w in lower for w in ["inconsistent", "contradicts", "previously", "established"]):
                label = "continuity"
            else:
                continue
            conflicts.append(
                f"{label}: {text[:200]} (specialist: {finding.specialistId})"
            )

        return conflicts

    def synthesize(
        self,
        *,
        user_message: str,
        intent: IntentClassification,
        findings: Iterable[SpecialistFinding],
        route_decision: Optional[Any] = None,
    ) -> SynthesisResult:
        ordered = self._sort_findings(findings)
        blockers: list[str] = []
        requirements: list[str] = []
        assumptions: list[str] = []
        tool_actions: list[ProposedToolAction] = []
        conflicts: list[str] = []
        recommendations: list[str] = []

        # Phase 7 — RouteDecision-aware conflict classification
        classified = self.classify_conflicts(findings)
        conflicts.extend(classified)

        for finding in ordered:
            blockers.extend(finding.blockingIssues)
            requirements.extend(finding.requirements)
            assumptions.extend(finding.assumptions)
            if finding.recommendation:
                recommendations.append(finding.recommendation)
            for action in finding.proposedToolActions:
                if not any(existing.toolId == action.toolId for existing in tool_actions):
                    tool_actions.append(action)

        primary = recommendations[0] if recommendations else ""
        if len(recommendations) > 1:
            conflicts.append("Resolved overlapping specialist recommendations by production priority chain.")

        # Storyboard structured fields stay internal; never invent a canned shot package
        # when specialists did not produce one.
        structured: dict[str, object] = {}

        response_type = "recommendation"
        if blockers:
            response_type = "warning"
        if intent.needsClarification:
            response_type = "clarification"
        if intent.isSimpleQuestion:
            response_type = "answer"
        if not primary:
            if blockers:
                primary = "I hit a blocker before I can recommend a next step."
            elif intent.needsClarification:
                primary = "I need one more detail before I can recommend a next step."
            elif tool_actions:
                primary = "I have a concrete action ready when you want to proceed."
            else:
                primary = "I'm with you — share the next detail or ask me what to prioritize."

        next_step = self._next_step(intent, tool_actions, blockers=blockers)
        compressed = self.compress(primary, blockers=blockers, next_step=next_step)
        # c2/D16: confidence must reflect heuristic-only findings. When every
        # finding is a heuristic/limited-analysis output (no live model reasoning)
        # — signalled by `LIMITED_ANALYSIS_ASSUMPTION` in assumptions, or a
        # repaired-after-validation-error finding (status=failed) — cap
        # confidence so synthesis cannot present heuristic guesses as high
        # certainty. A single validated finding lifts the cap.
        from .specialist_runner import LIMITED_ANALYSIS_ASSUMPTION  # local import avoids cycle

        def _is_limited(f: SpecialistFinding) -> bool:
            if getattr(f, "status", "") == "failed":
                return True
            return any(
                isinstance(a, str) and a.startswith(LIMITED_ANALYSIS_ASSUMPTION[:24])
                for a in (f.assumptions or [])
            )

        all_limited = bool(ordered) and all(_is_limited(f) for f in ordered)
        if blockers:
            confidence = 0.62
        elif all_limited:
            # Heuristic-only: cap below the validated-provider band so callers
            # can distinguish "real specialist reasoning" from "bounded heuristic".
            confidence = 0.55
        else:
            confidence = 0.88
        # Phase 7 — RouteDecision awareness: shape for discussion-oriented turns
        if route_decision is not None:
            action = getattr(route_decision, "actionClass", None)
            if action is not None:
                action_name = action.value if hasattr(action, "value") else str(action)
                if action_name in ("DISCUSS", "CLARIFY", "AMBIGUOUS", "UNKNOWN"):
                    tool_actions = tool_actions[:2]
                    if action_name == "CLARIFY":
                        response_type = "clarification"

        return SynthesisResult(
            responseType=response_type,  # type: ignore[arg-type]
            userMessage=compressed,
            recommendation=primary,
            requirements=list(dict.fromkeys(requirements)),
            blockers=list(dict.fromkeys(blockers)),
            assumptions=list(dict.fromkeys(assumptions)),
            proposedToolActions=tool_actions,
            structuredRecommendation=structured,
            conflictsResolved=conflicts,
            specialistIdsUsed=[f.specialistId for f in ordered],
            confidence=confidence,
        )

    def _sort_findings(self, findings: Iterable[SpecialistFinding]) -> list[SpecialistFinding]:
        rank = {sid: idx for idx, sid in enumerate(_PRIORITY_ORDER)}

        def sort_key(finding: SpecialistFinding) -> tuple[int, str]:
            return (rank.get(finding.specialistId, 99), finding.specialistId)

        return sorted(findings, key=sort_key)

    @staticmethod
    def compress(message: str, *, blockers: list[str], next_step: str) -> str:
        parts = [message.strip()]
        if blockers:
            parts.append("Blockers: " + "; ".join(blockers[:3]))
        if next_step:
            parts.append(f"Next: {next_step}")
        return " ".join(part for part in parts if part)

    @staticmethod
    def _next_step(
        intent: IntentClassification,
        actions: list[ProposedToolAction],
        *,
        blockers: list[str],
    ) -> str:
        """Only emit a Next step when there is a concrete action, approval, or blocker.

        Never append a generic 'Continue with the recommended direction' filler.
        """
        if blockers:
            return "Resolve the blocker above, then we can continue."
        if actions:
            # Prefer a creator-facing purpose over raw tool registry ids.
            purpose = str(getattr(actions[0], "purpose", "") or "").strip()
            if not purpose:
                tool_id = str(actions[0].toolId or "").replace("_", " ").strip()
                purpose = tool_id or "proposed action"
            return f"Review and approve: {purpose}."
        if intent.requiresApproval:
            return "Review the production plan and approve required steps."
        if intent.needsClarification:
            return ""
        return ""
