# M41 — Implementation Report

| Field | Value |
|---|---|
| **Phase** | 4.1 — Co-Director Production Completion |
| **Product** | Adept UI Studio / Co-Director |
| **Baseline** | [`M41_CODIRECTOR_AUDIT.md`](./M41_CODIRECTOR_AUDIT.md) |

> **Phase 4.1A (parallel):** Video Runtime & Generation Infrastructure — see
> [`M41_41A_VIDEO_RUNTIME_CERTIFICATION_REPORT.md`](./M41_41A_VIDEO_RUNTIME_CERTIFICATION_REPORT.md).
> Wave 6 media execution is gated on 4.1A GO.

---

## Wave 1 — Runtime honesty, project-bound sessions, reconnect

| Field | Value |
|---|---|
| **Date** | 2026-07-28 |
| **Scope** | Wave 1 only (Waves 2–8 not started) |
| **Verdict** | **GO — M41 Wave 1 runtime and session foundation complete** |

### Files changed

**Backend**

- `studio-api/app/codirector/errors.py` — Phase 4.1 error envelope; `PROJECT_REQUIRED`
- `studio-api/app/codirector/providers/base.py` — `testOnly` / `honesty` on health
- `studio-api/app/codirector/providers/mock.py` — mock health marked test-only
- `studio-api/app/codirector/service.py` — no-project tool → `PROJECT_REQUIRED`; mock health flags
- `studio-api/app/codirector/session_context.py` — canonical composed session-context contract
- `studio-api/app/routers/codirector.py` — `GET /api/codirector/session-context`

**Frontend**

- `studio-web/src/components/CoDirector/runtimeState.ts` — runtime state machine
- `studio-web/src/components/CoDirector/types.ts` — session context type; project-scoped safe caches; last-project suggestion
- `studio-web/src/components/CoDirector/CoDirectorSession.tsx` — binding, cancel-on-switch, reconnect, model config persist, no silent plan fallback
- `studio-web/src/components/CoDirector/CoDirectorShell.tsx` — honest ready/chip; no-project + reconnect banners
- `studio-web/src/components/CoDirector/CoDirectorHeader.tsx` — runtime chip
- `studio-web/src/components/CoDirector/CoDirectorOverflowMenu.tsx` — status / reconnect / model persist
- `studio-web/src/components/CoDirector/CoDirectorProjectContent.tsx` — “No Project Selected”
- `studio-web/src/components/CoDirector/CoDirectorNavDrawer.tsx` — “No Project Selected”
- `studio-web/src/components/CoDirector/codirector-cinematic.css` — chip / banner styles
- `studio-web/src/pages/CoDirectorPage.tsx` — unbind when route has no `projectId`
- `studio-web/src/api.ts` — envelope fields; `codirectorSessionContext`; health `testOnly`

**Tests / docs**

- `studio-api/tests/test_m41_codirector_wave1.py`
- `tests/e2e/m41/m41-cd-wave1.spec.ts`
- `docs/release-gate/m41/M41_TEST_REPORT.md` (Wave 1)

### Runtime-state implementation

User-facing states: Connected, Loading Model, Ollama Unavailable, Model Unavailable, Reconnecting, Degraded, Tool Execution Unavailable.

Derived in `runtimeState.ts` from health + reconnect/model-loading flags + project binding. Shell no longer hardcodes Ready. Mock health exposes `testOnly: true` / `honesty: "mocked"`.

### Project-binding changes

- Canonical bind from route / explicit `bindWorkspace` only.
- No project → banner, general chat only, production tools blocked (`PROJECT_REQUIRED` server-side).
- Last bound project is suggestion-only (`Resume Project`); never silent production permissions.
- `CoDirectorPage` calls `unbindWorkspace()` when `projectId` is absent.

### Persistence changes

- Conversations remain server-authoritative per `project_id`.
- Client message cache is project-scoped; legacy global key not used for hydrate.
- Selected model persists via `codirectorUpdateConfig`.
- localStorage/sessionStorage allowlist: no tokens, secrets, raw tool payloads, or full technical traces.

### Reconnect behavior

- Disconnect → Reconnecting with bounded backoff; **Reconnect** CTA after failures.
- Conversation + project binding preserved for the same project.
- Single-flight send (`sendInFlightRef`); cancel before project switch; cancel API idempotent.

### Removed fake or silent fallback paths

- Removed FE `planFromIntention` silent “drafted a plan” success when intelligence is off.
- Mock provider remains blocked outside `STUDIO_E2E`; stub_copy enhance still raises outside E2E.
- Failed chat/tool actions keep `partial_work_created: false`.

### Test results

See [`M41_TEST_REPORT.md`](./M41_TEST_REPORT.md) Wave 1 — API **16 passed**; Playwright **5 passed**.

### Remaining blockers (out of Wave 1)

- Wave 2+: sample/fake approval UI cleanup; tool registry gaps; specialist tool enablement; full M41-CD-15…40 and cert workflow.
- Approval Center / UnifiedExperience sample cards deferred to Wave 2.

---

**GO — M41 Wave 1 runtime and session foundation complete**

---

## Wave 2 — UI audit (pre-implementation)

| Field | Value |
|---|---|
| **Date** | 2026-07-28 |
| **Scope** | Wave 2 UI surfaces only (classification before polish) |
| **Method** | Code inspection of Co-Director shell, Project Content, nav, cards, cinematic CSS |

| Surface | Classification | Notes |
|---|---|---|
| Compact shell | Needs Polish / Misleading | Always mounts StageStrip + SpecialistStrip under chat; crowds narrow widths |
| Fullscreen layout | Needs Polish / Missing | CSS grid workspace — not shared `SplitPane`; no width persist; no layout presets |
| Header | Needs Polish | Runtime chip honest (Wave 1); project name not shown beside identity; no layout presets |
| Composer | Working / Needs Polish | Expanding input + Send/Stop present; no production toolbar — keep quiet |
| Nav drawer | Misleading | Storyboards→script, Props→characters, Exports→editor mis-aliases; dense route list |
| Options / overflow | Working | Status / reconnect / model persist from Wave 1 |
| Approvals tab | Fake or Sample Data | `ApprovalsList` POSTs hardcoded `story-1` / `media-1` seeds via `m214Approvals` |
| ApprovalCenterPanel | Fake or Sample Data | `"Mocked hitchhiker card"` seeds; unmounted from Shell but still in tree |
| Proposal cards | Working / Needs Polish | Real proposals in conversation; Approve not gated on `productionCapable` in card UI |
| Plan / task cards | Misleading | Light `.codirector-plan` / `.codirector-task` / `.codirector-cta-card` fills in `styles.css` |
| Empty states | Missing / Needs Polish | Approvals empty soft; no shared `CoDirectorEmptyState` / error card kit |
| Loading | Needs Polish | Hydrate/health mostly quiet; avoid indefinite loading when provider unavailable |
| Error / reconnect / no-project | Working | Wave 1 banners + structured send errors |
| Progressive disclosure | Missing | Inactive production chrome permanently reserved in compact |
| Narrow widths (360–640) | Needs Polish | Header wrap risk; strips steal composer space |
| Keyboard / focus | Working / Needs Polish | Drawer Escape/returnFocus exist; layout preset controls need labels |
| Contrast (Aurora) | Misleading | Light card CSS conflicts with cinematic shell |

**Deferred (out of Wave 2):** specialist tool execution, Director 2.0 timeline proposals, generation wiring, Editor place/subtitle tools, full cert (Waves 3–8).

---

## Wave 2 — Co-Director UI and approval honesty

| Field | Value |
|---|---|
| **Date** | 2026-07-28 |
| **Scope** | Wave 2 only (Waves 3–8 not started) |
| **Verdict** | **GO — M41 Wave 2 Co-Director UI and approval honesty complete** |

### Files changed

**Frontend**

- `studio-web/src/components/CoDirector/CoDirectorShell.tsx` — progressive disclosure compact; fullscreen `SplitPane` + layout presets
- `studio-web/src/components/CoDirector/layoutPresets.ts` — Chat Focus / Balanced / Project Focus
- `studio-web/src/components/CoDirector/CoDirectorHeader.tsx` — project label + preset controls
- `studio-web/src/components/CoDirector/navEntries.ts` + `CoDirectorNavDrawer.tsx` — honest nav; Jobs deferred; removed mis-aliases
- `studio-web/src/components/CoDirector/CoDirectorProjectContent.tsx` — real `listProposals`; honest empty Approvals/Plans
- `studio-web/src/components/CoDirector/CoDirectorProposalCard.tsx` — meta fields; Approve gated on `productionCapable`
- `studio-web/src/components/CoDirector/ApprovalCenterPanel.tsx` — no hitchhiker/sample seeds
- `studio-web/src/components/CoDirector/cards/*` — empty/error/content card primitives
- `studio-web/src/components/CoDirector/codirector-cinematic.css` — SplitPane host; Aurora card overrides; compact polish
- `studio-web/src/components/ui/SplitPane.tsx` — preset size requests + keyboard resize
- `studio-web/src/components/CoDirector/types.ts` + `CoDirectorSession.tsx` — project-scoped composer drafts

**Tests / docs**

- `tests/e2e/m41/m41-cd-wave2.spec.ts`
- `studio-web/src/components/CoDirector/layoutPresets.test.ts`
- `studio-web/src/components/CoDirector/CoDirectorNavDrawer.test.ts`
- `docs/release-gate/m41/M41_TEST_REPORT.md` (Wave 2)
- `docs/release-gate/m41/M41_WAVE2_REPORT.md`
- Screenshots under `artifacts/m41/wave2/`

### Progressive disclosure

Default chrome: conversation, runtime status, current project, composer. Compact no longer mounts StageStrip / SpecialistStrip. Fullscreen StageStrip only when an active plan stage exists; SpecialistStrip only when a character is selected. Approvals/plans/jobs panels stay quiet when empty.

### Layout presets

Chat Focus 70/30, Balanced 50/50, Project Focus 30/70 via `adept_codirector_split_preset` + size key `adept_codirector_split_primary`. Manual drag still persists.

### Approval honesty

Removed hardcoded `story-1` / `media-1` / hitchhiker seeds. Approvals load `listProposals` or show:

```text
No approvals are waiting.
Co-Director will place proposed production changes here before applying them.
```

### Wave 1 safeguards preserved

Runtime chip, no-project banner, project binding, reconnect, structured errors. Draft persistence is now project-scoped (`adept_codirector_draft_<projectId>`).

### Test results

See [`M41_TEST_REPORT.md`](./M41_TEST_REPORT.md) Wave 2 — Playwright **11 passed**; unit **5 passed**; Wave 1 regression API **16** + Playwright **5**.

### Remaining blockers (out of Wave 2)

- Waves 3+: tool registry, specialist execution, Director 2.0 handoff, generation wiring, full cert M41-CD-35…40.

---

**GO — M41 Wave 2 Co-Director UI and approval honesty complete**

---

## Wave 3 — Read Capability Audit (pre-implementation)

| Field | Value |
|---|---|
| **Date** | 2026-07-28 |
| **Scope** | Co-Director production read tools and live domain sources |
| **Note** | `studio-api/app/repositories/` is inert — live reads use domain services/stores |

| Capability | Current repository/source | Existing tool | Project-scoped | Typed response | Pagination | Filtering | Failure honesty | Wave 3 action |
|---|---|---|---|---|---|---|---|---|
| Project summary | `project_service.project_status/profile` | `get_project_status`, `get_project_profile` | Yes | Partial | No | No | Partial | Normalize → `project.get_summary` + envelope |
| Project blockers | session_context `unresolvedBlockers` | None as tool | Yes | Thin | No | No | Partial | Add `project.list_blockers` |
| Scripts | `script_storyboard` + extra routes | None | Yes | HTTP only | No | No | Partial | Add `script.list/get/search` |
| Scenes | `scene_service` / SceneService | `list_scenes`, `get_scene`, `get_active_scene` | Yes | Yes | limit only | Weak | Partial | Alias + search/relationship tools |
| Characters (Identity) | `character_identity/service` | `list_character_profiles`, `inspect_*` | Yes | Yes | Weak | Weak | Partial | Alias → `character.*`; no fabrication |
| Characters (Bible) | bible domain_service | `list_bible_entities`, `get_bible_entity`, `get_character_bible_context` | Yes | Yes | limit | entityType | Partial | Keep under `production_bible.*` |
| Production Bible | bible service/ops/context | Multiple bible reads | Yes | Yes | Partial | Partial | Partial | Envelope + `canonical_status` |
| Assets / library | `project_library` | `search_library_assets`, folder map/summary | Yes | Yes | limit | Partial | Partial | Alias → `asset.*` |
| Plans (intelligence) | intelligence store | Via chat plan state, not registry | Yes | JSON row | No | No | Partial | Add `production_plan.list/get` |
| Plans (m214) | m214 plan_view | HTTP `m214Plan` | Yes | Scaffolded | No | No | Honesty flag | Read with scaffold warning only |
| Proposals | `ProposalService` | HTTP list/get; not read tool | Yes | Yes | **Unbounded** | status | Good | Add `proposal.list/get` |
| Jobs (executive) | executive JobStore | HTTP; not read tool | Yes | Yes | Partial | Partial | Partial | Add `job.list/get` |
| Jobs (render) | `Job` ORM /api/projects/.../jobs | HTTP | Yes | Yes | Partial | No | Partial | Secondary `source: render` |
| Continuity (Bible) | bible conflicts | `list_continuity_warnings` | Yes | Yes | No | No | Partial | Fold into `continuity.*` with source |
| Continuity (vision) | VisionStore | `vision_validation_*` | Yes | Yes | limit | Partial | Partial | Fold into `continuity.*` |
| Continuity (heuristic) | learning continuity_suggestions | HTTP only | Yes | Heuristic | No | No | Soft | Label non-canonical / Deferred |
| Workspace context | `session_context.build_session_context` | HTTP GET; not tool | Optional | Thin | N/A | N/A | Partial | Add `workspace.get_active_context` |
| System capabilities | CapabilityAdapter + health tools | Scattered health tools | Mixed | Partial | N/A | N/A | Partial | Add `system.list_capabilities` |
| Retrieval envelope | None | Raw handler dicts | — | — | — | — | Missing | Add wrap at `execute_read` |
| Mutation tools | Closed registry | 37 mutating | Yes | Propose-only | — | — | Working | Keep out of Wave 3 read route |
| Demo/stub paths | Bible seed-demo, m214 hitchhiker, vision mock, mock provider | Various | — | — | — | — | Placeholder | Must not present as Beta truth |

**Stub/demo callouts:** Bible `seed-demo`, m214 `honesty: "scaffolded"` / hitchhiker media, vision mock fixtures, executive mock imagegen, Co-Director mock provider (E2E only).

**Duplicate surfaces:** Identity vs Bible characters; executive vs render jobs; intelligence vs m214 plans; three continuity sources — Wave 3 labels and separates; does not merge silently.

---

## Wave 3 — Canonical production retrieval

| Field | Value |
|---|---|
| **Date** | 2026-07-28 |
| **Scope** | Wave 3 only (Waves 4+ not started) |
| **Verdict** | **GO — M41 Wave 3 canonical production retrieval complete** |

### What shipped

- Canonical retrieval envelopes at `execute_read` (`read_envelope.py`) with evidence, warnings, pagination, status honesty.
- Dotted aliases + gap read tools (scripts, blockers, proposals, jobs, plans, continuity, workspace, capabilities).
- Project isolation + path scrubbing + requestId read dedupe + short TTL cache (jobs/proposals fresh).
- Project Content retrieval cards sharing ProposalService with Approvals.
- M41-CD-35…54 API + Playwright coverage; Wave 1/2 regression green.

### Primary paths

- Backend: `studio-api/app/codirector/tools/{read_envelope,read_cache,aliases,handlers/wave3_reads,execution,registry,definitions}.py`
- Frontend: `studio-web/src/components/CoDirector/retrieval/*`, `CoDirectorProjectContent.tsx`
- Report: [`M41_WAVE3_REPORT.md`](./M41_WAVE3_REPORT.md)

### Deferred (out of Wave 3)

Mutations, generation, Editor place, job retry/cancel, specialist execution, Wave 4+ plan operator.

---

**GO — M41 Wave 3 canonical production retrieval complete**

---

## Wave 4 — Durable Plan System Audit (pre-implementation)

| Field | Value |
|---|---|
| **Date** | 2026-07-28 |
| **Scope** | Co-Director production plan stores and surfaces |
| **Note** | Implementation must not begin without this canonical decision |

| System | Source/store | Durable | Project-scoped | Versioned | Step states | Dependencies | Blockers | Approvals | Recovery | Event history | Truth status | Wave 4 action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Intelligence production plan | `CoDirectorProductionPlan` + `IntelligenceStore` | Yes | Yes | No | In JSON (thin) | Weak | Strings | Via ProposalService | Read-only | Via synthesis link | **Canonical Candidate** | **Extend as sole writable store** |
| Wave 3 `production_plan.*` | Tool handlers over intelligence rows + m214 overlay | Reader | Yes | No | Returns stored | Returns stored | Returns stored | No | No | Evidence only | Reusable | Rebind to PlanService |
| m214 plan view | `m214/plan_view.py` + `m214_project_stages` | Partial | Yes | No | Heuristic stages | No | No | No | Stage pointer | Capability log | **Scaffolded** | Read-only projection; never authoritative |
| Frontend ActionPlan / runSteps | `CoDirectorSession` + `codirector/types.ts` | No | Session | No | Local | No | No | Local | Dismiss | Local audit | **Frontend Only / Legacy** | Keep cleared on intelligence path |
| SSE `productionAnalysis.planSteps` | Chat stream mirror | No | Session | No | Transient | No | No | No | Remount loses | No | **Session Only** | Non-authoritative mirror |
| ProposalService | `codirector_proposals` | Yes | Yes | Bible pins | N/A | Staleness | Stale flag | Yes | Receipts | Approvals | **Reusable** | Authoritative plan transitions via propose→approve |
| M213 SceneProductionPlan | `m213_*` tables | Yes | Yes | Snapshots | A–Z | Yes | Yes | Gates | advance API | Logs | Domain-specific | Deferred — out of Wave 4 truth path |
| M29 control plans | `m29_control_plans` | Yes | Yes | No | Job steps | Via jobs | No | Yes | Job queue | Job events | Fixture planner | Deferred — do not merge |
| ProductionJob / JobStore | executive tables | Yes | Yes | No | Job status | Yes | blocked_reason | Via proposals | Retry | Full audit | Job runtime | Deferred — not plan document store |

```text
Canonical production plan source:
studio-api/app/codirector/plans/ (CoDirectorProductionPlan + versions/events)

Legacy plan surfaces:
m214 plan_view; frontend ActionPlan; SSE productionAnalysis.planSteps; M213/M29 (out of Wave 4 truth path)

Compatibility behavior:
Wave 3 production_plan.* reads continue; m214 listed only as scaffolded; IntelligenceStore.save_plan routes through PlanService.create_draft adapter
```

---

## Wave 4 — Implementation summary

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Domain** | `studio-api/app/codirector/plans/` |
| **Migration** | M022 durable plan versions/events/idempotency |
| **Draft boundary** | `production_plan.create_draft` audited via `/tools/audited` + `execute_audited` (no plan-acceptance gate; always `draft`/unapproved) |
| **Authoritative mutations** | propose → human approve → `execute_approved_proposal` → PlanCommandService |
| **Atomic commit** | head + version snapshot + event + idempotency (single transaction) |
| **Readiness** | `get_readiness` returns `snapshotReadiness` + `currentReadiness` + `changedCapabilities` |
| **Session** | `activePlanId/Version/State`, `planReadiness`, `openPlanBlockers` |
| **FE** | `studio-web/src/components/CoDirector/plans/*` in Plans tab |
| **Detail** | [`M41_WAVE4_REPORT.md`](./M41_WAVE4_REPORT.md) |

**Idempotency retention:** `codirector_plan_command_idempotency` retains results ≥7 days (manual/ops purge; no auto-job in Wave 4).

**GO — M41 Wave 4 durable production planning complete**

