# Clean Creator Data Reset Report

**Milestone:** ADEPT UI — Clean Creator Data Reset + Fresh Timeline Baseline
**Date:** 2026-08-08 (UTC)
**Branch:** `feature/ai-guided-setup`
**Starting SHA:** `fa09c99d6395c29461cdec4555055faad116c435`

---

## 1. Purpose

Remove only creator/project/runtime data associated with existing sample (development) projects so that historical failed jobs, old Timeline migrations, stale workspace state, and pre-repair project state cannot contaminate current manual Beta observations. This is a PROJECT/CREATOR-DATA reset only — not an application, model, configuration, or source-code reset.

## 2. Safety Audit — What Was Preserved

**NOT deleted (preserved):**
- Source code, application configuration, certified workflow registry (`config/video-workflows/certified-registry.json`), provider configuration
- ComfyUI models, model weights, LoRAs, VAEs, text encoders (`data/models` — 110 GB)
- Runtimes, venvs, sandbox (`data/runtimes`, `data/m210b-*`)
- Application-level settings (`data/production_control`, `data/hosted_providers`, `data/codirector/status`)
- Secrets (`data/secrets`)
- Release-gate documentation, tests, logs required for certification evidence
- `schema_migrations` table (27 rows — app-level schema history)

## 3. Pre-Reset Inventory

**Source:** [`pre_reset_inventory.json`](pre_reset_inventory.json)

- **Projects:** 54 (all development/example: COI-*, CW-*, PL-*, PoseCraft*, WCC*, patch-probe, Dbg, H3-PRIVATE-LIVE-E2E, The Dreamweaver, etc.)
- **Scenes:** 54
- **Jobs:** 8 (3 failed `render_scene` on "The Dreamweaver", 5 done `imagegen` on H3-PRIVATE-LIVE-E2E)
- **Assets:** 11 (all `scope=project`)
- **Character profiles:** 24; **Voice profiles:** 15
- **Disk:** `data/projects/` ~230 dirs / 1846 MB, `data/assets/` ~170 dirs / 22 MB, plus 8 other project-id-keyed dir families (~1931 MB total creator data)

## 4. Backup

**Location:** `data/backups/pre-clean-beta-reset_2026-08-08T03-54-51Z/`
**Manifest:** `MANIFEST.txt` (in backup dir)

**Verification:**
- `studio.db` copied; backup DB opens and reports 54 projects (matches source)
- 11 project-id-keyed dir families copied (~1931 MB; models/venvs/runtimes/secrets excluded)
- Backup verified before any deletion proceeded

## 5. Prerequisite Repairs (Phase 0)

### 5.1 Cascade repair — `delete_project_residue`

The authoritative deletion path ([`studio-api/app/project_cleanup.py`](studio-api/app/project_cleanup.py)) covered all `project_id`/`projectId` tables plus 19 indirect cascades, but missed 8 tables. Added 8 entries to `_INDIRECT_PROJECT_DELETES`:
- `asset_versions` (via `asset_id IN assets`)
- `asset_edges` (via `from_id`/`to_id IN assets`)
- `codirector_approvals` (via `proposal_id IN codirector_proposals`)
- `codirector_execution_receipts` (via `proposal_id IN codirector_proposals`)
- `creative_item_versions` (via `item_id IN creative_items`)
- `m212_lesson_versions` (via `lesson_id IN m212_lessons`)
- `m28_recipe_stages` (via `recipe_id IN m28_recipes`)
- `m28_shot_profile_versions` (via `profile_id IN m28_shot_profiles`)

**Regression test:** [`studio-api/tests/test_project_cleanup_cascade.py`](studio-api/tests/test_project_cleanup_cascade.py) — 3 tests pass (cascade cleans all 8 repaired tables + project-scoped parents; m20/m28 chain coverage; other projects preserved).

### 5.2 Workspace nav prune — `pruneDeletedProjects`

Added `pruneDeletedProjects(validIds: Set<string>)` to [`studio-web/src/workspacePrefs.ts`](studio-web/src/workspacePrefs.ts), filtering both `adept_ui_last_workspace` (lastWorkspaceByProject map) and `adept_ui_recent_projects`. Wired into Home's `refresh()` in [`studio-web/src/pages/Home.tsx`](studio-web/src/pages/Home.tsx) so deleted project IDs never remain navigation targets.

**Unit tests:** [`studio-web/src/workspacePrefs.test.ts`](studio-web/src/workspacePrefs.test.ts) — 11 tests pass (4 new prune tests + 7 existing).

### 5.3 Build + test

- `npm --prefix studio-web run build` — succeeded
- API unit tests (cleanup + w46 + drift gate) — 14 passed (3 cascade + 8 w46 + 3 drift gate)
- Web unit tests (workspacePrefs + formatDuration + TimelinePreviewComposer) — 36 passed

## 6. Authoritative Deletion (Phase 2)

### 6.1 Deletion stress metrics

**Evidence:** [`reset_evidence.json`](reset_evidence.json) (final idempotent state); first-run stdout captured 54 deletions.

All 54 projects deleted via `DELETE /api/projects/{id}` (repaired authoritative cascade):
- **Count:** 54
- **OK:** 54 (HTTP 200)
- **Errors:** 0
- **Latency range:** 29.37 ms – 342.46 ms
- **Typical (p50):** ~48 ms
- **Outliers:** `CW-Doc-6192` (342 ms), `CW-Doc-probe` (157 ms), `H3-PRIVATE-LIVE-E2E` (134 ms) — all succeeded; no errors or timeouts

**Assessment:** The deletion subsystem handled 54 consecutive authoritative deletions without a single API error. The slowest deletions (300+ ms) correspond to projects with more cascade children (Co-Director conversations, production job events). No outliers indicated a defect — all returned 200.

### 6.2 Orphan cleanup

The authoritative DELETE only cascades for the 54 projects that existed at reset time. 164 pre-existing orphan rows (referencing projects deleted in prior dev sessions) across 17 tables were removed as documented orphan cleanup:

| Table | Orphan rows |
|---|---|
| codirector_conversation_events | 34 |
| codirector_conversations | 25 |
| character_profiles | 22 |
| m211_decision_records | 14 |
| m29_asset_versions | 14 |
| voice_profiles | 15 |
| m29_audio_cues | 9 |
| voice_performance_records | 7 |
| codirector_tool_invocations | 4 |
| spatial_scenes | 4 |
| script_docs | 4 |
| editor_projects | 3 |
| codirector_proposals | 2 |
| script_segments | 2 |
| storyboard_panels | 2 |
| production_job_events | 1 |
| voice_performance_plans | 1 |
| script_documents_v2 | 1 |
| **Total** | **164** |

Plus indirect orphans: 424 `asset_versions`, 161 `asset_edges` (pre-existing dangling rows whose assets were already gone).

### 6.3 Disk cleanup

All project-id-keyed dirs removed (every UUID-named entry — all dev/orphan residue):

| Dir family | Entries removed |
|---|---|
| projects | 230 |
| assets | 167 |
| environment_reference_sheet | 106 |
| image_product | 65 |
| image_pipeline | 53 |
| minimax_h3 | 51 |
| audio_studio | 18 |
| storyboard_studio | 20 |
| visual_continuity | 20 |
| timeline_retakes | 5 |
| exports | 9 |
| **Total** | **744** |

### 6.4 Integrity gate

**Result:** PASSED — all 28 checks green.

- Core tables empty: `projects`, `scenes`, `jobs`, `assets`, `character_profiles`, `voice_profiles` — all 0
- Indirect tables empty: `asset_versions`, `asset_edges`, `codirector_approvals`, `codirector_execution_receipts` — all 0
- Dangling references: 0 (scene→project, job→project, version→asset, edge→asset, approval→proposal, receipt→proposal)
- App-level intact: `schema_migrations` = 27 (untouched)
- Disk dirs clean: 0 UUID entries remaining in all 11 families

## 7. Clean Beta Restart (Phase 3)

- Stop → start via `Start-AdeptUI-Beta.ps1 -NoBrowser`
- No `ADEPT_TIMELINE_CERT_STUB`, no `ADEPT_TIMELINE_WORKFLOW_EXPORT`
- `http://127.0.0.1:8760/` → 200
- `http://127.0.0.1:8758/api/health` → 200
- Cert stub endpoint → 404 (disabled)
- Zero unintended process restarts during startup

## 8. Fresh Project Baseline (Phase 4)

**Playwright spec:** [`tests/e2e/timeline/clean-creator-data-reset-baseline.spec.ts`](tests/e2e/timeline/clean-creator-data-reset-baseline.spec.ts) — 4 tests pass.

### 8.1 Clean slate + fresh project

- Before creation: 0 projects (clean slate verified)
- Created "Timeline Clean Slate Test" via `POST /api/projects`
- **Project ID:** fresh UUID (created by API)
- **Scene ID:** fresh UUID (default "Scene 1" auto-created)
- Exactly 1 project, 1 scene, 0 jobs, 0 failed jobs
- Timeline master: 1 default batch block (unconfigured — no generator, no source image)
- No dismissed failure job IDs
- No preview failure state

### 8.2 localStorage prune proof

Seeded stale deleted project IDs into `adept_ui_last_workspace` and `adept_ui_recent_projects`. After reloading Home (which calls `pruneDeletedProjects` with real project IDs):
- Stale workspace IDs pruned (undefined)
- Stale recent-project IDs pruned (not found in list)
- Real surviving entries preserved

## 9. Clean Timeline Test (Phase 5)

- Entered Timeline explicitly
- Created Batch 1/2/3 via real endpoints (`POST .../batches`, `PATCH .../batches/{id}`)
- Uploaded 3 visibly distinct procedurally-generated PNGs (red/green/blue 8x8) via real `POST /api/projects/{pid}/assets`
- Bound each image to its batch via real clips endpoint
- **Assertions passed:**
  - Unique batch IDs (3 distinct)
  - 0 historical jobs after batch authoring
  - No `live-preview-failed-overlay` visible
  - `GET .../preflight` succeeded (`ok=true`, `mock=false`)
  - Cross-batch preview switching exercised
- Screenshot: `artifacts/03-timeline-clean-baseline.png`
- Project cleaned up after test (slate stays clean for manual creator use)

## 10. Drift Baseline (Phase 6)

**Evidence:** [`drift_baseline_result.json`](drift_baseline_result.json), [`drift_workflow_export.json`](drift_workflow_export.json)

Restarted API with `ADEPT_TIMELINE_WORKFLOW_EXPORT=1` only. Created a fresh project + batch with `ltx-local` generator, called `POST .../batches/{id}/workflow-export`.

**Required runtime behavior — all verified:**

| Field | Required | Actual |
|---|---|---|
| `selectedPath` | `topology` | `topology` |
| `topologyMatch` | `true` | `true` |
| `bindingsValid` | `true` | `true` |
| `legacyGraphHashCheck` | `false` | `false` |

**PID-scoped log scan** (API PID 5800, start timestamp bound):
- `workflowFingerprint` lines: 3 (present, emitted by this process instance)
- `graphHash mismatch` lines: 0 (zero — no legacy drift errors)
- Fingerprint line confirms: `workflow=ltx.simple_i2v@1.0.0 selectedPath=topology topologyMatch=true bindingsValid=true legacyGraphHashCheck=false`

**No `graphHash mismatch` appeared for a freshly-created generation.** The topology + bindings contract is the live runtime path; legacy `graphHash` is not consulted for certified entries.

## 11. Final Clean Beta State

- Final restart with no env flags (no cert stub, no export env)
- `http://127.0.0.1:8760/` → 200 (creator UI)
- `http://127.0.0.1:8758/api/health` → 200 (Studio API)
- Cert stub: disabled (404)
- Export env: disabled (404)
- API PID: 23952
- **Projects: 0** (clean slate verified after second-pass review cleanup)
- **Orphan asset dirs: 0** (all UUID-named dirs removed)
- Beta left running for manual creator generation

### 11.1 Second-pass review remediation

The Kimi K3 second-pass review ([82c48d72](82c48d72-885b-46b6-8125-b988c2055353)) found 3 blocking findings, all addressed:

1. **Residue "Drift Baseline Test" project** — a failed verifier run leaked a project. Deleted via authoritative DELETE; re-verified 0 projects + 0 orphan disk dirs.
2. **`verify_clean_drift_baseline.py` leaked projects on failure paths** — restructured `main()` with `try/finally` cleanup that always attempts the delete and warns loudly if cleanup fails. Evidence written BEFORE verdict so it survives FAIL returns.
3. **4 additional uncovered indirect tables** (`creative_item_versions`, `m212_lesson_versions`, `m28_recipe_stages`, `m28_shot_profile_versions`) — added cascade entries + regression test coverage. All 3 cascade tests pass.

## 12. Files Changed

**Source:**
- [`studio-api/app/project_cleanup.py`](studio-api/app/project_cleanup.py) — added 4 cascade entries
- [`studio-web/src/workspacePrefs.ts`](studio-web/src/workspacePrefs.ts) — added `pruneDeletedProjects`
- [`studio-web/src/pages/Home.tsx`](studio-web/src/pages/Home.tsx) — wired prune into refresh

**Tests:**
- [`studio-api/tests/test_project_cleanup_cascade.py`](studio-api/tests/test_project_cleanup_cascade.py) — new (2 tests)
- [`studio-web/src/workspacePrefs.test.ts`](studio-web/src/workspacePrefs.test.ts) — added 4 prune tests
- [`tests/e2e/timeline/clean-creator-data-reset-baseline.spec.ts`](tests/e2e/timeline/clean-creator-data-reset-baseline.spec.ts) — new (4 tests)

**Scripts:**
- [`scripts/backup_creator_data_pre_reset.py`](scripts/backup_creator_data_pre_reset.py) — new
- [`scripts/write_pre_reset_inventory.py`](scripts/write_pre_reset_inventory.py) — new
- [`scripts/clean_creator_data_reset.py`](scripts/clean_creator_data_reset.py) — new
- [`scripts/verify_clean_drift_baseline.py`](scripts/verify_clean_drift_baseline.py) — new

**Evidence:**
- [`pre_reset_inventory.json`](pre_reset_inventory.json)
- [`reset_evidence.json`](reset_evidence.json)
- [`drift_workflow_export.json`](drift_workflow_export.json)
- [`drift_baseline_result.json`](drift_baseline_result.json)
- `artifacts/` — Playwright screenshots + JSON artifacts

## 13. Limitations

- The deletion stress metrics from the first run (54 deletions, all 200) were captured in stdout; the idempotent second run (which performed the extended orphan cleanup) overwrote `reset_evidence.json` with a 0-deletion summary. The first-run stdout is the authoritative record of the 54-deletion stress test.
- The Playwright spec creates and deletes its own fresh project; the slate is left at 0 projects after the spec runs. The creator's manual "Timeline Clean Slate Test" will be the first real project on the clean baseline.
- Browser localStorage pruning is proven via the Playwright test context; the creator's actual browser profile is not modified by the agent. The in-app `pruneDeletedProjects` wiring ensures any stale IDs are pruned on the next Home load.
- **Disk asset dir gap:** the authoritative `DELETE /api/projects/{id}` cleans DB rows (via the repaired cascade) but does not remove the project's `data/assets/<pid>/` disk directory. Test projects created after the reset left orphan disk dirs that were manually removed. This is a latent gap in the API's delete path (out of scope for this creator-data reset) — the API should own disk cleanup for project-owned assets per Build Law #29.
- The 4 additional indirect tables (`creative_item_versions`, `m212_lesson_versions`, `m28_recipe_stages`, `m28_shot_profile_versions`) had 0 rows pre-reset, so the reset outcome was unaffected by the latent cascade gap; the repair is preventive.

## 14. Manual Review Path

1. Open `http://127.0.0.1:8760/` (creator UI)
2. Create a new project via the normal creator-facing flow
3. Enter Timeline, create batches, and perform Generate / Generate Scene
4. Verify no historical errors, no `graphHash mismatch`, preflight green

Beta is running and ready.

---

## GO — CLEAN CREATOR DATA BASELINE READY FOR MANUAL TIMELINE GENERATION
