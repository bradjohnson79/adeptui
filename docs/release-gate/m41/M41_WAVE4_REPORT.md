# M41 Phase 4.1 — Wave 4: Durable Production Plans

| Field | Value |
|---|---|
| **Phase** | 4.1 — Co-Director Production Completion |
| **Wave** | 4 — Durable production planning operator |
| **Date** | 2026-07-29 |
| **Product** | Adept UI Studio / Co-Director / Adept FilmWorks |
| **Baseline** | Wave 1 GO · Wave 2 GO · Wave 3 GO · [`M41_CODIRECTOR_AUDIT.md`](./M41_CODIRECTOR_AUDIT.md) |
| **Related** | [`M41_IMPLEMENTATION_REPORT.md`](./M41_IMPLEMENTATION_REPORT.md) · [`M41_TEST_REPORT.md`](./M41_TEST_REPORT.md) |
| **Owns** | **M41-CD-55 through M41-CD-78** |
| **Verdict** | **GO — M41 Wave 4 durable production planning complete** |

---

## 1. Objective

Promote `CoDirectorProductionPlan` into a durable plan-operator domain:

- audited `create_draft` without a plan-acceptance approval gate;
- atomic head + version + event + idempotency commits;
- snapshot + fresh capability readiness;
- authoritative transitions via propose → human approve → apply;
- Project Content plan workspace with revision diff;

without executing production steps.

**Maturity label:** Co-Director is a durable production planning operator, but not yet a production execution operator.

---

## 2. Scope

| In scope | Out of scope |
|---|---|
| Canonical `studio-api/app/codirector/plans/` domain | Production step execution |
| Migration M022 (versions / events / idempotency) | Generation / Editor / subtitle apply |
| Audited `production_plan.create_draft` | Job retry / cancel |
| Authoritative plan-management mutations | Specialist execution |
| Snapshot + fresh `get_readiness` | Wave 5+ operator waves |
| Session active-plan recovery | Merging M213 / M29 plan domains |
| Project Content plan workspace | Redefining M41-CD-01…54 |

---

## 3. Pre-implementation plan-system audit

Full matrix recorded in [`M41_IMPLEMENTATION_REPORT.md`](./M41_IMPLEMENTATION_REPORT.md) under **Wave 4 — Durable Plan System Audit**.

| Truth status | Systems |
|---|---|
| **Canonical Candidate → sole writable store** | `CoDirectorProductionPlan` + new `plans/` domain |
| Reusable reader | Wave 3 `production_plan.list/get` (rebound to PlanService) |
| Scaffolded | m214 `plan_view` |
| Frontend Only / Legacy | ActionPlan / `runSteps` |
| Session Only | SSE `productionAnalysis.planSteps` |
| Reusable execution/approval bus | `ProposalService` |
| Deferred / out of Wave 4 truth path | M213 scene plans, M29 control plans, executive jobs |

---

## 4. Canonical store decision

```text
Canonical production plan source:
studio-api/app/codirector/plans/ (CoDirectorProductionPlan + versions/events)

Legacy plan surfaces:
m214 plan_view; frontend ActionPlan; SSE productionAnalysis.planSteps; M213/M29 (out of Wave 4 truth path)

Compatibility behavior:
Wave 3 production_plan.* reads continue; m214 listed only as scaffolded; IntelligenceStore.save_plan routes through PlanService.create_draft adapter
```

| Table | Role |
|---|---|
| `codirector_production_plans` | Latest plan head |
| `codirector_production_plan_versions` | Immutable JSON snapshot per version |
| `codirector_production_plan_events` | Append-only history |
| `codirector_plan_command_idempotency` | `(project_id, request_id)` → result JSON; retain ≥7 days |

---

## 5. Legacy plan handling

| Surface | Honesty / behavior |
|---|---|
| m214 plan view | Listed only with `honesty: "scaffolded"`; never authoritative |
| Frontend ActionPlan | Non-authoritative; workspace reads canonical store |
| SSE `planSteps` | Transient conversational mirror only |
| `IntelligenceStore.save_plan` | Adapter → `PlanService.create_draft` (always `draft` / unapproved) |

---

## 6. Plan schema

Typed models in `studio-api/app/codirector/plans/schemas.py` (schema version `4.1.0`):

| Model | Contents |
|---|---|
| `ProductionPlan` | project, conversation, title/objective, state, version, steps, blockers, approvals, outputs, capabilitySnapshot, lifecycle timestamps, `unapproved` |
| `ProductionPlanStep` | order, deps, blockers, capabilities, proposedToolId, executionAvailability, durable step state |
| `ProductionPlanBlocker` | severity, source, resolution, open/resolved/dismissed |
| `PlanApprovalRequirement` | plan_acceptance vs later production-action types |
| `PlanCapabilitySnapshot` / `PlanReadinessReport` | snapshot vs current readiness |
| `PlanEvent` / `PlanCommandResult` | audit + command outcomes |

---

## 7. Plan state machine

Domain rules in `state_machine.py` (not UI).

### Plan state transitions

| From | Allowed to |
|---|---|
| `draft` | `proposed`, `awaiting_approval`, `cancelled` |
| `proposed` | `awaiting_approval`, `approved`, `cancelled`, `draft` |
| `awaiting_approval` | `approved`, `proposed`, `cancelled`, `draft` |
| `approved` | `ready`, `blocked`, `paused`, `cancelled`, `proposed` |
| `ready` | `blocked`, `paused`, `cancelled`, `approved`, `proposed` |
| `blocked` | `ready`, `paused`, `cancelled`, `approved`, `proposed` |
| `paused` | `ready`, `blocked`, `cancelled`, `approved`, `proposed` |
| `cancelled` | `archived` |
| `archived` | *(none)* |
| `in_progress` / `completed` / `failed` | Present for fixture/test only — **Wave 4 commands cannot enter these** |

### Command → transition (Wave 4)

| Command | Typical transition |
|---|---|
| `create_draft` | → `draft` (v1) |
| `propose` | `draft` → `proposed` |
| `approve` | `proposed`/`awaiting_approval` → `approved` (+ optional post-approve → `ready`/`blocked`) |
| `reject` | → `draft` |
| `revise` | authoritative states → `proposed` (re-acceptance); draft stays draft |
| `pause` / `resume` | ↔ `paused` (resume restores prior ready/blocked/approved) |
| `cancel` / `archive` | → `cancelled` → `archived` |

Rejected examples: `draft→completed`, `cancelled→in_progress`, `archived→ready`.

---

## 8. Step state model

| From | Allowed to (selected) |
|---|---|
| `pending` | `ready`, `blocked`, `awaiting_approval`, `deferred`, `unsupported`, `cancelled`, `skipped` |
| `ready` | `blocked`, `awaiting_approval`, `deferred`, `paused`, `in_progress`, `cancelled`, `skipped` |
| `blocked` | `ready`, `pending`, `deferred`, `cancelled`, `skipped` |
| `deferred` | `pending`, `ready`, `blocked`, `unsupported`, `cancelled` |
| `completed` / `skipped` / `cancelled` | terminal |

Wave 4 readiness computation sets `deferred`/`unsupported` from capabilities and never marks a step `completed` because the model claims so. Production `in_progress`/`completed` remain later-wave.

---

## 9. Dependency validation

`dependencies.py` / `validation.py`:

| Check | Result |
|---|---|
| Cycles | Reject (`PLAN_DEPENDENCY_CYCLE`) |
| Self-dependencies | Reject |
| Missing dependencies | Reject |
| Unreachable steps | Warning |
| Duplicate step IDs / missing title/project | Invalid |

---

## 10. Blocker model

Durable blockers on the plan body:

- severity: `info` / `warning` / `blocking`
- state: `open` / `resolved` / `dismissed`
- attributable `sourceType` / `sourceId`
- resolve via `production_plan.resolve_blocker` (propose → approve)

Open blocking blockers contribute to plan readiness `blocked`.

---

## 11. Approval model

| Kind | Wave 4 behavior |
|---|---|
| Plan acceptance (`plan_acceptance`) | Required before plan becomes authoritative; tool `production_plan.approve` |
| Production-action approval | **Not** granted by plan acceptance; generation/apply remain Wave 5+ |
| Draft persist | No plan-acceptance gate; remains `unapproved` |

---

## 12. Capability-readiness evaluation

| Field | Meaning |
|---|---|
| `snapshotReadiness` | From capability snapshot captured at create/revise |
| `currentReadiness` | Live re-eval against current deferred/available annotations |
| `changedCapabilities[]` | Diff when snapshot ≠ current |
| `requiresRefresh` | True when refresh/revision required before later-wave execution |

| Readiness level | When |
|---|---|
| `ready` | All steps available; no open blocking blockers |
| `partially_ready` | Mix of available + deferred |
| `deferred` | Production tools/caps only; not falsely ready |
| `blocked` | Open blocking blockers / permission |
| `unsupported` | All steps unsupported |

Generation / editor / subtitle families → `executionAvailability: deferred`.

---

## 13. Versioning and concurrency

- Immutable version row per accepted command.
- Optimistic concurrency via `expectedVersion` (except first `create_draft`).
- Stale updates → `PLAN_VERSION_CONFLICT` with reload guidance.
- Mutating tools pin `plan:{planId}` (+ `project`) in `baseResourceVersions`.

---

## 14. Idempotency

| Key | Behavior |
|---|---|
| `(project_id, request_id)` | Returns prior `PlanCommandResult` without duplicating head/version/event |
| Retention | Documented ≥7 days (`codirector_plan_command_idempotency`); purge job not shipped |

---

## 15. Event history

Append-only `codirector_production_plan_events`, including:

`PLAN_CREATED`, `PLAN_PROPOSED`, `PLAN_APPROVED`, `PLAN_REJECTED`, `PLAN_REVISED`, `PLAN_PAUSED`, `PLAN_RESUMED`, `PLAN_CANCELLED`, `PLAN_ARCHIVED`, `BLOCKER_RESOLVED`, `CAPABILITY_SNAPSHOT_UPDATED`.

Inspectable via `production_plan.list_events`.

---

## 16. Recovery behavior

`session_context` populates from canonical store (not localStorage):

- `activePlanId`, `activePlanVersion`, `activePlanState`, `activeStepId`
- `planReadiness`, `openPlanBlockers`, `lastPlanCommand`
- `activeProductionPlan` summary

Reconnect / restart: requestId dedupe; FE replaced by latest head; paused/cancelled preserved.

---

## 17. Project isolation

| Case | Result |
|---|---|
| Cross-project get/mutate | Denied (`PLAN_ACCESS_DENIED` / not found) |
| No project / missing project | `PROJECT_REQUIRED` / not found |
| Plan mutations on Wave 3 read route | `TOOL_KIND_MISMATCH` |

---

## 18. Security findings

| Control | Status |
|---|---|
| Cross-project checks on every command | Yes |
| Plan text treated untrusted | Scrubbed via tool result sanitizer |
| Unknown capability/tool IDs | Deferred honesty — never false `ready` |
| Bound payload size | Parameter max lengths + elevated plan result budgets |
| Model cannot redefine transitions/approvals | Domain state machine + closed command set |
| `execute_read` not weakened | Separate `execute_audited` for draft only |

### Draft persistence boundary

`production_plan.create_draft` may persist without plan approval **only if**:

1. state is always `draft`;
2. it cannot become active/ready/approved alone;
3. it cannot authorize production actions;
4. API + Project Content label it unapproved;
5. creation is idempotent (`requestId`) and audited (`PLAN_CREATED` + version snapshot).

### Command transaction boundary

Each accepted command commits atomically:

1. latest plan-head update;
2. immutable version snapshot;
3. append-only event;
4. idempotency result;

or full rollback.

---

## 19. Frontend plan workspace

`studio-web/src/components/CoDirector/plans/` wired into Plans tab of `CoDirectorProjectContent.tsx`:

| Component | Role |
|---|---|
| `PlanWorkspacePanel` | Orchestrates load + commands |
| `PlanSummaryCard` | Title, state, version, unapproved, readiness, step counts |
| `PlanStepList` | Persisted step states; deferred honesty |
| `PlanDependencyView` | Dep edges |
| `PlanBlockers` / `PlanApprovals` | Open blockers; plan-acceptance vs action approval |
| `PlanReadiness` | Snapshot vs current divergence |
| `PlanHistory` | Versions + events |
| `PlanRevisionDiff` | Structured diff before approval |
| `PlanCommandProposal` | Propose/approve/reject/pause/resume/cancel/archive — **no execution buttons** |

API helpers: `runCoDirectorAuditedTool`, `getProductionPlan*`, `proposeProductionPlanCommand` in `studio-web/src/api.ts`.

---

## 20. Files changed (primary)

| Area | Paths |
|---|---|
| Domain | `studio-api/app/codirector/plans/*` |
| DB / migration | `studio-api/app/db.py`, `migrations/m022_durable_production_plans.py` |
| Errors | `studio-api/app/codirector/errors.py` (`PLAN_*`) |
| Tools | `definitions.py`, `registry.py`, `aliases.py`, `execution.py`, `handlers/wave4_plans.py`, `read_cache.py` |
| Adapter | `intelligence/store.py` |
| Session / chat | `session_context.py`, `service.py` |
| Router | `routers/codirector.py` (`POST .../tools/audited`) |
| FE | `studio-web/src/components/CoDirector/plans/*`, `CoDirectorProjectContent.tsx`, `api.ts` |
| Tests | `test_m41_codirector_wave4.py`, `test_m41_plan_state_machine.py`, `test_m41_plan_dependencies.py`, `tests/e2e/m41/m41-cd-wave4.spec.ts` |
| Reports | this file; IMPLEMENTATION + TEST updates |

Registry after Wave 4: **87 read / 47 mutating** (includes Wave 3 gap tools + 17 `production_plan.*` tools).

---

## 21. Plan tools matrix

| Tool ID | Kind | Approval | Repository |
|---|---|---|---|
| `production_plan.list` | read | — | PlanService + m214 scaffold overlay |
| `production_plan.get` | read | — | PlanService |
| `production_plan.get_version` | read | — | version snapshots |
| `production_plan.list_versions` | read | — | version metadata |
| `production_plan.list_events` | read | — | append-only events |
| `production_plan.validate` | read | — | validation.py |
| `production_plan.get_readiness` | read | — | snapshot + fresh |
| `production_plan.create_draft` | mutating | **No** (audited) | PlanCommandService |
| `production_plan.propose` | mutating | Yes | PlanCommandService |
| `production_plan.approve` | mutating | Yes | PlanCommandService |
| `production_plan.reject` | mutating | Yes | PlanCommandService |
| `production_plan.revise` | mutating | Yes | PlanCommandService |
| `production_plan.pause` | mutating | Yes* | PlanCommandService |
| `production_plan.resume` | mutating | Yes* | PlanCommandService |
| `production_plan.cancel` | mutating | Yes | PlanCommandService |
| `production_plan.archive` | mutating | Yes | PlanCommandService |
| `production_plan.resolve_blocker` | mutating | Yes | PlanCommandService |

\*UI may use explicit confirm; still auditable propose/apply commands.

---

## 22. Plan commands matrix

| Command | Atomic head+version+event+idem | Idempotent | Notes |
|---|---|---|---|
| `create_draft` | Yes | Yes | No plan-acceptance gate |
| `propose` | Yes | Yes | Authoritative formalize |
| `approve` | Yes | Yes | Plan acceptance only |
| `reject` | Yes | Yes | Returns to draft |
| `revise` | Yes | Yes | New version; may require re-acceptance |
| `pause` / `resume` | Yes | Yes | Preserves prior state in metadata |
| `cancel` / `archive` | Yes | Yes | Terminal path |
| `resolve_blocker` | Yes | Yes | Plan-management only |

---

## 23. M41-CD-55…78 results

| ID | Title | Layer | Result |
|---|---|---|---|
| M41-CD-55 | Canonical durable plan store is selected and documented | API + report | **PASS** |
| M41-CD-56 | Plan persists across backend restart and frontend reload | API | **PASS** |
| M41-CD-57 | Plan schema preserves project, version, steps, blockers, approvals, and outputs | API | **PASS** |
| M41-CD-58 | Legacy/scaffold plan sources cannot become authoritative silently | API | **PASS** |
| M41-CD-59 | Valid plan-state transitions succeed | Unit | **PASS** |
| M41-CD-60 | Invalid plan-state transitions are rejected | Unit | **PASS** |
| M41-CD-61 | Terminal plans cannot resume or mutate illegally | Unit | **PASS** |
| M41-CD-62 | Pause and resume preserve plan state and history | Unit | **PASS** |
| M41-CD-63 | Dependency cycles are rejected | Unit | **PASS** |
| M41-CD-64 | Missing and self-dependencies are rejected | Unit | **PASS** |
| M41-CD-65 | Step readiness derives from dependencies and blockers | Unit | **PASS** |
| M41-CD-66 | Deferred capabilities prevent false ready state | Unit + API | **PASS** |
| M41-CD-67 | Plan approval is distinct from production-action approval | API | **PASS** |
| M41-CD-68 | Revision creates a new version and preserves the previous version | API | **PASS** |
| M41-CD-69 | Version conflict rejects stale updates | API | **PASS** |
| M41-CD-70 | Plan command request IDs are idempotent | API | **PASS** |
| M41-CD-71 | Project A cannot access or mutate Project B plans | API | **PASS** |
| M41-CD-72 | No-project mode cannot create or mutate a plan | API + E2E | **PASS** |
| M41-CD-73 | Reconnect does not duplicate plans, commands, or events | API | **PASS** |
| M41-CD-74 | Active plan and blockers recover after reconnect/restart | API | **PASS** |
| M41-CD-75 | Co-Director creates a grounded plan proposal from real project context | API + E2E | **PASS** |
| M41-CD-76 | Project Content renders plan state, steps, blockers, readiness, and history | Contract + E2E | **PASS** |
| M41-CD-77 | Deferred production steps show honest unavailable states and no fake progress | API + E2E | **PASS** |
| M41-CD-78 | Plan revision UI shows a structured diff before approval | Contract + E2E | **PASS** |

### Commands run

```text
cd studio-api
python -m pytest tests/test_m41_codirector_wave4.py tests/test_m41_plan_state_machine.py tests/test_m41_plan_dependencies.py -q
# 25 passed

python -m pytest tests/test_m41_codirector_wave1.py tests/test_m41_codirector_wave3.py tests/test_m41_codirector_wave4.py tests/test_m41_plan_state_machine.py tests/test_m41_plan_dependencies.py -q
# 63 passed
```

---

## 24. Wave 1 regression

| Suite | Result |
|---|---|
| `tests/test_m41_codirector_wave1.py` (M41-CD-01…14) | **PASS** |
| Runtime honesty / project binding / no-project safeguards | Intact |

---

## 25. Wave 2 regression

| Suite | Result |
|---|---|
| Prior Wave 2 GO (M41-CD-15…34) | Preserved — Approvals honesty, SplitPane, progressive disclosure, Aurora empty states |
| Note | No Wave 2 API suite in-repo; Wave 2 e2e remained the prior acceptance baseline |

---

## 26. Wave 3 regression

| Suite | Result |
|---|---|
| `tests/test_m41_codirector_wave3.py` (M41-CD-35…54) | **PASS** |
| Retrieval envelopes / read-only route | Intact |
| Plan mutations cannot enter Wave 3 read route | **PASS** (`TOOL_KIND_MISMATCH`) |
| CD-49 | Assertion updated for nested `data.plan.state` (Wave 4 payload growth) |

---

## 27. Manual / Playwright scenarios

| Scenario | Expected | Coverage |
|---|---|---|
| Create plan | Persisted `draft`, deferred caps honest, no execution | API + e2e draft |
| Approve plan | Plan acceptance only; version/event; no production start | API propose→approve |
| Revise plan | Diff + new version after approval | API + revision UI contract |
| Pause / resume | Durable state + events | Domain + commands |
| Capability honesty | Video gen deferred in Wave 4 | API + screenshots |
| Recovery | Reload restores active plan; no duplicates | API session fields |
| Negatives | Cross-project, stale version, no-project, cancel resume | API |

E2E spec: `tests/e2e/m41/m41-cd-wave4.spec.ts`.

---

## 28. Screenshot evidence

Under `artifacts/m41/wave4/` (12 files):

| File |
|---|
| `m41-cd-55-canonical-plan.png` |
| `m41-cd-56-plan-recovery.png` |
| `m41-cd-59-state-transition.png` |
| `m41-cd-63-dependency-validation.png` |
| `m41-cd-66-capability-deferred.png` |
| `m41-cd-67-plan-vs-action-approval.png` |
| `m41-cd-68-version-history.png` |
| `m41-cd-69-version-conflict.png` |
| `m41-cd-75-grounded-plan-proposal.png` |
| `m41-cd-76-plan-workspace.png` |
| `m41-cd-77-no-fake-progress.png` |
| `m41-cd-78-revision-diff.png` |

---

## 29. Known limitations

- Wave 4 never executes a production step.
- Pause/resume may use UI confirm; other authoritative commands use Approvals proposals.
- Idempotency purge job not automated (retain ≥7 days documented).
- Tool-loop still one read tool per chat turn (Wave 3 constraint).
- m214 remains scaffolded honesty only.

---

## 30. Deferred Wave 5+ work

Specialist execution, generation apply, Director/Editor/subtitle apply, job retry/cancel, applying production proposals, executing plan steps, entering `in_progress`/`completed`/`failed` via real production work.

---

## 31. Final verdict

**GO — M41 Wave 4 durable production planning complete**
