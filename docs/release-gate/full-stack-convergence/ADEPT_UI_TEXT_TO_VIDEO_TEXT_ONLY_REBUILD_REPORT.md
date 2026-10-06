# Adept UI — Text to Video Text-Only Rebuild — Unified Completion Report

**Journey:** Rebuild Text to Video into a true text-only creator surface.
**Branch:** (current working tree, uncommitted — accumulated across the CREATE-convergence journey)
**Date:** 2026-09-03
**Verdict:** **GO — FULL-STACK E2E VERIFIED** (text-only contract proven; real fal_seedance T2V video generated → Library → survived reload)

---

## 1. Creator intent

Text to Video means exactly `TEXT → VIDEO`:

- No image references, character sheets, environment sheets, prop sheets, start frame, or inherited project image references.
- The References panel does not belong on this surface and has been **removed** (UI + state + backend compile boundary).
- AUTO selects only a genuinely executable T2V path. Local LTX/WAN/Hunyuan/MiniMax-H3 are Reference/Image-to-Video and are **excluded** from the true T2V path (disabled in the dropdown with the honest reason).
- No silent fal/Kie. No I2V/R2V fallback. No start-frame requirement. Paid hosted T2V requires explicit owner approval.

---

## 2. Scope of changes (this journey)

### Frontend

**`studio-web/src/components/Txt2VidPanel.tsx`** — rewritten as a clean text-only surface:
- Removed `ReferencesPane`, `SpatialReferenceFieldset`, `MiniMaxH3PlanPanel` imports and usage.
- Removed all spatial state and `sceneReferenceProvenance` preflight.
- `queueTxt2Vid` now submits a **clean text-only payload** (prompt, negative, style, aspect, fps, duration_sec, engine, width, height, resolution, `providerPreference: "fal"`, `paidFallbackApproved`). No reference/spatial/start-frame IDs.
- `generate()` resolves the effective T2V engine (AUTO → first executable T2V, never local I2V). If none → honest blocker (`txt2vid-message`), no submit. If a paid fal T2V engine → `PaidFalFallbackDialog` for explicit approval; on approve → submit clean payload with `paidFallbackApproved: true`.
- Dynamic, honest subtitle (reflects whether an executable T2V engine is connected).
- `EngineAuthoritySelect` with `requireTextToVideo` (local R2V engines disabled).
- Kept `PromptIntelligencePanel` (text-only, compact disclosure).

**`studio-web/src/components/PaidFalFallbackDialog.tsx`** — repurposed for paid T2V approval:
- Removed the I2V `generate_local_start_frame` action.
- Only `approve_paid_fal` and `cancel` actions remain. Title/message reflect paid Text-to-Video approval.

### Backend

**`studio-api/app/queue_worker.py` (`_txt2vid`)** — hardened to text-only:
- Defensively strips all reference/image/spatial/start-frame params at the top (`spatialMapId`, `spatialReferenceBundle`, `sceneReferenceProvenance`, `start_asset_id`, `source_asset_id`, `reference_asset_ids`, …).
- Removed the spatial-reference compile block and the spatial-reference upload to fal.ai.
- `image_url=None`, `end_image_url=None` → routes `fal_seedance` to its true text-to-video endpoint (`bytedance/seedance-2.0/text-to-video`); leaves Kling/Veo/Runway text-only.
- `s.start_asset_id = None` → AUTO resolution is never influenced by a start frame.
- `history_json` no longer records spatial fields.

**`studio-api/app/codirector/production_intent/execute.py` (`_enqueue_standalone_video`)** — closed the Co-Director leak:
- Removed the injection of `start_asset_id`/`source_asset_id` from `intent.sourceAssets` into `txt2vid` jobs. Standalone Co-Director T2V is text-only; image-conditioning belongs to `render_scene` / 1 Frame / 3 Frame.

### Tests

**`tests/e2e/m30h-local-first/no-silent-fal-fallback.spec.ts`** — rewritten for the text-only contract:
- "Generate never silently submits fal — blocker or paid-approval dialog only" (route-intercept: 0 POSTs to `/txt2vid` without approval; no `generate-local-start-frame`).
- "Txt2Vid surface is text-only — no References panel or Attach Asset controls" (no `scene-references-pane`, `references-attach-form`, `videospatial-reference`).
- "Txt2Vid submit payload carries only text + generation settings (no reference IDs)" (intercepts + captures the body, asserts no forbidden reference/spatial/start-frame keys; aborts so no paid submit).

**`tests/e2e/minimax-h3/minimax-h3-adept-ui-surface-cert.spec.ts`** — test B repurposed:
- "B — Text2Video honestly excludes MiniMax H3 (R2V/I2V, not true T2V)" — asserts the `minimax-h3` option is **disabled** on T2V and the H3 plan panel is absent. Also made the `openTxt2Vid` helper robust (wait for the canonical `?workspace=txt2vid` deep link instead of a racy immediate check + invalid `?workspace=video` fallback).

**`tests/e2e/final-systems/helpers/finalSystemsCert.ts`** — `openTxt2VidH3` guards `selectOption("minimax-h3")` (only when enabled) so it cannot hang on the disabled option.

**`tests/e2e/graduation/adept-ui-dramatic-scene-graduation.spec.ts`** — guards the H3 `selectOption` (only when enabled) so it cannot hang.

---

## 3. Generator honesty (classification)

| Generator | True T2V? | T2V-surface status |
|---|---|---|
| `fal_seedance` | Yes (text-to-video endpoint) | Executable when `fal_api_key` configured; paid approval required |
| `fal_kling` / `fal_veo` / `fal_runway` | Yes (text-only mode) | Available when configured; paid approval required |
| `minimax-h3` | No (R2V/I2V) | **Disabled** on T2V — "use 1 Frame or 3 Frame" |
| `ltx` / `wan` (local) | No (R2V/I2V) | **Disabled** on T2V — "use 1 Frame or 3 Frame" |
| `hunyuan` | No (R2V) | Not offered on T2V |

At runtime during this session: `fal_api_key` **configured = True** → `fal_seedance` is a genuine executable T2V engine. AUTO resolves to it. Local R2V engines are disabled.

---

## 4. Live proof — Korri Anadriya (`beffd3d8-791d-4adf-9c4d-681ec9d4efb0`)

Surface: `http://127.0.0.1:5173/project/beffd3d8-…?workspace=txt2vid`

| # | Proof point | Result |
|---|---|---|
| 1 | No References panel exists | **PASS** — `scene-references-pane` absent |
| 2 | No inherited character/environment images | **PASS** — no reference images rendered |
| 3 | No Attach Asset controls | **PASS** — `references-attach-form`, `ref-attach-submit`, `videospatial-reference` absent |
| 4 | Creator enters only text + generation settings | **PASS** — Prompt, Generator, Duration, Aspect, Resolution, FPS, Style, History, Negative |
| 5 | Generate inspects only real executable T2V engines | **PASS** — local R2V disabled; `fal_seedance` executable |
| 6 | Request payload has no unintended image/reference IDs | **PASS** — Playwright captured submit body; no forbidden keys (proven) |
| 7 | Real T2V engine executable → generate a real video | **PASS** — `fal_seedance` job `d1eb0965…` → "Txt2Vid complete" (fal in progress → done) |
| 8 | Result reaches project Library and survives reload | **PASS** — asset `d053a527…` (`kind=video`, `txt2vid_45bde8fe_fal.mp4`, 2,394,952 bytes on disk); visible as `video txt2vid bytedance` in Library after reload (Filter: Video) |
| 9 | If no engine executable → exact honest blocker | **N/A** (engine executable); blocker path verified by code + Playwright (fires when no executable T2V) |

### E2E TRACE

- **User action:** Creator enters prompt + generation settings, clicks **Generate Video** → **Approve paid fal.ai submission**.
- **Frontend:** `Txt2VidPanel.generate()` → `resolveEffectiveEngine()` → `fal_seedance` (executable) → `PaidFalFallbackDialog` → approve → `queueTxt2Vid({ engine: "fal_seedance", paidFallbackApproved: true })`.
- **API:** `POST /api/projects/{id}/txt2vid` → clean text-only payload (no reference IDs).
- **Backend:** `_txt2vid` strips any reference params → `s.start_asset_id=None` → `is_fal_engine` branch → `assert_fal_allowed` (paid approved) → `build_fal_arguments(image_url=None)` → `bytedance/seedance-2.0/text-to-video`.
- **Runtime/Provider:** fal.ai `fal_seedance` text-to-video → video generated.
- **Result:** job `done` → asset `d053a527…` registered (`kind=video`, mp4 on disk).
- **Library/Hydration:** asset appears in project Library.
- **Reload:** navigated away to `?workspace=library` → asset `video txt2vid bytedance` still present (Filter: Video). **Persistence survives reload.**
- **Downstream:** Promote bar available (Add to Director as Scene / Start / Middle / End / Profiles / Open Timeline).

---

## 5. Tests run

| Suite | Result |
|---|---|
| `tests/e2e/m30h-local-first/no-silent-fal-fallback.spec.ts` (3 tests) | **3 passed** |
| `tests/e2e/minimax-h3/minimax-h3-adept-ui-surface-cert.spec.ts` test B | **1 passed** |
| `tests/e2e/final-systems/remaining-workspaces.spec.ts` | **1 passed** |
| `tests/e2e/home/explore-core-creation-workspaces.spec.ts` | **1 passed** |
| `studio-web` vitest `draftCapabilities.test.ts` (8 tests, module used by new panel) | **8 passed** |
| `studio-web` full vitest suite | 917 passed / 38 failed — **all 38 failures are pre-existing in unrelated files** (voice studio, scriptwriter, scene-creator-mini, etc.); none in `Txt2VidPanel`/`PaidFalFallbackDialog`/`draftCapabilities`/`EngineAuthoritySelect`/`useTimelineVideoGenerators`. No new failures introduced by this journey. |

---

## 6. Runtime / ComfyUI Protection Law

- **COMFY BEFORE:** PID 19500, healthy (`:8188/system_stats` 200).
- **COMFY AFTER:** PID 19500, healthy (unchanged).
- **COMFY RESTARTED?:** **NO.**
- **WHY?:** Ordinary UI + API-only work. Backend changes picked up by recycling **Studio API only** (`scripts/restart_studio_api_only.py`: old PID 20880 → new PID 29940). No supervisor bounce, no Comfy/MiniMax lifecycle action.
- MiniMax `:8192` not started (owner approval not given; H3 offline — correctly excluded from T2V).

---

## 7. Fences honored

- One project, one Library: the T2V video was generated into the **Korri Anadriya** project Library (no disposable multi-project spam).
- Comfy `:8188` leave-alone: PID unchanged throughout.
- No supervisor bounce.
- No mocks: real fal_seedance cloud generation, real mp4 on disk.
- No silent I2V/R2V fallback: local R2V engines disabled; no start-frame path.
- No silent fal: explicit paid-approval dialog; cancel = no submit (proven).
- No paid hosted generation without owner approval: owner approved exactly one paid `fal_seedance` clip via explicit question; the Playwright payload test aborts before any submit.
- MiniMax `:8192` not started without owner approval.

---

## 8. Co-Director routing

- `m29/providers.py` already distinguishes `image_to_video` (→ `render_scene`, requires scene frames) from `text_to_video` (→ `txt2vid` job, `scene_id` may be `None`, no reference asset IDs).
- `_enqueue_standalone_video` leak closed: `start_asset_id`/`source_asset_id` no longer injected into `txt2vid` jobs from `intent.sourceAssets`.
- Result: "Create a video from this text" → Text to Video; "Animate this image" → 1 Frame / I2V; "Use these references" → Timeline R2V. A text-only video request is not routed into a reference/image workflow.

---

## 9. Known limitations / out-of-scope (honest)

- **Pre-existing `tsc -b` typecheck failures** in the working tree (voice studio, `useStudioHealth`, `ProjectEditor` missing `coDirectorProjectPath` import, `useTimelineVideoGenerators` ModelDescriptor index signature). These are from prior uncommitted work, **not** introduced by this journey; my T2V files are type-clean. The Vite dev server (esbuild) runs the app for the live/Playwright proof. A clean production `tsc -b` build remains blocked by these pre-existing errors and is out of scope for the T2V text-only rebuild.
- **Pre-existing `coDirectorProjectPath` import dropped** in `ProjectEditor.tsx` (prior uncommitted change) — latent runtime bug for the standalone bible-workspace path only; not exercised by T2V. Not fixed (out of scope).
- **Pre-existing vitest failures (38)** in unrelated modules — not introduced by this journey.
- **Independent GPT-5.4 peer review not run:** Law #27 specifies `gpt-5.4-medium` for subagents, but that model is not available in this environment's Task-tool model list. Per tool guidance, no substitute model was used; the primary agent performed the second-pass review. A truly independent peer review can be run when `gpt-5.4-medium` is available.
- **Paid E2E limited to one clip:** Owner approved exactly one `fal_seedance` clip for the live proof. Repeatable full E2E requires owner approval per run (fence honored).

---

## 10. Manual review

- Local creator UI: `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=txt2vid`
- Studio API: `http://127.0.0.1:8758/api/healthz`
- Comfy (read-only): `http://127.0.0.1:8188/system_stats` (PID 19500, leave-alone)
- To reproduce: open Text to Video, enter a prompt, click Generate → Approve paid fal.ai submission (fal configured) → wait for the video → check Library (Filter: Video) → reload → asset persists.

---

## 11. Verdict

**GO — ADEPT UI TEXT TO VIDEO TEXT-ONLY REBUILD VERIFIED (FULL-STACK E2E PASSED).**

Text to Video is a clean text-only surface. The creator provides text and video-generation settings only. No project image references or reference sheets leak into the request. No start frame is requested. AUTO chooses only real executable T2V capability (`fal_seedance`). The result either generates honestly and persists (proven: real fal video → Library → survived reload), or reports the exact runtime/provider blocker without changing modes. Co-Director routes text-only video to T2V (not I2V/R2V). Comfy `:8188` was left alone throughout.

**REMAINING (out of scope, pre-existing):** clean `tsc -b` production build blocked by prior uncommitted typecheck errors; independent GPT-5.4 peer review pending model availability.
