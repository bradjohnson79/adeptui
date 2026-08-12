# Phase 6 — Professional Workflow Engine

## Workflow Definitions (`workflow/definitions.py`)
- 4 format-aware definitions: commercial (9 stages), narrative (12), music_video (7), unknown (4)
- `WorkflowRequirementType`: BLOCKING / REQUIRED / RECOMMENDED / OPTIONAL
- `major_stage_boundary` flag for partnership check-ins
- `get_workflow_for_format` dispatches by project type

## Reconciliation (`workflow/reconciliation.py`)
- `reconcile_workflow` — multi-stage maturity assessment, not a single step number
- `_gather_project_info` — reads 8 authoritative evidence sources
- `_assess_stage_maturity` — deterministic, 0.0-1.0 per stage
- Zero writes (Law 4)

## Recommendation Engine (`workflow/recommendations.py`)
- `recommend_next_actions` — ranked: creator goal > blocker > stage readiness > best practice
- Max 4 recommendations. Deferred recommendation suppression.
- All recommendations have `route_target` fields for Phase 3 routing

## Conversation Integration (`conversation/next_steps.py`)
- `build_workflow_next_steps` — supersedes generic heuristic next-steps
- `build_next_step_options` — deprecated (Phase 6), kept for backward compat
- Major-stage check-in for Balanced mode

## Tests: 28
## Certification: GO — Workflow Engine is single production next-step authority
