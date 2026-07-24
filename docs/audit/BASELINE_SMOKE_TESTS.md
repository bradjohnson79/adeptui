# Baseline Smoke Tests

**Status:** EXECUTED WITH CAPTURED BASELINE EXCEPTIONS  
**Evidence log:** `docs/audit/phase0-baseline-results.json`  
**Safety result:** Isolated smoke and recovery fixtures did not use production data.

## Baseline identity

- Branch: `feat/director-workspace`
- HEAD: `2c5f61d574f27aed8c4f4adc70e9c993bb862aa1`
- Working tree: intentionally dirty with broad existing work (22 modified, 60 untracked after removal of three transient text files)
- Runtime: Node 22.23.1; npm 10.9.8; Python 3.11.15; ffmpeg 8.1.2
- GPU: RTX 5090, 32607 MiB
- Services: ComfyUI HTTP 200; Ollama HTTP 200
- Capture shell: no `STUDIO_*` environment variable names set
- Production SQLite, read-only inspection: SHA-256 `47abc7c2848fb2ed9695a04020779050fb9dbb1034fd94c6e7cb635c6ed27fe6`; integrity OK; 15 tables

## Execution record

| Test | Result | Evidence / classification |
|---|---|---|
| Python compile | Pass | `compileall` exit 0 |
| Backend full suite | Pass | 9 passed, 0 failed; 5 Pydantic deprecation warnings |
| Baseline API startup | Pass | Isolated startup check passed |
| Isolated backend smoke | Pass | 3 passed; `production_data_used: false` |
| SQLite initialization | Pass | Temporary isolated data |
| Project create/open/save | Pass | Covered by isolated smoke |
| Scene creation | Pass | Covered by isolated smoke |
| Job creation/list | Pass | Covered by isolated smoke |
| Asset upload/library | Pass | Covered by isolated smoke |
| Backup safety tests | Pass | 3 passed |
| Recovery drill | Pass | Temporary fixture manifests, integrity, row, and project matched |
| Development API startup | Pass | API health HTTP 200 |
| Development web startup | Pass | Web HTTP 200 |
| ComfyUI reachability | Pass | HTTP 200 |
| TypeScript | Captured baseline failure | Exit 2; 15 diagnostics in four existing UI files |
| Frontend build | Captured baseline failure | Exit 2 on the same 15 TypeScript diagnostics |
| Lint | Not captured | No verified result supplied; no pass claimed |
| Profile / Story / Scene Sheet deep journey | Deferred/manual | Not covered by the isolated smoke suite |
| Director → Editor handoff | Deferred/manual | Not covered by the isolated smoke suite |
| Job cancel/restart reconciliation | Deferred/manual | Restart reconciliation remains future product work |
| Full generated-output lineage | Deferred/manual | Incomplete lineage remains a product risk |
| Audio / Editor / final export journey | Deferred/manual | No deep UI/product pass claimed |
| First-time user click-through | Deferred/manual | Audit exists; interactive journey not recorded as passed |

Exact harness commands, durations, exit codes, and output are retained in `docs/audit/phase0-baseline-results.json`.

## Recovery evidence

The backup/recovery CLI was exercised against a temporary fixture:

- create/verify manifests matched;
- verify/restore manifests matched;
- restored SQLite integrity passed;
- restored row and project matched;
- archive SHA-256 was `b91593c79b648e9dfe171b045955fbc28d8cdd60dcaacf3ff818814d66f00561`;
- the fixture was removed;
- no production data was accessed.

Production SQLite was only inspected read-only; it was not used by the isolated baseline suite or recovery drill.

## Captured frontend exception

TypeScript and the frontend build report the same 15 diagnostics in:

- `src/components/AssistantPanel.tsx`
- `src/components/AvatarStudioWorkspace.tsx`
- `src/components/ProjectHome.tsx`
- `src/pages/Home.tsx`

No diagnostic occurs in the new Phase 0 core/workspace files. There is no pre-edit TypeScript snapshot, so the defensible classification is **captured baseline failures not attributable to Phase 0**, not a claim that they are mathematically proven pre-existing.

## Deferred product risks

The following are future work and are not Phase 0 failures:

- queued/running job reconciliation after restart;
- orphan and deletion handling;
- incomplete generated-output lineage;
- machine-specific model and ComfyUI paths.

## Approval rule

These results complete Phase 0 safety evidence with the frontend diagnostics recorded as the main baseline exception. They do **not** authorize or start Phase 1. Explicit approval is required, and all new architecture paths remain additive, unwired, and default-off until then.

