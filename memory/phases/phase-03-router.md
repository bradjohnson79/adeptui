# Phase 3 — Intent + Stage Router

## RouteDecision (`app/codirector/routing/contracts.py`)
- 11 action classes: DISCUSS, NAVIGATE, READ_INSPECT, MODIFY_KNOWLEDGE, PROPOSE_CREATIVE_CHANGE, EXECUTE_PRODUCTION, APPROVE, REJECT, CLARIFY, AMBIGUOUS, UNKNOWN
- 16-field model: actionClass, target, confidence, destructive, writeAllowed, capabilityAvailable, classifierSource, targetToolIds, etc.

## Deterministic classifier (`routing/deterministic.py`)
- 8 pattern groups: NAVIGATE, APPROVE, REJECT, READ_INSPECT, DISCUSS, MODIFY_KNOWLEDGE, EXECUTE_PRODUCTION (destructive + generate)
- Negation detection runs FIRST (§8.7)
- False-positive guard (§8.8)

## Semantic fallback (`routing/semantic.py`)
- `classify_semantic` — async, calls configured provider, structured validation
- `route_with_semantic_fallback` — 3 confidence zones (≥0.85 direct, 0.70-0.85 validation, <0.70 classifier)
- Consequential actions require higher confidence

## Context integration (`routing/context.py`)
- `StageSensitiveRouter` — stage-dependent routing ("Create shots"=script vs image-planning)
- `CapabilityGate` — preserves action class for unavailable capabilities
- `build_router_context` — assembles all Phase 2 inputs

## Tests: 10
## Certification: GO — Taxonomy Authority Law enacted
