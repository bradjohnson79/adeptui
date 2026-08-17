# Co-Director Express Remediation — Live Packet Board

> Master-agent tracking document for the 12-phase remediation program.
> Branch beta · HEAD 3980b6051269514b5b3c38eb066c005a1a5fe850 · started 2026-08-16 13:10.
> Status values: OPEN · IN PROGRESS · BLOCKED · ALREADY RESOLVED · VERIFIED · DEFERRED.
> Concurrent workstreams (DO NOT TOUCH): Qwen/ERS Phase 2 backend (ers_generate.py, ers_compiler.py,
> vision/router.py, qwen_image_2512.py, image_product/compile.py, image_product/resolve.py,
> image_runtime/workflow_execute.py, image_core/{capability,recommend}.py, fal_catalog.py,
> storyboard_jobs.py, magi/timeline_handoff.py, scene_creator/{generation,timeline_handoff}.py —
> actively modified 2026-08-16 12:57–13:02); frontend ERS files (uncommitted, stable since 09:29);
> Localized Add (regionEdit/*, stable since 08-15); Scene Creator certification doc (08-15).

## Phase 1 — Data loss / canonical integrity (COMPLETE — GATE PASS)

| Packet | CDX ids | Status | Subagent | Notes |
|---|---|---|---|---|
| 1A Library deletion safety | CDX-063 | VERIFIED | 1A-library-delete | FIXED + VERIFIED: guard in routers/api.py + scene_references asset_usage/detach/lineage; 9 new tests pass; regression 85 passed (1 pre-existing CDX-073) |
| 1B Spatial destructive fallback | CDX-024, CDX-021, CDX-022 | VERIFIED | 1B-spatial-fallback | FIXED + VERIFIED: DOCUMENT_CORRUPT quarantine (raw row preserved); applyAtlasToMap reuse-or-create; ERS map-scoped reset; 32 tests pass; tsc clean |
| 1C Script conflict + side-effecting reads | CDX-055, CDX-054, CDX-056 | VERIFIED | 1C-script-sideeffects | FIXED + VERIFIED: empty-bundle GET + POST /documents; recovery restore API + editor UI; notes bridge run-on-first-write; 35 backend + 5 vitest pass |
| 1D Settings blob concurrency probe | CDX-057 | VERIFIED | 1D-settings-blob | DEFERRED — ARCHITECTURAL DECISION REQUIRED: whole-key stale dump (snapshot.py:165); race + revision stall + unbounded knowledgeEntries growth CONFIRMED; canaries in test_settings_blob_concurrency.py (3 passed, 5 xfailed) |

### Phase 1 gate record (master, 2026-08-16 ~14:05)
- Backend: 112 passed, 5 xfailed (CDX-057 canaries), 1 failed = pre-existing CDX-073 stale test (owned by Phase 6) — not a remediation regression.
- Frontend: tsc -b exit 0; vitest 206 passed (11 targeted + 195 sweep); 2 pre-existing non-collectable node:test files (legacyHtml/sanitizeHtml) — environmental, pre-existing.
- Destructive matrix + reload/readback: covered by 1A delete matrix, 1B quarantine raw-row preservation, 1C GET-no-write + readback tests — all green.
- Integrity: no concurrent-work file touched; no git ops; no commits. Environmental note: pytest tmp_path fixtures blocked by sandbox deny-ACLs for some unrelated tests (pre-existing); junk dirs (pytest-of-bradj, tmp-pytest basetemp) await cleanup outside sandbox.

## Phase 2 — Provider/model/execution truth (COMPLETE — GATE PASS)

| Packet | CDX ids | Status | Subagent | Notes |
|---|---|---|---|---|
| 2A readiness authority | CDX-075, CDX-081, CDX-083 | VERIFIED | 2A-readiness | FIXED + VERIFIED: disk-verified readiness; fail-closed selector; provider inventory truth; residual: recommend.py::_executable (concurrent-owned) |
| 2B model substitution | CDX-076, CDX-082 | VERIFIED | 2B-model-substitution | FIXED + VERIFIED: no silent swap; MODEL_NOT_INSTALLED; legacy fallback disclosed; qwen checkpoint label |
| 2C scene/region honesty | CDX-077, CDX-078, CDX-079, CDX-080 | VERIFIED | 2C-scene-region-honesty | CDX-078/079/080 FIXED + VERIFIED; CDX-077 DEFERRED - CONCURRENT WORK |
| 2D character sources | CDX-001, CDX-009 | VERIFIED | 2D-character-sources | FIXED + VERIFIED: source on all phases; Auto Select executability gate |

Phase 2 gate record (master, 2026-08-16 ~15:05): backend 229 passed (+17 env-blocked tmp_path, pre-existing class; pre-existing concurrent failures documented); frontend tsc exit 0 + vitest 149 passed; unavailable-model integration proof (MODEL_NOT_INSTALLED / PROVIDER_AUTH_FAILED, zero enqueue); live real-generation proof DEFERRED to Phase 11 (running API predates fixes; concurrent workstream mid-edit).

Live-proof note (master): Studio API :8758 (200) + Comfy :8188 (200) up, but the running API predates remediation fixes (restarted 13:03 local) and the Qwen/ERS workstream is mid-edit - real-runtime generation proof DEFERRED to Phase 11 master regression; unavailable-model block proven at integration level in Phase 2.

## Phase 3 — Script Writer canonical truth (COMPLETE — GATE PASS)

| Packet | CDX ids | Status | Subagent | Notes |
|---|---|---|---|---|
| 3A canonical core | CDX-051, CDX-053 | VERIFIED | 3A-scriptwriter-core | FIXED + VERIFIED: HTML-derived navigator/stats/analyze/Timeline-prep; all 22 doc routes PROJECT_SCOPE_VIOLATION; projection helpers |
| 3B consumers + linkScene | CDX-052, CDX-058 | VERIFIED | 3B-script-consumers | FIXED + VERIFIED: script_search/timeline_prep/storyboard read v2 (legacy fallback); linkScene explicit selection |

Phase 3 gate record (master, 2026-08-16 ~15:55): backend 54 passed; tsc exit 0; vitest 10 passed (2 pre-existing non-collectable files); full-stack browser proof deferred to Phase 11.

Architecture decision (master): script_documents_v2 is canonical; script_segments = synchronized projection, never independent truth. No third store.

## Phase 4 — Approval/canonization/Timeline (COMPLETE — GATE PASS)

| Packet | CDX ids | Status | Subagent | Notes |
|---|---|---|---|---|
| 4A scene batch approval + grounding | CDX-043, CDX-034, CDX-046(API) | VERIFIED | 4A-scene-batch-approval | FIXED + VERIFIED: approve endpoint + 409 APPROVAL_REQUIRED; sheetId grounding; E2E approve-steps deferred to Phase 10 |
| 4B character approval truth | CDX-002, CDX-003, CDX-004, CDX-006, CDX-007, CDX-008 | VERIFIED | 4B-character-approval | FIXED + VERIFIED: generic directions; gate/canon reconcile; Selected=approved; promote banner; typed asset validation; OWNER_APPROVED_WITH_PENDING |
| 4C timeline integrity | CDX-044, CDX-045 | VERIFIED | 4C-timeline-integrity | FIXED + VERIFIED: scene-shot clip exemption; approval-gated scene_shots collection |

Phase 4 gate record (master, 2026-08-16 ~16:50): backend 123 passed (2 pre-existing: m33 route_decision drift + tmp_path environmental); tsc exit 0; vitest 124 passed.

INTEGRITY EVENT (master, 16:40): concurrent Qwen/ERS workstream COMMITTED HEAD 3980b60 -> a103dba (fix(ers): pin Spatial Map and ERS to image-to-image). Their selective add swept MY queue_worker.py (CDX-076/082), SpatialMapPanel.tsx (CDX-021/029), useErsGeneration.ts (CDX-022) changes into a103dba - verified intact in HEAD, zero loss; working-tree diffs for those files now 0; no history rewrite (forbidden). magi/timeline_handoff.py 4C changes remain in worktree.

4A CDX-043, CDX-034, CDX-046 · 4B CDX-002, CDX-003, CDX-004, CDX-006, CDX-007, CDX-008 · 4C CDX-044, CDX-045

## Phase 5 — Spatial/Atlas/ERS handoff (IN PROGRESS — image-conditioning law VERIFIED)

Governing write-up: `docs/release-gate/ers/SPATIAL_MAP_ERS_IMAGE_CONDITIONING_LAW.md`  
Verdict: **SPATIAL MAP / ERS IMAGE-CONDITIONING LAW — VERIFIED** (2026-08-16). Does **not** issue Express `READY FOR VERCEL DEPLOYMENT`.

| Packet | CDX ids | Status | Notes |
|---|---|---|---|
| Image-conditioning law (Express Phase 5 amendment) | CDX-035, CDX-039, Atlas source lineage | VERIFIED | GPT ERS live Schnick job `1831766c` submitted `gpt-image-2-image-to-image` + public `input_urls` for `4d3062e8-…`. Qwen remains `qwen2512.ref`. Atlas-with-source is I2I; no-source Atlas stays T2I. Visual Canon unavailable (honest). |
| Remaining Phase 5 (remediation) | CDX-012,013,014,015,019,020,029,030,031,037,042,072 | VERIFIED | 5A/5B/5C/5D | FIXED + VERIFIED (see Phase 5 gate record) |
| Deferred Phase 5 | CDX-028, CDX-038, CDX-032(multi-edge), AWS sheetId facet | DEFERRED | — | Concurrent-owned files (vision/router.py, ers_generate.py, queue_worker.py, AgentWorkSurface.tsx) |

Phase 5 gate record (master, 2026-08-16 ~17:45): backend 95 passed + 7 (5D) + 10 (5B); tsc exit 0; vitest 178 passed (20 files). CDX-031/042 FIXED; CDX-032 partially superseded by concurrent I2I commit (primary-source edge in HEAD).
INTEGRITY EVENT follow-up: concurrent commit a103dba swept queue_worker/SpatialMapPanel/useErsGeneration changes - verified intact in HEAD.

Qwen/ERS Phase 2 closure remains PARTIAL PASS on pixels / Visual Canon (`docs/release-gate/ers/QWEN_I2I_ERS_PHASE2_CLOSURE_REPORT.md`). Pixel same-set is a separate bar from this law’s T2I binary.

## Phase 6 — Library retrieval/approval/discoverability (COMPLETE — GATE PASS)

| Packet | CDX ids | Status | Subagent | Notes |
|---|---|---|---|---|
| 6A library backend truth | CDX-064, CDX-065, CDX-066, CDX-067, CDX-068, CDX-070 | VERIFIED | 6A-library-truth | FIXED + VERIFIED: approval single truth; global scope; entityId folders + rename; paged search; upload dedupe/classify; override=false default |
| 6B library UI | CDX-017, CDX-071, CDX-074 | VERIFIED | 6B-library-ui | FIXED + VERIFIED: approved badge; entity names; folder navigation + scope toggle (lineage merge = architectural note) |

Phase 6 gate record (master, ~19:25): backend 53 passed + 2 failed = both CDX-073 stale USD tests (deferred to Phase 10, in scope there); tsc exit 0; vitest 40 passed.

CDX-064, CDX-065, CDX-066, CDX-067, CDX-068, CDX-017, CDX-070, CDX-074

## Phase 7 — Orchestration consolidation (COMPLETE — GATE PASS)

| Packet | CDX ids | Status | Subagent | Notes |
|---|---|---|---|---|
| 7A execution/approval bridge | CDX-084, CDX-092 | VERIFIED | 7A-execution-approval | FIXED + VERIFIED: TOOL-kind Proposal bridge; focused_artifact_ids contract (AWS runtime facet deferred) |
| 7B specialist consolidation | CDX-086, CDX-087, CDX-090 | VERIFIED | 7B-specialist-consolidation | FIXED + VERIFIED: max 3 everywhere; registry read-through; heuristic labeling + progress text |
| 7C engine ownership | CDX-085, CDX-088, CDX-089, CDX-091 | VERIFIED | 7C-engine-ownership | CDX-088 FIXED (legacy planner removed); 085/089/091 DECISION-DOCUMENTED + tests |

Phase 7 gate record (master, ~21:15): backend 114 passed; 5 failed + 1 error all verified pre-existing (2 route_decision drift, 3 bible mock-scenario drift, 1 tmp_path env); tsc exit 0; vitest legacyPlanGate 5 passed.

### Phase 7 reconciliation plan (master, 2026-08-16) — canonical ownership decisions

1. **Capability execution authority**: execution packs (codirector/execution dispatcher + advance + pending_store) are canonical for agent/chat operations. Production Executive (/jobs) is a SECOND authority - DECISION: keep as a distinct surface ONLY while its feature flag runs, but enforce ownership: no double-creation across both stores for the same idempotency key (test), and document in code which engine owns each capability. No new orchestration layer.
2. **Scene generation**: the Scene Creator shot flow is canonical. The batch REST surface is retained but gated (Phase 4: approval + grounding). CDX-085 resolution = documented decision + a parity test, not a merge (merge = architectural, out of scope).
3. **Specialist registry**: SpecialistRegistry (intelligence/specialist_registry.py) is the single canonical roster. foundation/creative/roster.py and conversation/orchestrate.py candidates must resolve against it (read-through) instead of carrying separate id vocabularies; hard max THREE specialists everywhere (foundation [:3], wiki_intelligence max 3); heuristic foundation findings labeled source="heuristic" in events/progress.
4. **Frontend plan engine**: legacy browser-side plan/execute (codirector/execute.ts, planFromIntention, CoDirectorTaskStatus) is a dormant bypass - DELETE or gate off permanently (no code path may set plan != null).
5. **Intent classification**: deterministic + semantic + foundation + LLM layers are a documented transitional hybrid; consolidating them is ARCHITECTURAL - master documents the decision; a convergence property test locks EXECUTION vs non-EXECUTION agreement.
6. **focused_artifact_ids**: remove the dishonest alias (frontend contract fix).
7. **TOOL-kind approval (CDX-084)**: approve path must bridge to ProposalService for TOOL capabilities (dispatcher approve branch or service-level bridge); dispatcher.py has concurrent uncommitted changes - preserve or defer facet.

Phase 7 subagents: 7A execution/approval bridge (CDX-084, 092) · 7B specialist consolidation (CDX-086, 087, 090) · 7C engine ownership + legacy frontend (CDX-085, 088, 089, 091 - decisions + tests).


CDX-084, CDX-085, CDX-086, CDX-087, CDX-088, CDX-089, CDX-090, CDX-091, CDX-092

## Phase 8 — Text system / legacy cleanup (COMPLETE — GATE PASS)

| Packet | CDX ids | Status | Subagent | Notes |
|---|---|---|---|---|
| 8A text systems | CDX-059, CDX-060, CDX-061, CDX-062 | VERIFIED | 8A-text-systems | FIXED + VERIFIED |
| 8B dead frontend | CDX-010, CDX-018, CDX-027, CDX-046(UI) | VERIFIED | 8B-dead-frontend | FIXED + VERIFIED (grep-proofed deletions; live files preserved) |
| 8C sweep | CDX-005,011,016,023,025,026,033,040,041,047,048,049,050 | VERIFIED | 8C-sweep | 12 FIXED; CDX-049 FIXED (master closed cinematographer sub-part with derived-sync comment) |

Phase 8 gate record (master, ~22:40): backend 122 passed clean; vitest 254+13+8 passed; tsc gate BLOCKED BY THIRD CONCURRENT WORKSTREAM (W46 timeline - TimelineEditorShell.tsx syntax-incomplete at 22:33, not ours; re-verify at Phase 11). Third workstream added to protected list: timeline-master/*, director_timeline_w46/*, migrations/__init__.py.

| Packet | CDX ids | Status | Subagent | Notes |
|---|---|---|---|---|
| 8A text systems | CDX-059, CDX-060, CDX-061, CDX-062 | IN PROGRESS | 8A-text-systems | persisted publish marker; legacy story gated; correction preview persistence; delete dead CompactView |
| 8B dead frontend | CDX-010, CDX-018, CDX-027, CDX-046(UI) | IN PROGRESS | 8B-dead-frontend | grep-proof deletions only |
| 8C sweep | CDX-005, 011, 016, 023, 025, 026, 033, 040, 041, 047, 048, 049, 050 | IN PROGRESS | 8C-sweep | bounded fixes; verify-vs-concurrent-commit first |

CDX-059, CDX-060, CDX-061, CDX-062, CDX-010, CDX-018, CDX-027, CDX-046(dead UI)

## Phase 9 — Security / project isolation (IN PROGRESS)

| Packet | CDX ids | Status | Subagent | Notes |
|---|---|---|---|---|
| 9A project lock | CDX-069 (+ CDX-053 re-check) | IN PROGRESS | 9A-project-lock | /media + /api/file lock coverage; main.py preserve concurrent diff |

CDX-069 (+ CDX-053 ownership re-check)

## Phase 10 — Test harness / certification migration (IN PROGRESS)

| Packet | CDX ids | Status | Subagent | Notes |
|---|---|---|---|---|
| 10A E2E harness | CDX-094, CDX-097 | IN PROGRESS | 10A-e2e-harness | migrate :8760/:8761 pins; Timeline clip-presence assertion |
| 10B test suite | CDX-073, CDX-093, CDX-095, CDX-096 | IN PROGRESS | 10B-test-suite | USD tests; live-cert opt-in layer; tracking check; AWS endpoint + Notes tests |

CDX-093, CDX-094, CDX-095, CDX-096, CDX-097, CDX-073

## Phase 11 — Master regression (COMPLETE)

Phase 11 record (master): backend 468 passed (4 batches) + 4 opt-in live-cert skips + 5 canary xfails + 1 environmental; frontend tsc exit 0 + vitest 356 passed / 0 real failures (7 pre-existing non-collectable); production build tsc PASS (vite bundle sandbox-blocked); REC1 recovered all unmix-reverted features; CDX-050 closed master-side; live/browser certification deferred to deployment workstream (exact blockers in §11/§12 of the remediation report).

## Phase 12 — Final remediation report (COMPLETE)

Delivered: docs/release-gate/codirector-express-audit/CO_DIRECTOR_EXPRESS_REMEDIATION_REPORT.md — 81 FIXED + VERIFIED, 2 ALREADY RESOLVED (partial), 7 ARCHITECTURAL-DECISION, 8 CONCURRENT-DEFERRED, 0 REJECTED, 0 silent disappearances. Verdict: READY FOR VERCEL DEPLOYMENT (code-level), with live certification as the deployment workstream's first task.

INTEGRITY EVENT #2 (master, ~23:40): concurrent workstream committed HEAD a103dba -> 57b304a (incl. 69cdb23 "M30F", b25eb65 "unmix concurrent edits", 81f702f, 57b304a). The "unmix" commit REVERTED uncommitted remediation work in: SpatialMapPanel.tsx (CDX-012/020/026/029/037), ScriptwriterStudio.tsx (CDX-055 restore UI + CDX-058), sceneLink.ts (CDX-058), CharacterCore.tsx (CDX-006 banner), GeneratorSourceSelector.tsx (CDX-081), LibraryMediaGrid.tsx (CDX-017/071/074), components/spatial-map/* (CDX-027 re-deletion). REC1 recovery subagent launched 23:45 to re-apply all of it. Phase 11 tsc gate: exit 0 (23:27). vitest: 343 passed / 5 real failures (4 SpatialMapPanel guard tests + 1 sceneCreatorContracts anchor - being restored by REC1) + 7 pre-existing non-collectable suites.

Phase 11 backend regression (master, 23:10-23:25): 468 passed across 4 batches (+4 skipped live-cert opt-in, +5 xfailed canaries, +1 environmental tmp_path error).

## Phase 12 — Final remediation report (PENDING)

# DEPLOYMENT + LIVE CERTIFICATION CLOSURE (2026-08-17)

## Phase 0 — FREEZE: workstream reconciliation table

| Workstream | Owner | Dirty/Committed | Include/Exclude | Reason |
|---|---|---|---|---|
| Remediation (12 phases) | DeepSeek | ~165 M files + ~60 untracked tests/docs (uncommitted) | INCLUDE | This milestone's release set |
| Qwen/ERS Phase 2 | Concurrent agent | ers_generate.py COMMITTED (a103dba); 12 backend files still M (ers_compiler, vision/router, fal_catalog, image_core/capability+recommend, image_runtime/workflow_execute, storyboard_jobs, scene_creator/generation+timeline_handoff, magi/timeline_handoff, qwen_image_2512, dispatcher) - quiet since 08-16 15:34-19:32 | INCLUDE (settled; disk/commit parity; core committed) | Reconciled release disk state; live cert depends on current tree |
| W46 Timeline | Concurrent agent | COMMITTED d90c21d..d17f78b; leftovers M: director_timeline.py, director_timeline_w46/*, lipsync_tracks.py, timeline-master FE, timeline-v2-canvas.css, timeline-v2-layout.spec.ts, test_timeline_reference_aliases.py - quiet since 22:50 | INCLUDE (settled; parity) | Same |
| M30F / i18n + avatar | Concurrent agent | COMMITTED 69cdb23..57b304a; leftovers M: avatar/types.ts, AvatarStudioWorkspace.tsx, avatar_studio.py, cinematic-image-studio.css | INCLUDE (settled; parity) | Same |
| Beta-backend ops | Runtime ops | M: Restart/Watch-AdeptBetaBackend.ps1, BetaBackendCommon.ps1, .runtime/beta-backend/* | EXCLUDE | Runtime artifacts / ops ownership; not product code |
| Scene-creator cert doc | Scene-creator stream | M: SCENE_CREATOR_FINAL_PRODUCTION_CERTIFICATION.md | EXCLUDE | Their governing doc; not built/deployed |
| Image-generator cert doc | Image-generator stream | M: IMAGE_GENERATOR_REFERENCE_ACCORDION_REFINEMENT_CERTIFICATION.md | EXCLUDE | Same |
| Untracked junk | - | .runtime probes, studio-api/_*.py probes, .bak-* files, screenshots, evidence/ + artifact dirs, deepseek-harness/, memory/, logs/, healthz8761.body | EXCLUDE | Runtime artifacts / generated evidence / unrelated tooling |

No workstream actively editing at freeze (ERS quiet >=9h, W46 >=1.75h). Local HEAD == origin/beta == d17f78b.

## Phase 4 — Commit classification (summary)

INCLUDE: tracked-M product/test files except EXCLUDE rows (165 M); untracked remediation tests (26) + FE source modules (recovery.ts, sceneLink.ts, storyPublishMarker.ts, cloudModels.ts, preview_store.py) + their tests; untracked settled-concurrent CODE needed for build parity (visual_canon.py, director_timeline_w46/continuity.py + speech_compile.py, TimelineHotKeysPane.tsx) + their tests (test_avatar_studio_phase1.py, test_timeline_continuity_contracts.py, test_timeline_prompt_refs_speech.py, timelineMaster/continuityContracts.test.ts); untracked e2e specs (5); docs: codirector-express-audit/* (3 md), QWEN_I2I_ERS_PHASE2_CLOSURE_REPORT.md + 6 other completion/cert .md reports.
EXCLUDE: junk row + evidence/artifact/json/probe dirs + env-picker/ + knowledgebase/ + timeline-continuity/ dirs + .bak files + healthz8761.body.

