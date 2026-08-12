# Phase 9 — Canonical Professional Acceptance Scenarios

## Harness (`tests/helpers/scenario_session.py`)
- `ScenarioSession` holds persistent mock project state across 4-14 turns
- Each turn calls classify_deterministic → plan_conversation → response_composer
- Behavioral assertions only (no exact prose)
- Negative side-effect verification (writeAllowed, operator_requested)

## Scenarios (54 tests)
- **Schnick Coffee** (14 turns): full 20s commercial workflow
- **Narrative** (8 turns): format-aware, not commercial assumptions
- **Music Video** (5 turns): non-script-heavy, no screenplay gate
- **Resilience** (12 turns): manual work, project switching, corrections
- **Edge Cases** (15 turns): known/unknown facts, specialist restraint, failure recovery

## Certification: GO
