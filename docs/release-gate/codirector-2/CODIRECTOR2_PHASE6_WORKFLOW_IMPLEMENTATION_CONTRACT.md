# CO-DIRECTOR 2.0 — PHASE 6 WORKFLOW ENGINE IMPLEMENTATION CONTRACT (FREEZE)

| Field | Value |
|---|---|
| Phase | 6 (implementation) |
| Date | 2026-08-08 |
| Status | **FROZEN** |
| Dependency | Phase 2–5 certified |

## 1. Existing machinery audit

| Component | File | Classification |
|---|---|---|
| `production_lifecycle/service.py` | Authoritative `currentStage` (9 stages) | **KEEP** — evidence source |
| `production_lifecycle/contracts.py` | 9-stage vocabulary | **KEEP** — reused labels |
| `conversation/next_steps.py` | Generic heuristic invitations | **SUPERSEDE** — replace with evidence-based |
| `conversation/planner.py` | Heuristic conversation planner | **ADAPT** — consume Workflow Assessment |
| `conversation/momentum.py` | Creative continuity | **KEEP** — separate concern |
| `persist_deferred_option` | Creator override memory | **REUSE** for recommendation deferral |

## 2. No new stage source

Workflow Engine consumes only `get_authoritative_stage()` and `collect_stage_evidence()` from Phase 2. Never writes stage. Stage remains evidence-derived.

## 3. Workflow definition model

`app/codirector/workflow/definitions.py` — `WorkflowDefinition`, `WorkflowStage`, `WorkflowRequirement` (BLOCKING/REQUIRED/RECOMMENDED/OPTIONAL), format-aware definitions for commercial/narrative/music_video/unknown.

## 4. Reconciliation

`app/codirector/workflow/reconciliation.py` — `reconcile_workflow()` produces multi-stage assessment (maturity per stage, not single step number). Readiness engine with deterministic checks against Production State.

## 5. Recommendation engine

`app/codirector/workflow/recommendations.py` — `recommend_next_actions()` with ranking: creator goal > blocker > active task > stage readiness > best practice > optional. Max 4 recommendations. Known-fact suppression (creator-stated/creator-approved facts only). AI inference does not suppress.

## 6. Partnership + conversation

Major-stage check-ins via `major_stage_boundary` flag. Creator override → `persist_deferred_option`. `next_steps.py` `build_next_step_options` superseded by Workflow Engine.

## 7. Routing

Recommendations never bypass Phase 3. NAVIGATE → Verified Operator. Mutations → proposal/approval.

## 8. Subagents

B (definitions) + C (reconciliation) in parallel. D (recommendations) + E (partnership) in parallel after B+C. Then F (routing) + G (tests). H (verifier).

---

*Frozen. No Phase 6 source edits precede this document.*
