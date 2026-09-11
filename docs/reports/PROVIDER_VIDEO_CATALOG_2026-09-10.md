# Provider Video Catalog + Catalog Sync Utility + Timeline UX Root Fixes

**Date:** 2026-09-10 · **Branch:** `feat/character-creator-final-closure` · **Mission plan:** `provider_catalog_fast_path_20ebc262.plan.md`

This is the governing report for the Provider Catalog Fast Path mission: read-only enumeration of the fal / Kie / WaveSpeed video catalogs, a permanent Provider Catalog Sync utility with an admin refresh command, the canonical-registry foundation, and the three Timeline UX root fixes (always-on preflight, H3 15s default, Library modal top Add).

---

## 1. Catalog discovery results (read-only, zero paid generations)

**Live refresh evidence:** `data/hosted_providers/provider_catalog.json` — `updatedAt 2026-09-11T05:20:58Z`, **459 normalized rows**, all `pending_review` (never auto-exposed). Second live refresh: `new=0, updated=0, removed=0` (idempotent — see §2.1 for the defect the hardened proof caught and the repair). No generation endpoints were called at any point — enumeration + schema reads only.

| Provider | Rows | Source | Key status |
|---|---|---|---|
| fal | 391 | Centralized catalog API (`/v1/models` cursor pagination + per-endpoint schema inspect) | `fal_api_key` present |
| Kie | 68 | docs.kie.ai `llms.txt` index + embedded OpenAPI YAML per page | `kie_api_key` present |
| WaveSpeed | 0 | `GET /api/v3/models` source implemented | **`wavespeed_api_key` missing → honest `Requires Setup`** (not an error) |

**Schema coverage:** 389/391 fal endpoints schema-verified; 2 residual genuine 404s (`fal-ai/decart/lucy-5b/image-to-video`, `minimax/h3-max/director` — catalog lists them, schema endpoint 404s; rows kept with `status: discovered`).

### Surface eligibility (contract predicates over all 459 rows)

| Surface | Predicate | Eligible rows |
|---|---|---|
| Text to Video | `t2v` | 150 |
| 1 Frame | `i2v AND firstFrame` | 227 |
| 3 Frame | `i2v AND firstFrame AND lastFrame` | 78 |
| Timeline-Omni | `r2v OR (i2v AND firstFrame)` | 237 |

### Required coverage checks

- **Seedance** — 26 fal rows. 2.0 Fast: 4–15s (≤15s ✓), 480p/720p, audio. 2.0 standard I2V: first+last frame ✓, 480p/720p/1080p/4k ✓. 2.5: 4–30s native ✓, 480p/720p/1080p. All 2.0 Mini/Fast/standard + 2.5 present.
- **MiniMax H3 Max (fal)** — 7 rows: T2V / I2V / R2V / multi-angle / turbo, **5–15s, 480P/768P/1080P**. `minimax/h3-max/director` = discovered (schema 404).
- **MiniMax H3 (Kie)** — 3 rows: T2V / I2V / R2V, **4–15s, 768P/2K**.
- **Kling (fal)** — 61 rows: v1.x–v2.x, **o1, o3 (standard/pro/4k)**, T2V/I2V/R2V/V2V; o3 3–15s with audio.
- **Veo (fal)** — 17 rows: veo2, veo3.1 (+fast, first-last-frame, reference), 4/6/8s, 720p–4k, audio.
- **Happy Horse — FOUND.** fal `alibaba/happy-horse/*` (v1 + v1.1: T2V/I2V/R2V, 3–15s, 720p/1080p) + Kie `happyhorse/*` (6 rows). Not in any Adept list — awaiting review.
- **Runway — NOT FOUND on fal.** Zero live catalog rows. `fal_catalog.py:124` pins `fal-ai/runway-gen3/turbo/image-to-video` — **dead endpoint drift** (see §4).

## 2. Provider Catalog Sync utility (permanent)

- `studio-api/app/hosted_providers/catalog_contract.py` — canonical `CatalogVideoRow` (provider/family/model/endpoint/version/tier, mode flags t2v/i2v/r2v/firstFrame/lastFrame/references, duration min/max/enum, resolutions, audio, pricing, requestSchema, liveSubmit, reviewStatus) + the 4 frozen surface predicates.
- `catalog_sources/{wavespeed,fal,kie}_catalog_source.py` — reusable read-only fetch/parse modules (pure parsers unit-tested against fixtures, no network in tests).
- `catalog_sync.py` — `refresh_all()`: parallel per-provider fetch → normalize → diff vs stored → persist versioned `provider_catalog.json` (`updatedAt`, per-provider raw payloads, normalized rows, `reviewStatus`). New endpoints default `pending_review`; capability changes on approved rows set `providerChangedSinceReview`; removals only counted for providers that actually answered. Idempotent (live-proven: run 2 = 0/0/0).
- **Admin API** (verified live): `GET /api/hosted-providers/catalog?reviewStatus=pending_review`, `POST /api/hosted-providers/catalog/refresh` (77s full live refresh), `POST /api/hosted-providers/catalog/review/{row_id}` (approve/hide roundtrip verified). Approval only makes a row *eligible* for registry merge — never auto-exposed to creators.
- **UI:** `ProviderCatalogAdmin.tsx` inside Settings → Hosted Providers → **Advanced** `<details>` (developer chrome only, per creator-first law): refresh button, last-refresh time, per-provider counts, pending-review list with Approve/Hide.

### 2.1 Defect found by the hardened proof → repaired → revalidated (commit `8bb92af8`)

The hardened idempotency proof (reset store → refresh → refresh, asserting `new=0` on run 2) **failed on re-run**: run 2 discovered `new=2` because run 1 had silently produced a **partial Kie census** (66 rows instead of 68). Root cause: `docs.kie.ai` intermittently serves an HTML challenge/interstitial body with HTTP <400; `_fetch_page` counted those pages as `nospec` (legit prose) instead of `failed`, so the census looked complete. Repair: `_looks_bogus()` detects empty/HTML/challenge bodies (tight check — leading markup or challenge title in the first 4 KB, so prose pages with HTML snippets in examples are never misclassified), bogus bodies are retried like network errors (3 attempts), and a page that stays bogus is `failed` → `complete=False` → `catalog_sync` already refuses removals from an incomplete census and names the URL in `fetchFailures`. Regression: 3 new tests (pure `_looks_bogus` matrix; stubbed-transport retry-then-succeed; persistent-bogus marks incomplete). **Revalidated live:** full reset + double refresh → run 1 kie=68 (`unparsed=7`, only legit prose pages), run 2 `new=0, updated=0, removed=0`. Idempotent.

## 3. Canonical registry merge (Track C) — commit `88c8faa`

One source of truth now governs video-generator truth; the four drifting backend lists are derived views:

- **`app/hosted_providers/video_registry.py` (new)** — frozen `VideoGeneratorRegistration` + `CORE_VIDEO_REGISTRY` (17 rows: 9 local + 7 hosted + `runway` dead-endpoint inventory). Creator-surface views iterate core rows only; `catalog_registrations()` / `merged_registry()` lazily merge **approved** provider-catalog rows (review inventory — never auto-exposed, never in creator-surface views). Zero app imports at module level (no cycles — verified).
- **`video_readiness.py`** — `PRODUCT_ALIASES` / `PRODUCT_ADAPTER` / `LIVE_SUBMIT_ADAPTERS` / `HOSTED_LIVE_ONLY` / `SETUP_COMPONENTS` / `REQUIRED_NODES` replaced with registry views; derivation logic untouched.
- **`generator_authority.py`** — duplicate `PRODUCT_ALIASES` killed (re-export); `_ADAPTER_ONLY_IDS` / `CREATE_ENGINE_ROWS` derived; `_workflow_capabilities` now emits 4-surface records for hosted products with surface workflows (Kling/Veo/Runway honesty); Seedance output byte-identical.
- **`workflow_capabilities.py`** — `_LOCAL_WORKFLOW` derived; new hosted branch in `surface_workflow_status` placed after the untouched Seedance branch.
- **`model_registry.py`** — 16 video `_desc(...)` literals replaced with derivation in the same list positions; image/LLM rows untouched.
- **`tests/test_video_registry_parity.py` (new)** — 18 snapshot-parity tests: every derived view byte-identical to today's literal values, Seedance surface-status byte-identity, hosted-branch honesty, catalog-merge isolation (approved → `catalog_registrations()` only; pending never merges; creator views untouched).

**Primary verification (independently re-run, not just subagent-reported):** parity **18/18 PASS**; import sanity `imports OK`; consuming suites (`-k "readiness or generator_authority or workflow_capabilities or model_registry or fal"`) = **13 failed / 277 passed / 1 skipped / 30 collection errors — counts identical to the pre-change baseline** (all 13 failures reproduced on the reverted tree by the subagent; the 30 collection errors are pre-existing in-flight branch work, incl. an `IndentationError` in `codirector/routing/deterministic.py`). Disclosure: `video_readiness.py`, `generator_authority.py`, `workflow_capabilities.py` were previously **untracked** working-tree files (Sep 8–9 batch); commit `88c8faa` adds them to git for the first time, carrying that earlier work plus the refactor — their app-internal imports resolve to tracked modules or files in the same commit.

## 4. Drift findings (live truth vs pinned code)

1. **Three-way fal Kling disagreement:** `fal_catalog.py` pins `kling-video/v2.5-turbo/pro/image-to-video`; `models.py`/`discovery.py` say `fal-ai/kling-video/v3/pro/text-to-video`. Live catalog: **both exist** (v2.5-turbo and v3 families) — the registry now records per-mode endpoints from live truth.
2. **Runway dead endpoint:** `fal_catalog.py:124` `fal-ai/runway-gen3/turbo/image-to-video` — absent from the live fal catalog. `runway` product has no `model_registry` row and no live submit adapter; recorded `liveSubmit=False`.
3. **Kling/Veo Timeline stubs:** absent from `LIVE_SUBMIT_ADAPTERS` while `fal_catalog` builds full arguments — catalog rows record `liveSubmit` honestly (only the 6 live Seedance 2.0/2.5 fal endpoints are `liveSubmit=True`).
4. **Kie H3 duration drift:** Kie live = 4–15s @ 768P/2K; fal H3 Max = 5–15s @ 480P–1080P — two providers, two legal canvases for the "same" model family. Registry keeps them as distinct products (`minimax-h3` local remains its own gate).

## 5. Timeline UX root fixes (Track D)

### 5.1 Always-on preflight (event-driven, no polling)

New `studio-web/src/timelineMaster/useTimelinePreflight.ts`: `buildPreflightSignature(master, director)` projects exactly what backend `run_preflight` reads (batch generatorId / plannedDuration / promptSegments / references / sourceAnchors, `master.turboLora`, `master.sceneGeneratorId`, director camera/lipsync/prompt segments); 400ms debounce, single-flight + trailing rerun, stale-token guard, fail-open on error. Scene-open + signature change are the only triggers. Both Preflight buttons (toolbar + header) converge on the hook as "Re-check now"; the Generate gate and Inspector read the same state (repairs the divergence where the toolbar never updated `preflightBlockingCount`). **Required fix landed:** `ReferencesPane onChange` routed through `afterMutation()` so reference edits bump the signature. The expensive runtime-staging probe stays generate-time only.

### 5.2 H3 15-second root fix (all three layers)

- **Layer 1 (frontend seed):** `timelineSceneDuration.ts` — `isMinimaxH3Engine` now matches `"auto"`; blank/`auto`/`minimax-h3*` all seed **15.0** with `maxDurationSec` passthrough. (File was untracked → committed this mission, so the law survives clean checkout.)
- **Layer 2 (backend defaults chain):** `legal_canvas.seed_new_scene_duration_sec()`; `schemas.py SceneIn.duration_sec=None`; project creation (`routers/api.py`) seeds Scene 1 by engine law; `SceneService.create` seeds when the creator didn't choose; `AddBatchBody.plannedDuration=None` + `service.add_batch` seeds 15.0 for H3. **Explicit creator choice is never overridden**; `snap_h3_timeline_duration` still fails closed on empty input. Co-Director `create_scene` handler no longer hardcodes 5.0 (passes None → seed law fires). *Test-caught bug fixed this session: relative import in `service.add_batch` went beyond top-level package — the seeding path would have 500'd on first live use.*
- **Layer 3 (no write-back):** `FrameModes.tsx` 1F/FLF Generate persist canvas only — the snapped 17k+5 value is never written to `scene.duration_sec` (regression: Scene 7 held `7.291666666666667`). `extend_service.retake_extend_segment` persists the creator's **requested** duration for H3 (snap is request-scoped, disclosed at generation).

### 5.3 Library modal top Add button

`AddFromProjectLibraryModal.tsx` header now carries `data-testid="timeline-add-from-project-library-add-top"` — same `commit()`, same `disabled={selected.size === 0}`; double execution impossible (commit → onClose unmounts). CSS flex-wrap header actions; source-assertion regression in `trackFlags.test.ts`.

### 5.4 Frontend engine list derivation

`EngineAuthoritySelect.tsx` now treats the served registry (`GET /api/engines`) as authoritative for membership + order; newly approved registry engines appear with their server label without a frontend redeploy. Hard-coded list remains as offline fallback only. Byte-identical today (server list == hard-coded set).

## 6. Tests & evidence

| Suite | Result |
|---|---|
| `test_provider_catalog.py` (parsers, diff/review flags, liveSubmit truth, predicates, Kie bogus-body hardening) | **16/16 PASS** |
| `test_h3_timeline_duration.py` (snap grid, seed law, add_batch + SceneService + Co-Director seeding) | **12/12 PASS** |
| `test_timeline_extend.py` (incl. new H3 non-grid retake persists 7.0, never 7.2917) | **24/24 PASS** |
| Authority/readiness/catalog regression (`test_generator_authority`, `test_capabilities`, `test_readiness_contract`, `test_m210_readiness_baseline`, `test_seedance_version_authority` + catalog) | **92/92 PASS** |
| Web vitest: `timelineSceneDuration` (10), `useTimelinePreflight` (8), `frameModesDuration` (2), `trackFlags` top-Add assertion | **PASS** (trackFlags file also carries 2 pre-existing aspirational red tests — `TemperatureControl` doesn't exist even at HEAD; out of scope) |
| Registry parity (`test_video_registry_parity.py`) | **18/18 PASS** (independently re-run by primary) |
| Registry consuming suites (readiness / authority / capabilities / model_registry / fal) | **277 passed** — 13 failed + 30 collection errors **identical to pre-change baseline** (proven on reverted tree) |
| Live read-only refresh ×2 via HTTP | **PASS** — 459 rows, idempotent (`new=0, updated=0, removed=0` on run 2, after Kie bogus-body repair `8bb92af8`), zero generation calls |
| Web production build | **vite build GREEN (8.25s)**; `tsc -b` gate RED — **pre-existing**: 9 errors at committed HEAD, 121 in the working tree (Sep 9 uncommitted batch), **zero in mission files** (28-file error list cross-checked). Two minimal repairs landed to reduce pre-existing breakage (`types.ts` Health.comfy.probed, `ProjectEditor.tsx` missing import). |

## 7. Runtime / guardrail compliance

- **COMFY BEFORE:** healthy on :8188 · **COMFY AFTER:** healthy · **COMFY RESTARTED?: NO** (read-only `system_stats` observation only).
- Studio API recycled via smallest scope (listener PID stop + uvicorn start); `:8192` untouched; no supervisor restart.
- No paid generations, no inference, no model downloads. fal/Kie keys used for catalog/schema reads only.
- No new projects spawned; no creator-surface changes outside Settings → Advanced.

## 8. Known limitations / pre-existing issues (not mission-caused)

- `tsc -b` type gate red (see §6) — 28 files, all pre-existing; recommend a dedicated type-debt mission.
- `app/main.py:280` `ProposalService.persist_stale_non_terminal` AttributeError at API startup — pre-existing, non-fatal.
- 2 residual fal schema 404s (genuinely dead upstream schema endpoints; rows kept as `discovered`).
- 30 pytest collection errors + 13 consuming-suite failures across the wider backend tree — **identical at the pre-change baseline** (in-flight Sep 8–9 branch work, incl. an `IndentationError` in `codirector/routing/deterministic.py`); not mission-caused and not registry-caused (18/18 parity proves the derived views byte-identical).
- WaveSpeed rows require `wavespeed_api_key` (Setup Wizard) — source implemented and tested against fixtures.

## 9. Verdict

**GO — TIMELINE UX + PROVIDER VIDEO CATALOG VERIFIED**

All mandatory gates passed with observed evidence: 459-row live catalog (fal 391 / Kie 68 / WaveSpeed honest `Requires Setup`), idempotent sync revalidated after the Kie bogus-body repair, admin refresh/list/review API + Settings → Advanced UI live-verified, canonical registry merged with 18/18 byte-identical parity (independently re-run by primary) and baseline-identical consuming suites, H3 15-second law live-proven end-to-end on a disposable project, always-on event-driven preflight wired, Library modal top Add landed, all mission test suites green, `vite build` green. Known pre-existing issues are enumerated in §8 and are not mission-caused.
