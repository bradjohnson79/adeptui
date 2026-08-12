# Phase 7 — Specialist Crew Rewire

## Selector (`intelligence/specialist_selector.py`)
- **RouteDecision-aware**: uses `RouteActionClass`, not legacy `IntentKind`
- **MAX_SPECIALISTS = 3** (was 8)
- Crew by RouteDecision:
  - NAVIGATE/APPROVE/REJECT → 0
  - Simple READ → 0, analytical READ → ≤1
  - DISCUSS → 1, CLARIFY/AMBIGUOUS → ≤1
  - PROPOSE_CREATIVE_CHANGE → 1-2, EXECUTE_PRODUCTION → max 3
- `SpecialistContext` dataclass (route_decision, creator_goal, workflow_stage, workflow_active_task)
- Legacy `_INTENT_SPECIALISTS` and `_CONTINUITY_INTENTS` removed

## Policies (`intelligence/specialist_policies.py`)
- `enforce_specialist_permissions` — runtime assert for may_execute_tools=False
- `assert_runner_permissions` — convenience for runner entry

## Synthesis (`intelligence/synthesis.py`)
- `classify_conflicts` — stylistic, feasibility, continuity classification
- RouteDecision-aware result shaping
- Trims tool actions for DISCUSS/CLARIFY/AMBIGUOUS

## Service Gating (`intelligence/service.py`, `service.py`)
- Selection behind RouteDecision when available
- Zero-specialist guard for NAVIGATE/READ_INSPECT/APPROVE/REJECT

## Tests: 29 (24 specialist + 5 allowlist)
## Certification: GO (recovered — was incomplete, Agents C-F were missing)
