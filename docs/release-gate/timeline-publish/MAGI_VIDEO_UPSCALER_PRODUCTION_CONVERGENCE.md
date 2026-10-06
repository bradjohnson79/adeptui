# MAGI Video Upscaler Production Convergence

**Law 2 / Law 30 governing report** for MAGI full-scene Timeline upscale.  
Supersedes [`READY_FOR_PRIMARY_REVIEW.md`](READY_FOR_PRIMARY_REVIEW.md) for target gating, job-completion persist, Library fail-closed, and live Scene 12B proof. That file remains historical for Timeline Publish chrome and Venture Corridor Dialogue Playwright A–E.

| Field | Value |
|---|---|
| Date | 2026-09-13 (PT) / 2026-09-14 (UTC) |
| Branch | `feat/character-creator-final-closure` |
| HEAD SHA | `99665cf76693e359cedc60c50c4405daf1b4e3a1` |
| Working tree | Convergence changes uncommitted (not committed unless asked) |
| Project | **Korri Anadriya** (`beffd3d8-791d-4adf-9c4d-681ec9d4efb0`) — reused, no new project |
| Scene | **12B — Quarters Interview** (`d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`) |
| Creator UI | http://127.0.0.1:5173/ |
| Studio API | http://127.0.0.1:8758/ |
| Live Timeline | http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline&sceneId=d774a22f-2b02-4eb2-b5ab-a98af9ff8f85 |
| Evidence | `.runtime/_magi_upscale_12b_cert.json`, `docs/release-gate/timeline-publish/artifacts/magi-upscale-12b-reload.png` |

Product law: Timeline produces and verifies the full assembled scene. MAGI enhances that master as a **derivative**. The original stitch / published master stays on disk. The creator chooses whether the enhanced file becomes the Published Master. **No auto-publish.**

Honesty: **spatial frame enhancement only — not temporal AI restoration.**

---

## Verdict

**GO — MAGI FULL-SCENE VIDEO UPSCALER VERIFIED FOR TIMELINE**

---

## Individual verdicts

| Gate | Status |
|---|---|
| MAGI VIDEO UPSCALER ENGINE | **PASS** — FFmpeg Fast + Real-ESRGAN-ncnn-Vulkan (existing inventory) |
| REALESRGAN READY | **PASS** — `realesrganReady: true`; preferred model `realesr-animevideov3` already on disk |
| FFMPEG FULL-SCENE APPLY | **PASS** — Pass A on ~30s published master |
| REALESRGAN FULL-SCENE APPLY | **PASS** — Pass B, 720 frames, ~187s |
| FULL MULTI-BATCH MASTER INPUT | **PASS** — 2-batch stitch `9170c85b-…` → published master `a85c2632-…` |
| AUDIO PRESERVED | **PASS** — AAC in/out; GPU remux uses `apad` + duration lock, no `-shortest` |
| FPS PRESERVED | **PASS** — 23.99 fps in/out |
| DURATION PRESERVED | **PASS** — FFmpeg Δ 1.7 ms; GPU Δ 40 ms (timebase, not clip) |
| A/V SYNC PRESERVED | **PASS** — audio start 0; duration/fps match; no silent channel drop |
| SOURCE MASTER PRESERVED | **PASS** — sha256 `2b517495cd85e3c8e8fc42869e88c519f56c6e0d83a5d68b2572907852cac78d` unchanged after A/B/C |
| DERIVATIVE ASSET CREATED | **PASS** — new files, parent = published master |
| LIBRARY REGISTRATION VERIFIED | **PASS** — `tag=magi_upscale`, `video.generated`; assign failure now fails the MAGI job |
| TIMELINE → MAGI HANDOFF | **PASS** — Preview Monitor chooser + poll; optional `?workspace=magi&sceneId=&assetId=` uses existing `importTimelineAsset` |
| `scenePublish.upscaledAssetId` PERSISTED | **PASS** — written on **job completion**, not enqueue |
| RELOAD VERIFIED | **PASS** — GET master + remounted Timeline still show `c51066df-a383-483e-a98d-a42e916e90c7` |
| PUBLISH-UPSCALE LINEAGE VERIFIED | **PASS** — parent lineage + `preferredPublishSource` → `upscaled`; Update Published shown; **not** auto-published |
| NO COMFY DEPENDENCY INTRODUCED | **PASS** — Comfy unused; `:8188` read-only |

---

## Live Scene 12B

Source published master `a85c2632-dd04-4450-be5d-214aa191e209`: **864×480**, 30.048 s, 23.99 fps, **720** frames, AAC, 2.82 MB.

Same-resolution target `864x480` refused: HTTP **400** `TARGET_NOT_ABOVE_SOURCE`.

Legal options: 1080p / 1440p / 4K / 8K. Default target **1080p**. Default engine **Real-ESRGAN GPU** when ready.

### Pass A — FFmpeg apply — PASS

| | |
|---|---|
| Job | `030a28ec-8a2b-4cf6-b8d6-1e14b4daa2f9` (~3.27 s) |
| POST | `upscaledAssetId: null`, `autoPublished: false` |
| Derived | `902cfaf7-b88b-4e5f-8e20-e832635a4797` → `upscale_0ef7819864.mp4` |
| Out | 1920×1080, 30.050 s, AAC, parent = published master, Library row |
| Frames | 721 vs source 720 (~1 frame container slop; duration matched) |

### Pass B — Real-ESRGAN — PASS

| | |
|---|---|
| Job | `af2b2145-b2e0-4d7f-9224-827df64ba1f8` (~187 s) |
| Engine | `realesrgan-ncnn-vulkan` / `realesr-animevideov3` |
| Derived | `b84516c6-4710-451e-b6a0-c20026e9573e` → `upscale_acfb631a4d.mp4` (15.6 MB) |
| Out | 1920×1080, 30.008 s, **720** frames, AAC, source hash unchanged |
| Persist | `upscaledAssetId` updated to GPU derivative; published id unchanged |

### Pass C — Preview Monitor + reload — PASS

Chooser opened from **UPSCALE WITH MAGI**. Creator path: **FFmpeg Fast** + **1440p** + Start. UI polled the `magi_upscale` job (did not treat POST 200 as done). Chooser closed after success.

| | |
|---|---|
| Job | `b7170941-7d5f-4d50-bbb2-3d5e5341f9f8` — `preview: false`, `persistScenePublish: true` |
| Derived | `c51066df-a383-483e-a98d-a42e916e90c7` → `upscale_0635505dca.mp4` (13.5 MB) |
| Out | **2560×1440**, 30.050 s, 721 frames, AAC, parent = `a85c2632-…` |
| Library | `tag=magi_upscale`, `Project/Video/Generated` |
| After remount | Preview Monitor shows **Changes Pending** + **Update Published** + **Upscale with MAGI** |
| GET master | `upscaledAssetId=c51066df-…`, `upscalePendingPublish=true`, `publishedAssetId` still `a85c2632-…` |

Reload proof is backend master-store hydration, not React state.

---

## E2E TRACE

| Hop | Result |
|---|---|
| User action | PASS — UPSCALE WITH MAGI → engine/target → Start |
| Frontend | PASS — `MagiUpscaleChooser` + `pollMagiUpscaleJob` |
| API | PASS — `POST .../magi-upscale` enqueue; `GET .../jobs/{id}` until done |
| Backend | PASS — FFmpeg / Real-ESRGAN apply; persist only on job completion |
| Persistence | PASS — `scenePublish.upscaledAssetId` + Library row |
| Runtime | PASS — local MAGI engines; Comfy not used |
| Result | PASS — derivative above source; audio/fps/duration intact |
| Reload | PASS — id survives remount + GET master |
| Downstream | PASS — Update Published available; `source: "upscaled"` when creator publishes; no auto-publish |

---

## What was reconnected (not rebuilt)

1. Shared target gate — `studio-api/app/magi/upscale_targets.py` + FE `magiUpscaleTargets.ts`. Only presets **strictly above** source. Empty target = first legal preset (1080p source defaults to 1440p).
2. Timeline Preview Monitor chooser — Real-ESRGAN GPU default when ready; FFmpeg never labeled AI. Poll job; never treat enqueue as finished.
3. Persist `upscaledAssetId` on `run_upscale_job` when `persistScenePublish=true`. Draft `scenePublish` with empty `publishedAssetId` allowed before first Publish.
4. Library `assign_asset` fail-closed for `tag=magi_upscale` / `op=upscale`.
5. GPU remux: removed `-shortest`; `-af apad` + `-t {assembled_duration}` (video clock is authority).
6. Publish / Update Published send `source: "upscaled"` when a derivative id exists.
7. Optional Open in MAGI uses existing `api.magi.importTimelineAsset`.

---

## Tests

| Suite | Result |
|---|---|
| pytest `test_upscale_targets` + `test_magi_upscale_convergence` + `test_scene_publish` + `test_magi_upscaling` | **36 passed** |
| vitest `magiUpscaleTargets` + `pollMagiUpscaleJob` + `scenePublish` | **15 passed** |
| Playwright `tests/e2e/timeline/timeline-publish-magi-cert.spec.ts` | Updated (POST `upscaledAssetId` is null; persist asserted after job). **Not re-run this session.** Uses Venture Corridor Dialogue only — never Scene 12B. |

Unit coverage: 1080→1080 rejected; 1080→1440 ok; enqueue does not persist; job completion does; Library assign failure fails MAGI job; preview cannot set `persistScenePublish`; first publish can use `source=upscaled`.

---

## COMFYUI PROTECTION LAW

| | |
|---|---|
| COMFY BEFORE | PID **45624**, `GET http://127.0.0.1:8188/system_stats` 200 |
| COMFY AFTER | PID **45624**, `GET /system_stats` 200 |
| COMFY RESTARTED? | **NO** |
| WHY? | Ordinary MAGI/Timeline work. `:8188` read-only. Vite `:5173` was restarted after it died mid-reload. Studio API stayed on `:8758`. |

---

## How to review

1. Confirm http://127.0.0.1:8758/api/healthz and http://127.0.0.1:5173/ return 200.
2. Open Scene 12B Timeline URL above.
3. Confirm Preview Monitor: Changes Pending, Update Published, Upscale with MAGI.
4. Open Upscale with MAGI: honesty line, current master 864×480, legal targets only, GPU default when ready.
5. Do **not** click Update Published unless you intend to replace the Adept Chronicles Published Master with the 1440p MAGI derivative.
6. Original published file hash must remain `2b517495cd85e3c8e8fc42869e88c519f56c6e0d83a5d68b2572907852cac78d` until an explicit Update Published.

---

## Limitations

- Vite `:5173` died once during Pass C remount; restarted Vite only. Comfy and Studio API were not recycled for that recover.
- Playwright VCD MAGI cert spec was updated and not re-run here. Live proof is Scene 12B API + browser, not that spec.
- Update Published was **not** clicked on Adept Chronicles (no auto-publish; would replace published v1). Lineage + chrome + unit tests prove the wire.
- FFmpeg apply can report one extra container frame (721 vs 720) with duration still matching.
- GPU remux duration 30.008 vs 30.048 s is timebase, not `-shortest` clipping.
- Spatial enhancement only. Flicker / temporal restoration is out of scope and not claimed.
- No new upscaler, Comfy graph, or SeedVR2. No model downloads.

---

## Out of scope (untouched)

Timeline generation, multi-batch continuity logic, Final Check, Re-Take, Dialogue Authority, Co-Director production, Character Creator, Spatial/3D shelf. MAGI preview (`preview=true`, 3 s silent) stays separate from Timeline apply.

---

## Checklist

```text
[x] Branch + HEAD SHA recorded
[x] Contracts: publishedAssetId may be empty; upscalePendingPublish added
[x] Full-stack hops wired (chooser → job → persist → Library → reload)
[x] Visible UPSCALE WITH MAGI control polls to completion
[x] Real FFmpeg + Real-ESRGAN runtimes; no mock completion
[x] Persistence after reload verified
[x] Same-or-lower target refused
[x] Library assign fail-closed for MAGI upscale
[x] Unit tests 36 + 15 passed
[x] Playwright spec updated (not re-run)
[x] Beta UI at :5173; API at :8758
[x] Evidence JSON + reload screenshot
[x] Limitations honest
[x] Comfy untouched (PID 45624)
[x] Verdict: GO
```
