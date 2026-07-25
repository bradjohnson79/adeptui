"""Conflict resolution and response compression for synthesis."""

from __future__ import annotations

from typing import Iterable

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
    def synthesize(
        self,
        *,
        user_message: str,
        intent: IntentClassification,
        findings: Iterable[SpecialistFinding],
    ) -> SynthesisResult:
        ordered = self._sort_findings(findings)
        blockers: list[str] = []
        requirements: list[str] = []
        assumptions: list[str] = []
        tool_actions: list[ProposedToolAction] = []
        conflicts: list[str] = []
        recommendations: list[str] = []

        for finding in ordered:
            blockers.extend(finding.blockingIssues)
            requirements.extend(finding.requirements)
            assumptions.extend(finding.assumptions)
            if finding.recommendation:
                recommendations.append(finding.recommendation)
            for action in finding.proposedToolActions:
                if not any(existing.toolId == action.toolId for existing in tool_actions):
                    tool_actions.append(action)

        primary = recommendations[0] if recommendations else "Continue with the recommended production direction."
        if len(recommendations) > 1:
            conflicts.append("Resolved overlapping specialist recommendations by production priority chain.")

        structured: dict[str, object] = {}
        if intent.primaryIntent == "create_storyboard":
            structured = {
                "shotPurpose": "Establish tension before the next story beat.",
                "shotType": "medium two-shot",
                "lens": "35mm",
                "cameraPosition": "corridor side, slightly offset from primary set geography",
                "cameraHeight": "eye level",
                "movement": "locked",
                "lighting": ["preserve practical corridor lighting", "maintain readable facial exposure"],
                "continuityConstraints": requirements[:4],
                "workflowRecommendation": "configured_storyboard_image_workflow",
                "confidence": 0.91,
            }

        response_type = "recommendation"
        if blockers:
            response_type = "warning"
        if intent.needsClarification:
            response_type = "clarification"
        if intent.isSimpleQuestion:
            response_type = "answer"
            primary = (
                "Based on the current project context, here's a concise answer: "
                + (primary if primary else "I can help once you specify the scene or asset.")
            )

        compressed = self.compress(primary, blockers=blockers, next_step=self._next_step(intent, tool_actions))
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
            confidence=0.88 if not blockers else 0.62,
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
    def _next_step(intent: IntentClassification, actions: list[ProposedToolAction]) -> str:
        if actions:
            return f"Review and approve the proposed {actions[0].toolId} action."
        if intent.requiresApproval:
            return "Review the production plan and approve required steps."
        return "Continue with the recommended direction."
