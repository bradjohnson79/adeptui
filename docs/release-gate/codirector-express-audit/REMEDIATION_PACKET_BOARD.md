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

## Phase 2 — Provider/model/execution truth (IN PROGRESS)

| Packet | CDX ids | Status | Subagent | Notes |
|---|---|---|---|---|
| 2A readiness authority | CDX-075, CDX-081, CDX-083 | IN PROGRESS | 2A-readiness | disk-verified readiness; fail-closed selector; provider inventory truth |
| 2B model substitution | CDX-076, CDX-082 | IN PROGRESS | 2B-model-substitution | no silent swap; MODEL_NOT_INSTALLED; qwen checkpoint label |
| 2C scene/region honesty | CDX-077, CDX-078, CDX-079, CDX-080 | IN PROGRESS | 2C-scene-region-honesty | CDX-077 DEFERRED - CONCURRENT WORK (recommend.py/generation.py/RegionEditPanel active) |
| 2D character sources | CDX-001, CDX-009 | IN PROGRESS | 2D-character-sources | source choice on all phases; Auto Select executability |

Live-proof note (master): Studio API :8758 (200) + Comfy :8188 (200) up, but the running API predates remediation fixes (restarted 13:03 local) and the Qwen/ERS workstream is mid-edit - real-runtime generation proof DEFERRED to Phase 11 master regression; unavailable-model block proven at integration level in Phase 2.

## Phase 3 — Script Writer canonical truth (OPEN)

CDX-051, CDX-052, CDX-053, CDX-058 — mostly serial; architecture decision: script_documents_v2 is canonical.

## Phase 4 — Approval/canonization/Timeline (OPEN)

4A CDX-043, CDX-034, CDX-046 · 4B CDX-002, CDX-003, CDX-004, CDX-006, CDX-007, CDX-008 · 4C CDX-044, CDX-045

## Phase 5 — Spatial/Atlas/ERS handoff (IN PROGRESS — image-conditioning law VERIFIED)

Governing write-up: `docs/release-gate/ers/SPATIAL_MAP_ERS_IMAGE_CONDITIONING_LAW.md`  
Verdict: **SPATIAL MAP / ERS IMAGE-CONDITIONING LAW — VERIFIED** (2026-08-16). Does **not** issue Express `READY FOR VERCEL DEPLOYMENT`.

| Packet | CDX ids | Status | Notes |
|---|---|---|---|
| Image-conditioning law (Express Phase 5 amendment) | CDX-035, CDX-039, Atlas source lineage | VERIFIED | GPT ERS live Schnick job `1831766c` submitted `gpt-image-2-image-to-image` + public `input_urls` for `4d3062e8-…`. Qwen remains `qwen2512.ref`. Atlas-with-source is I2I; no-source Atlas stays T2I. Visual Canon unavailable (honest). |
| Remaining Phase 5 | CDX-012, 013, 014, 015, 019, 020, 028, 029, 030, 031, 032, 037, 038, 042, 072 | OPEN | Not closed by the image-conditioning law. |

Qwen/ERS Phase 2 closure remains PARTIAL PASS on pixels / Visual Canon (`docs/release-gate/ers/QWEN_I2I_ERS_PHASE2_CLOSURE_REPORT.md`). Pixel same-set is a separate bar from this law’s T2I binary.

## Phase 6 — Library retrieval/approval/discoverability (OPEN)

CDX-064, CDX-065, CDX-066, CDX-067, CDX-068, CDX-017, CDX-070, CDX-074

## Phase 7 — Orchestration consolidation (OPEN — architecture-sensitive)

CDX-084, CDX-085, CDX-086, CDX-087, CDX-088, CDX-089, CDX-090, CDX-091, CDX-092

## Phase 8 — Text system / legacy cleanup (OPEN)

CDX-059, CDX-060, CDX-061, CDX-062, CDX-010, CDX-018, CDX-027, CDX-046(dead UI)

## Phase 9 — Security / project isolation (OPEN)

CDX-069 (+ CDX-053 ownership re-check)

## Phase 10 — Test harness / certification migration (OPEN)

CDX-093, CDX-094, CDX-095, CDX-096, CDX-097, CDX-073

## Phase 11 — Master regression (PENDING)

## Phase 12 — Final remediation report (PENDING)
