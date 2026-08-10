"""RouteDecision-aware specialist selection — minimum-crew, scoped, with structured confidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from app.codirector.routing.contracts import RouteActionClass, RouteDecision
from .specialist_registry import SpecialistRegistry

MAX_SPECIALISTS = 3

# Domain → specialist crew mapping (replaces legacy _INTENT_SPECIALISTS)
# These are the domains specialists can be consulted for, keyed by target domain
_DOMAIN_SPECIALISTS: dict[str, tuple[str, ...]] = {
    "story": ("story-analyst", "storyteller", "story-editor"),
    "script": ("screenwriter", "story-editor", "script-supervisor"),
    "dialogue": ("screenwriter", "performance-director"),
    "character": ("character-creator", "casting-director", "performance-director"),
    "bible": ("bible-manager", "story-analyst", "continuity-analyst"),
    "scene": ("director", "screenwriter", "story-analyst"),
    "shot": ("cinematographer", "prompt-architect", "technical-director"),
    "visual": ("art-director", "production-designer", "lighting-supervisor"),
    "audio": ("sound-designer", "sound-producer", "music-supervisor"),
    "continuity": ("continuity-analyst", "script-supervisor"),
    "production": ("producer", "pipeline-manager", "director"),
    "general": ("director", "producer", "story-analyst"),  # fallback for unknown domains
}

# RouteActionClass → (max_specialists, [domain_relevance_order])
_ROUTE_CREW_RULES: dict[RouteActionClass, tuple[int, list[str]]] = {
    RouteActionClass.NAVIGATE: (0, []),
    RouteActionClass.APPROVE: (0, []),
    RouteActionClass.REJECT: (0, []),
    RouteActionClass.READ_INSPECT: (1, ["general", "story", "scene"]),  # at most 1, analytical only
    RouteActionClass.CLARIFY: (1, ["general"]),
    RouteActionClass.AMBIGUOUS: (1, ["general"]),
    RouteActionClass.UNKNOWN: (1, ["general"]),
    RouteActionClass.DISCUSS: (1, ["story", "script", "character", "general"]),
    RouteActionClass.MODIFY_KNOWLEDGE: (1, ["bible", "story"]),
    RouteActionClass.PROPOSE_CREATIVE_CHANGE: (2, ["story", "script", "visual", "audio", "scene"]),
    RouteActionClass.EXECUTE_PRODUCTION: (3, ["production", "shot", "scene", "audio", "visual", "timeline"]),
}


@dataclass
class SpecialistContext:
    """Input context for specialist selection — all fields optional, selector degrades gracefully."""
    route_decision: Optional[RouteDecision] = None
    creator_goal: Optional[str] = None          # natural language goal from conversation focus
    workflow_stage: Optional[str] = None        # Phase 6 derived stage id
    workflow_active_task: Optional[str] = None  # Phase 6 active task


@dataclass
class SpecialistSelection:
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    reasons: list[str] = field(default_factory=list)
    selection_confidence: float = 0.0
    target_domain: Optional[str] = None

    @property
    def all_selected(self) -> tuple[str, ...]:
        return self.required + self.optional


class SpecialistSelector:
    def __init__(self, registry: SpecialistRegistry | None = None, *, max_specialists: int = MAX_SPECIALISTS) -> None:
        self.registry = registry or SpecialistRegistry()
        self.max_specialists = max(1, max_specialists)

    def select(
        self,
        context: SpecialistContext,
    ) -> SpecialistSelection:
        """Select specialists based on RouteDecision + context, not legacy IntentKind."""
        route = context.route_decision
        if route is None:
            return self._fallback_selection("general")

        action = route.actionClass
        rule = _ROUTE_CREW_RULES.get(action)

        if rule is None or rule[0] == 0:
            return SpecialistSelection(
                reasons=[f"route={action.value}: zero specialists required"],
                selection_confidence=1.0,
                target_domain=None,
            )

        max_for_action, domain_order = rule
        effective_max = min(max_for_action, self.max_specialists)

        domain = self._resolve_domain(route, context)
        selected = self._select_for_domain(domain, domain_order, effective_max)
        confidence = self._compute_confidence(route)

        if not selected:
            return self._fallback_selection("general")

        required_count = min(2 if effective_max > 1 else 1, len(selected))
        required = tuple(selected[:required_count])
        optional = tuple(selected[required_count:])

        return SpecialistSelection(
            required=required,
            optional=optional,
            reasons=[f"route={action.value}", f"domain={domain}", f"max={effective_max}"],
            selection_confidence=confidence,
            target_domain=domain,
        )

    def _resolve_domain(self, route: RouteDecision, context: SpecialistContext) -> str:
        """Resolve the specialist domain from route target + creator goal + workflow context."""
        target = (route.target or "").lower() if route.target else ""
        goal = (context.creator_goal or "").lower() if context.creator_goal else ""

        for domain_key in _DOMAIN_SPECIALISTS:
            if domain_key in target:
                return domain_key

        for domain_key in _DOMAIN_SPECIALISTS:
            if domain_key in goal:
                return domain_key

        stage = (context.workflow_stage or "").lower() if context.workflow_stage else ""
        for domain_key in _DOMAIN_SPECIALISTS:
            if domain_key in stage:
                return domain_key

        action_name = route.actionClass.value.lower() if route.actionClass else ""
        if "discuss" in action_name or "clarify" in action_name or "unknown" in action_name:
            return "general"
        if "read" in action_name:
            return "general"
        if "propose" in action_name or "modify" in action_name:
            return "story"
        if "execute" in action_name or "production" in action_name:
            return "production"

        return "general"

    def _select_for_domain(self, domain: str, domain_order: list[str], max_count: int) -> list[str]:
        """Select specialists for a resolved domain, up to max_count."""
        candidates = list(_DOMAIN_SPECIALISTS.get(domain, _DOMAIN_SPECIALISTS["general"]))

        if len(candidates) < max_count:
            for alt_domain in domain_order:
                if alt_domain == domain:
                    continue
                alt_ids = _DOMAIN_SPECIALISTS.get(alt_domain, ())
                for alt_id in alt_ids:
                    if alt_id not in candidates and alt_id in self.registry.ids():
                        candidates.append(alt_id)
                        if len(candidates) >= max_count:
                            break
                if len(candidates) >= max_count:
                    break

        selected = [sid for sid in candidates if sid in self.registry.ids()]
        return selected[:max_count]

    def _compute_confidence(self, route: RouteDecision) -> float:
        """Compute selection confidence from route decision confidence and specificity."""
        base = route.confidence
        if route.target:
            base += 0.1
        if route.targetWorkspace:
            base += 0.05
        return min(base, 1.0)

    def _fallback_selection(self, domain: str) -> SpecialistSelection:
        """Safe fallback when route decision is unavailable."""
        candidates = list(_DOMAIN_SPECIALISTS.get(domain, _DOMAIN_SPECIALISTS["general"]))
        selected = [sid for sid in candidates[:1] if sid in self.registry.ids()]
        return SpecialistSelection(
            required=tuple(selected),
            selection_confidence=0.5,
            target_domain=domain,
            reasons=["fallback: no route decision available"],
        )

    def validate_selection(self, specialist_ids: list[str]) -> list[str]:
        return self.registry.validate_ids(specialist_ids)
