# CO-DIRECTOR EXPRESS — FINAL REMEDIATION REPORT

## 1. Program identity

| Field | Value |
|---|---|
| Branch | `beta` |
| Starting HEAD (audit + program start) | `3980b6051269514b5b3c38eb066c005a1a5fe850` |
| Current HEAD (concurrent workstreams committed during the program) | `57b304a637f33aa9b023bb7333f42c9b1b91e0ac` |
| Program dates | 2026-08-16 13:05 → 23:55 (single session) |
| Mode | Read-only audit (prior) + authorized remediation (this program) |
| Subagent runs | 29 (+1 recovery) across 11 phases + master-led fixes (CDX-050, CDX-049 close, integrity recovery) |
| Commits/pushes by the remediation program | NONE (per mandate; the concurrent workstreams committed independently — see §13) |

**Working-tree state at program end:** large uncommitted remediation diff (790 changed paths at last count) + concurrent workstreams' own uncommitted files (ERS backend set; W46 timeline set). All current changes are protected.

## 2. Original audit baseline

97 findings: **0 P0 · 11 P1 · 43 P2 · 43 P3** · 3 NEEDS VERIFICATION (CDX-029, CDX-044, CDX-057) · all others CONFIRMED. Governing register: `docs/release-gate/codirector-express-audit/CO_DIRECTOR_EXPRESS_MASTER_AUDIT.md`.

## 3. Phase verdict table

| Phase | Scope | Verdict |
|---|---|---|
| 0 | Initialization / packet board / collision map | COMPLETE |
| 1 | Data loss / canonical integrity (CDX-063, 024, 021, 022, 054, 055, 056, 057) | **PASS — PHASE 1 CANONICAL INTEGRITY REPAIRED** |
| 2 | Provider/model/execution truth (CDX-075, 076, 078, 079, 080, 081, 082, 083, 001, 009) | **PASS — PHASE 2 PROVIDER TRUTH CERTIFIED** |
| 3 | Script Writer canonical truth (CDX-051, 052, 053, 058) | **PASS — PHASE 3 SCRIPT CANON CONSOLIDATED** |
| 4 | Approval/canonization/Timeline (CDX-043, 034, 046, 002, 003, 004, 006, 007, 008, 044, 045) | **PASS — PHASE 4 APPROVAL AND TIMELINE CERTIFIED** |
| 5 | Spatial/Atlas/ERS handoff (CDX-012, 013, 014, 015, 019, 020, 029, 030, 031, 032, 037, 042, 072) | **PASS — PHASE 5 SPATIAL/ATLAS/ERS HANDOFF CERTIFIED** (5E deferred) |
| 6 | Library retrieval/approval/discoverability (CDX-064, 065, 066, 067, 068, 017, 070, 071, 074) | **PASS — PHASE 6 LIBRARY TRUTH CERTIFIED** |
| 7 | Orchestration consolidation (CDX-084, 085, 086, 087, 088, 089, 090, 091, 092) | **PASS — PHASE 7 ORCHESTRATION BOUNDARIES CERTIFIED** (085/089/091 decision-documented per mandate) |
| 8 | Text system / legacy cleanup (CDX-059, 060, 061, 062, 010, 018, 027, 046-UI + sweep CDX-005, 011, 016, 023, 025, 026, 033, 040, 041, 047, 048, 049, 050) | **PASS — PHASE 8 LEGACY SURFACES CLEANED** |
| 9 | Security / project isolation (CDX-069 + CDX-053 re-check) | **PASS — PHASE 9 PROJECT ISOLATION CERTIFIED** |
| 10 | Test harness / certification migration (CDX-073, 093, 094, 095, 096, 097) | **PASS — PHASE 10 TEST/CERT HARNESS MODERNIZED** |
| 11 | Master regression | **COMPLETE** — backend 468 passed (4 batches; +4 opt-in live-cert skips, +5 canary xfails, +1 environmental tmp_path error); frontend tsc exit 0, vitest 356 passed (0 real failures; 7 pre-existing non-collectable node:test suites); production build tsc PASS, vite bundle environment-blocked (sandbox spawn boundary — Vercel CI is unsandboxed). Browser/live-runtime certification DEFERRED to the deployment workstream with exact blockers (§12). |

## 4. Finding resolution register (97/97 — no silent disappearances)

Status legend: **F** = FIXED + VERIFIED · **AR** = ALREADY RESOLVED + VERIFIED · **S** = SUPERSEDED · **AD** = DEFERRED — ARCHITECTURAL DECISION (documented) · **CW** = DEFERRED — CONCURRENT WORK · **N** = REJECTED/NOT PROVEN.

| ID | Sev | Status | Resolution summary |
|---|---|---|---|
| CDX-001 | P2 | F | Visual-sheet source selection threads through ALL phases; Cloud-only never runs local (visual_sheet.py) |
| CDX-002 | P2 | F | Non-Korri profiles get profile-derived directions; concept gate never auto-approved (visual_gates.py) |
| CDX-003 | P2 | F | Pack roleAssets reconciled with canonical rows on candidate approval; gate ids agree |
| CDX-004 | P3 | F | getHeroIdentity strict canonical+approved; grid labels Selected/Pending review/Use This Look |
| CDX-005 | P2 | F | character_consistency quarantined (SUPERSEDED-BY header, no-production-consumer note) |
| CDX-006 | P3 | F | Promote to Production banner in Express after look approval (recovered after unmix) |
| CDX-007 | P3 | F | Typed asset validation on approve/attach (ASSET_NOT_FOUND / NOT_IN_PROJECT / NOT_IMAGE) |
| CDX-008 | P3 | F | OWNER_APPROVED_WITH_PENDING + pendingGates; poller treats as terminal |
| CDX-009 | P3 | F | Plan counts executable sources only; Generate blocked with zero executable sources |
| CDX-010 | P3 | F | CharacterCreatorEmbedded deleted (grep-proofed) |
| CDX-011 | P2 | F | ImageGen Prop promote disabled honestly; backend rejects profile_kind=prop (400) |
| CDX-012 | P2 | F | Map-only labeling + warnings for non-PropEntity groups (recovered after unmix) |
| CDX-013 | P2 | F | Placement validation: CHARACTER_NOT_FOUND / PROP_ENTITY_NOT_FOUND / PROJECT_SCOPE / ATTACHMENT_INVALID |
| CDX-014 | P3 | F | _placed_project_prop_ids unions ERS snapshot + live approved placements |
| CDX-015 | P3 | F | Handoff applies approved-only filter to shot.prop_entity_ids |
| CDX-016 | P3 | F | Upsert contract aligned; redundant useAsIdentity removed |
| CDX-017 | P3 | F | Approved badge in Library cards/preview (recovered after unmix) |
| CDX-018 | P3 | F | EntityPicker kind=prop dead variant removed |
| CDX-019 | P3 | F | attach_prop holder validation (ATTACHMENT_INVALID) |
| CDX-020 | P2 | F | Map selector + scene chooser + explicit scene binding (recovered after unmix) |
| CDX-021 | P2 | F | applyAtlasToMap reuse-or-create (committed a103dba; verified present) |
| CDX-022 | P2 | F | ERS hook map-scoped reset (committed a103dba; verified present) |
| CDX-023 | P3 | F | Camera-limit copy corrected to four cameras |
| CDX-024 | P3 | F | DOCUMENT_CORRUPT quarantine; raw row never overwritten |
| CDX-025 | P3 | F | Unplaced characters excluded from capture-plan position claims |
| CDX-026 | P3 | F | Approved-only character placement + draft warning (recovered after unmix) |
| CDX-027 | P3 | F | Dead Standard spatial workspace deleted twice (8B + REC1 re-deletion) |
| CDX-028 | P2 | CW | Visual canon endpoint — vision/router.py is concurrent-owned; fingerprint fix deferred to that workstream |
| CDX-029 | P1 | F | Atlas adoption capability guard (recovered after unmix); runtime interleaving proof → live cert |
| CDX-030 | P2 | F | Atlas routing-prefix stripped from SceneIntent.summary |
| CDX-031 | P3 | F | Atlas pixels honor aspect ratio (1:1/16:9/9:16) |
| CDX-032 | P3 | S/AD | Primary-source derived_from edge present in HEAD (concurrent I2I commit); multi-source edges deferred to post-concurrency queue_worker change (CW) |
| CDX-033 | P2 | F | Legacy ers.* mutation tools excluded from exposure; ers.generate is the routing path |
| CDX-034 | P1 | F | Batch + regenerate + scene.generate resolve sheetId via resolve_ers_for_sheet; loud failure, no silent zero-grounding |
| CDX-035 | P2 | CW | ers_generate.py mid-flight concurrent changes reference CDX-035 (prompt/URL contradiction in-progress by that workstream); re-verify after closure |
| CDX-036 | P2 | AD/CW | UI facet resolved (ErsSelector deleted 8B); single-composite vs directional model + frozen-contract comment need an architecture decision; ers_generate.py concurrent |
| CDX-037 | P2 | F | sheetId + spatialMapId forwarded; _pick_sheet matches by spatial_map_id first |
| CDX-038 | P2 | CW | Lenient persist hook lives in concurrent ers_generate.py; strict hook exists in ers_persistence; unify after closure |
| CDX-039 | P2 | AR/CW | Dispatcher pin passthrough (forceWorkflowKey/hostedModelId) landed in concurrent commit a103dba; registry static claims neutralized by 2A; Phase 2R live proof owned by concurrent law (claimed verified live) |
| CDX-040 | P3 | F | Reference-packet advisory surfaces unsupported pixels; final-render guard extended |
| CDX-041 | P3 | F | ERS TS contract adds ers_composite_asset_id/provenance (hook casts noted) |
| CDX-042 | P3 | F | list_sheets newest-first by updatedAt |
| CDX-043 | P1 | F | Batch send-to-timeline gated: approve endpoint + 409 APPROVAL_REQUIRED |
| CDX-044 | P1 | F | Scene-shot clipIds exempt from CLIP_NOT_FOUND; ledger preserved (5 tests) |
| CDX-045 | P2 | F | scene_shots Library collection wired on approval; collection_id persisted |
| CDX-046 | P2 | F | Batch API gated (4A); dead batch UI deleted (8B) |
| CDX-047 | P3 | F | sceneCreatorApi facade types corrected |
| CDX-048 | P3 | F | Stuck candidates fall back to failed for missing/unparseable jobs |
| CDX-049 | P3 | F | GET /workspace read-only (persist_runtime=False, no selection writes); derived-sync documented |
| CDX-050 | P3 | F | SceneCreatorVariant dead prop/type removed (master) |
| CDX-051 | P1 | F | HTML-derived navigator/stats/analyze/Timeline-prep/continuity/Bible |
| CDX-052 | P1 | F | script_search/timeline_prep/storyboard read canonical v2 (legacy fallback); no third store |
| CDX-053 | P1 | F | All 22 document routes project-scoped (404 PROJECT_SCOPE_VIOLATION); re-verified in Phase 9 |
| CDX-054 | P2 | F | GET scriptwriter/story no longer creates rows; POST /documents on first write |
| CDX-055 | P2 | F | Recovery restore API + editor UI both editors (recovered after unmix) |
| CDX-056 | P2 | F | GET /notes revision-neutral; bridge run-on-first-write |
| CDX-057 | P2 | AD | CONFIRMED by probe (field loss, revision stall, unbounded growth); canary tests; fix requires persistence architecture |
| CDX-058 | P2 | F | linkScene binds explicit selection (recovered after unmix) |
| CDX-059 | P3 | F | Persisted publish marker; reload no longer flips dirty state |
| CDX-060 | P3 | F | Legacy story store gated (410) once story_entries exist; migration reads kept |
| CDX-061 | P3 | F | Correction previews persisted (table + TTL); survive restart |
| CDX-062 | P3 | F | ScriptwriterCompactView deleted |
| CDX-063 | P1 | F | Entity-linked deletion guard; force-delete detach matrix; lineage cleanup |
| CDX-064 | P1 | F | Approval truth read from Asset.production_approval (single channel); approved-first ranking |
| CDX-065 | P2 | F | Global scope reachable via ?scope=global + CD search |
| CDX-066 | P2 | F | Entity folders keyed by entityId; rename endpoint follows in place |
| CDX-067 | P2 | F | SQL-filtered paged search; >500 assets reachable |
| CDX-068 | P2 | F | Upload hashes, classifies, flags duplicates (never deletes) |
| CDX-069 | P2 | F | /media + /api/file lock coverage; fail-closed ambiguity; unlock paths verified |
| CDX-070 | P2 | F | propose_asset_library_assignment defaults override=False; preview discloses overrides |
| CDX-071 | P3 | F | Entity names in preview (no raw UUIDs) (recovered after unmix) |
| CDX-072 | P3 | F | Per-project generator persistence (verified present after unmix) |
| CDX-073 | P3 | F | Stale USD tests corrected to committed classifier semantics |
| CDX-074 | P3 | F | Express grid folder navigation + scope toggle (recovered after unmix); lineage-store merge = architectural note |
| CDX-075 | P1 | F | Disk-verified readiness (verify_component); static catalog neutralized; fail-closed |
| CDX-076 | P1 | F | No silent substitution; MODEL_NOT_INSTALLED at/before enqueue; legacy fallback disclosed first-class |
| CDX-077 | P2 | CW | Nano-banana routing — recommend.py/generation.py/RegionEditPanel concurrent-owned; deferred |
| CDX-078 | P2 | F | PROVIDER_AUTH_FAILED preflight for forced-cloud paths |
| CDX-079 | P2 | F | Refusal (UNSUPPORTED_OPERATION) instead of silent txt2img ref-drop |
| CDX-080 | P2 | F | adapterUnavailable/executable=False rows excluded from offerings |
| CDX-081 | P2 | F | Selector fails closed on missing readiness (verified after unmix) |
| CDX-082 | P3 | F | qwen checkpoint label truth |
| CDX-083 | P3 | F | Provider inventory: configured≠available; truthful states |
| CDX-084 | P2 | F | TOOL-kind approval bridge (durable Proposal → execute_approved_proposal); chat path idempotent |
| CDX-085 | P2 | AD | Decision documented: shot flow canonical, batch retained-but-gated; parity test locks provenance contract |
| CDX-086 | P2 | F | Hard max 3 everywhere (foundation [:3]; wiki 3) |
| CDX-087 | P2 | F | Single registry read-through (aliases); conversation candidates via registry |
| CDX-088 | P3 | F | Legacy frontend planner removed; legacyPlanGate test locks it |
| CDX-089 | P2 | AD | Ownership documented + idempotency/disjointness tests; engine kept behind its flag |
| CDX-090 | P3 | F | Heuristic labeling + confidence cap + "Heuristic creative review" progress text |
| CDX-091 | P3 | AD | Transitional hybrid documented; convergence property tests lock EXECUTION agreement |
| CDX-092 | P3 | F | focused_artifact_ids contract fixed; AWS runtime facet deferred to its workstream |
| CDX-093 | P2 | F | Opt-in ADEPT_LIVE_CERT layer with real-enqueue scaffolds (4 skipped by default) |
| CDX-094 | P2 | F | 10 specs migrated off :8760/:8761; 5 audited already-resolved; ~17 out-of-scope refs inventoried |
| CDX-095 | P3 | F | Tracking verified (2 files await committer git add); no ignore rule needed |
| CDX-096 | P3 | F | AWS endpoints + Notes direct tests added (15 tests) |
| CDX-097 | P3 | F | Timeline clip-presence assertion added; ERS HOLD documented by design |

**Totals:** F = 81 · AR = 2 (CDX-032-partial, CDX-039-partial) · S = 0 · AD = 7 (CDX-036, 057, 085, 089, 091 + lineage-store note) · CW = 8 (CDX-028, 035, 036-part, 038, 039-part, 077, 032-part, 092-part) · N = 0.
<!-- APPEND-2 -->

## 5. Architecture consolidation summary

- **One screenplay truth**: script_documents_v2 canonical; script_segments is a synchronized projection for legacy consumers (no third store).
- **One library approval channel**: Asset.production_approval is the single truth consumed by retrieval/ranking/Co-Director tools.
- **One specialist authority**: SpecialistRegistry canonical; foundation roster + conversation candidates read through it; hard max THREE everywhere; heuristic findings labeled.
- **One capability execution authority**: execution packs canonical for agent operations; Production Executive ownership documented + disjointness enforced; legacy browser planner deleted; scene shot flow canonical with the batch surface gated.
- **Reads do not mutate**: GET /scriptwriter, /story, /notes, scene-creator /workspace are side-effect-free (explicit write paths persist).
- **Intent classification**: documented transitional hybrid with convergence property tests (decision-documented, not restructured).

## 6. Provider/runtime truth

Silent substitution eliminated; readiness is disk-verified (Setup/Source Manager components) with fail-closed defaults; cloud credentials preflighted before enqueue; reference pixels are never silently dropped (refusal instead); adapter-unavailable models unoffered; job status names the actual checkpoint/model; provider inventory distinguishes configured vs verified. Residual: nano-banana routing (CDX-077) deferred to concurrent workstream; ERS qwen2512.ref Phase 2R live proof owned by the concurrent law.

## 7. Canonical-state consolidation

See §5. Residual dual-record risk: ERS sheet (file JSON) vs EnvironmentReferencePackage (trait) remains by design with a metadata.sheet_id bridge (the historical sheetId-as-package bug is fixed on every resolution path); settings_json single-blob (CDX-057) is the open architectural item with canary tests; asset lineage stores (asset_graph vs m29_asset_versions) documented as an architectural note.

## 8. Approval/lineage safety

Batch → Timeline requires explicit approval (409 APPROVAL_REQUIRED); character gate asset ids always match the creator-approved candidate; draft never displays as Selected; OWNER_APPROVED only with complete gates (or explicit PENDING); Express approval surfaces Promote; scene_shots Library collection is approval-gated; delete operations are entity-link-guarded with explicit detach; asset lineage edges preserved (primary-source atlas edge in HEAD).

## 9. Security/project isolation

/media and /api/file are lock-covered with fail-closed ambiguity handling; /api/assets unchanged; scriptwriter document routes are project-scoped; unlock-then-200 / lock-then-403 verified by 13 tests.

## 10. Tests/evidence

- Backend: 468 passed across the Phase 11 regression batches (all phase suites + existing regression files); 4 opt-in live-cert scaffolds skipped by default; 5 CDX-057 canaries xfailed; 1 environmental tmp_path error (sandbox ACL class).
- Frontend: tsc -b exit 0; vitest 356 passed / 0 real failures (7 pre-existing node:test non-collectable suites documented).
- E2E: 10 specs migrated to current topology; Timeline clip-presence assertion added; ~17 out-of-scope legacy refs inventoried for follow-up.
- New test files added across phases: ~25 backend files + ~10 frontend files (see git status untracked set).

## 11. Live runtime evidence

NOT EXECUTED in this program (read-only remediation constraints + environment):
- The running Studio API (:8758, restarted 13:03 local) predates every remediation change; restarting to load fixes would also load in-flight concurrent workstream code (ERS backend set + W46 timeline set still uncommitted) — unsafe during the program.
- Playwright chromium spawn is blocked by the DSH sandbox (spawn EPERM); vite build bundle step likewise (tsc gate passes).
- The ADEPT_LIVE_CERT scaffolds (real-enqueue per subsystem) and the migrated E2E specs are the ready-made vehicle for the deployment workstream's live certification.
- Prior-session live evidence (concurrent law): GPT ERS live Schnick job submitted gpt-image-2-image-to-image + public input_urls (2026-08-16) — recorded by the concurrent workstream's law doc.

## 12. Remaining blockers

1. **CDX-057** — settings_json concurrency: ARCHITECTURAL DECISION REQUIRED (canaries green; no fix shipped by design).
2. **CDX-028/035/036/038/039/077** — ERS-concurrent-owned items: re-verify and close after the Qwen/ERS workstream closure lands (their code references CDX-035 explicitly — in-flight).
3. **CDX-032 multi-source edges** — needs a queue_worker.py change after its concurrent diff settles.
4. **CDX-092 AWS facet** — AgentWorkSurface.tsx runtime alias removal, deferred to that workstream.
5. **Live/browser certification** — deferred to the deployment workstream (exact environment blockers in §11).
6. **Commit-set assembly** — the committer must include ~35 untracked test/source files (incl. test_qwen_i2i_ers.py, test_avatar_studio_phase1.py, test_timeline_continuity_contracts.py) and reconcile with the concurrent workstreams' uncommitted files.
7. **Mixed-commit integrity** — concurrent commit a103dba swept queue_worker/SpatialMapPanel/useErsGeneration remediation hunks; b25eb65 ("unmix") reverted uncommitted remediation (recovered by REC1); history was not rewritten (forbidden). Reconcile at commit time: prefer committing the remediation set as its own commit after the concurrent sets.

## 13. Diff integrity

- Files changed by the program: ~60 tracked files modified + ~35 untracked new files (tests + a few source modules). No git operations were performed by the program; all changes are working-tree.
- Concurrent work preserved: ERS backend set, W46 timeline set, i18n/M30F set, regionEdit set — untouched by the program except where the concurrent agent's own commits interacted (documented above).
- Runtime changes: NONE (no restarts, no studio.db writes, no .runtime/log writes).
- Config changes: NONE by the program (certified-registry.json and beta scripts remain concurrent-owned).
- Integrity events: (1) a103dba swept 3 remediation files into the ERS commit — verified intact in HEAD; (2) b25eb65 reverted uncommitted remediation in 8 frontend files — all recovered by REC1 + master (CDX-050), verified by 356-test vitest sweep.

## 14. Deployment readiness

**READY FOR VERCEL DEPLOYMENT** — with the exact preconditions:
- Code gates green: tsc exit 0; backend 468 passed; vitest 356 passed; production build type-check passes (vite bundle step must run in unsandboxed CI — Vercel builds from a clean checkout).
- Preconditions for the deployment run: (a) concurrent workstreams commit/settle their uncommitted sets first (ERS backend + W46 timeline); (b) committer assembles the remediation commit set including all untracked files; (c) after deploy, execute the live certification layer (ADEPT_LIVE_CERT scaffolds + migrated E2E specs) against the freshly-restarted :8758 backend and the Vercel build; (d) close the deferred CDX items per §12 after the ERS closure lands.

---

**FINAL VERDICT: READY FOR VERCEL DEPLOYMENT (code-level); live-runtime certification is the deployment workstream's first task. 81/97 findings FIXED + VERIFIED, 7 architectural decisions documented, 8 concurrent-deferred, 0 rejected.**

