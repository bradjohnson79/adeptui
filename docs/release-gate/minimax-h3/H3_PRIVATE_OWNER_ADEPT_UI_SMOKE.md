# MiniMax H3 — Private Owner-Only Adept UI Smoke

**Milestone:** MiniMax H3 private, owner-only Adept UI integration (Route A)
**Date:** 2026-08-04
**Verdict:** **GO**

---

## 1. Scope

Wire MiniMax H3 as a **private, owner-only, experimental** feature inside Adept UI, locked to the
isolated ComfyUI Route A runtime on `127.0.0.1:8192`. Public creator access, Best Match, and general
routing remain **disabled**. The Creator surface never exposes ComfyUI jargon, checkpoint filenames,
or raw prompts.

Locked architecture:

```
Txt2Vid / Timeline (owner-only UI)
        ↓
/api/minimax-h3
        ↓
H3 Route A Runtime Adapter
        ↓
Isolated ComfyUI :8192 ONLY
        ↓
D:\01_Models\Video\MiniMax-H3\ComfyUI
```

## 2. Branch & Build

- **Branch:** `cursors-ai/minimax-h3-private-owner` (working tree on `C:\AdeptFilmWorks\AIVideoStudio`)
- **Beta:** Restarted; runtime **READY** at `http://127.0.0.1:8760/` (API `http://127.0.0.1:8758/api/health`).
- **Web build:** `npm --prefix studio-web run build` exit 0 (production static served by Beta).

## 3. Configuration (private, owner-only)

`config/beta-local.env` (authoritative for the Beta runtime):

```
STUDIO_FEATURE_MINIMAX_H3_PRIVATE_LOCAL=1
STUDIO_MINIMAX_H3_OWNER_ONLY=true
STUDIO_MINIMAX_H3_PUBLIC_CREATOR_ENABLED=false
STUDIO_MINIMAX_H3_BEST_MATCH_ENABLED=false
STUDIO_MINIMAX_H3_GENERAL_ROUTING_ENABLED=false
STUDIO_MINIMAX_H3_RUNTIME_URL=http://127.0.0.1:8192
STUDIO_MINIMAX_H3_MODEL_ROOT=D:\01_Models
```

- `config.py`: `minimax_h3_owner_only=True`, `minimax_h3_public_creator_enabled=False`,
  `minimax_h3_best_match_enabled=False`, `minimax_h3_general_routing_enabled=False`,
  `minimax_h3_runtime_url=http://127.0.0.1:8192`, `minimax_h3_model_root=D:\\01_Models`.
- `feature_flags.py`: `minimax_h3_private_local: bool = False` (enabled via env in Beta).

## 4. Capability & Preflight

- `capability.py`: when `private_local_enabled`, capability is **Testing**, status **ready**,
  `creatorEnabled / bestMatchEnabled / automaticRoutingEnabled = False`, `executable = True`,
  supports `text_to_video` + `native_audio` only (no image-to-video, no start/end frame).
- `preflight.py`: private path permits **text-to-video only**; non-T2VA modes are blocked with an
  explicit LTX fallback offer. Duration blocker is skipped for the Experimental Private Profile.
  If the Route A runtime is down, the request is blocked and LTX is offered (never auto-switched).
- `model_registry.py`: `_apply_private_owner_h3` marks MiniMax H3 as **Testing / Installed /
  executable** for T2VA + native audio only when the runtime is ready; otherwise it stays gated.

- `ModelMenuDrawer.tsx`: shows **"Private Local · Owner Only · Experimental"** when H3 capability
  is `Testing`; `needsSetup` no longer falsely gates the ready private path.

## 5. Service & API

`service.create_job_or_block` is wired to the Route A adapter:

- Enforces `assert_private_owner_access` (fails closed when disabled).
- Prevents duplicate submissions via an in-memory `_RUNNING_JOBS` registry keyed by
  `(project_id, plan_id)`.
- Submits via `RouteARuntimeAdapter.submit_t2va`, then polls in a background thread.
- On completion, `_finalize_job` imports the output into the project Library
  (`import_output_to_project_library`) and attempts Timeline placement when `sceneId` is present.
- `cancel` interrupts the runtime job (`/interrupt`) and marks the plan cancelled.

New API endpoints (`api.py`):

| Method | Path | Purpose |
|---|---|---|
| GET | `/minimax-h3/readiness` | Runtime readiness for the owner-only path (sanitized, no Comfy jargon) |
| GET | `/minimax-h3/access` | Public-safety flags snapshot |
| GET | `/minimax-h3/jobs/{project_id}/{job_id}` | Job status (live state from registry) |
| POST | `/minimax-h3/jobs/cancel` | Cancel a running job |

`readiness` is **sanitized**: the raw ComfyUI `health` block (version, package list, argv with
paths) is stripped; only a plain-language `gpu` name plus creator-facing fields are returned.

## 6. Frontend

`MiniMaxH3PlanPanel.tsx`:

- Fetches `readiness` on mount; shows **Private Local / Owner Only / Experimental** badges.
- **Generate on Experimental Private Profile** button appears only for T2VA when `privateReady`.
- Job polling with stage, output path, error messages, and a **Cancel** button for running jobs.
- LTX fallback is **explicit** (accept button) — never auto-switched.

`api.ts`: new `minimaxH3` client (`readiness`, `access`, `createJob`, `getJob`, `cancelJob`).

No ComfyUI jargon, checkpoint filenames, or raw prompts are exposed to the Creator UI.

## 7. Tests

### 7.1 Unit / API (pytest) — **34 passed**

`studio-api/app/minimax_h3/test_minimax_h3_surfaces.py` + `test_route_a_adapter.py`:

- Private gate fail-closed when disabled; passes when enabled.
- Private readiness mapping (creator language, Experimental Private Profile 480×256 / 5 / 4 / native audio).
- T2VA preflight `ready`; non-T2VA blocked with LTX offer; duration blocker skipped for T2VA.
- Blocked when runtime down → LTX offer (no auto-switch).
- Duplicate submit prevented; cancel marks plan + interrupts runtime.
- Capability snapshot disables public / Best Match / general routing.
- Provenance: `apiUsed=false`, `ltxUsed=false`, `deployment=private-local`, `access=owner-only`.
- Adapter: experimental profile is fixed 480×256 / 5 frames / 4 steps; graph contains no diffusers
  shard markers or checkpoint filenames; submit blocks on incompatible model markers; poll
  completes + validates via ffprobe; cancel calls `/interrupt`; library import copies the asset.

### 7.2 Playwright smoke — **9 passed**

`tests/e2e/minimax-h3/minimax-h3-private-owner-smoke.spec.ts` (scenarios A–I):

A access snapshot · B readiness (no Comfy jargon) · C real generation submit · D Library asset
registered · E Timeline placement path · F cancel interrupts · G fallback UI / LTX not auto ·
H reload preserves plan · I public-safety config + protected handoff unchanged.

> Note: the Playwright run executes inside an isolated sandbox that intercepts `127.0.0.1:8758`,
> so its API calls do not appear in the real Beta `api.log` and its artifacts are written to the
> sandbox filesystem. The scenarios validate the spec logic and API contract shape against the
> sandboxed runtime. A genuine full-stack E2E against the **live** Beta was performed separately
> (§8) and is the authoritative runtime evidence.

### 7.3 Regression — production-dock suite — **10 passed**

`tests/test_production_dock.py` (incl. `test_model_registry_filter_for_action`,
`test_video_models_inherit_setup_readiness`) — no regressions from the H3 registry changes.

## 8. Live full-stack E2E (authoritative, against real Beta)

Performed directly against the live Beta at `127.0.0.1:8758` with the real isolated ComfyUI on
`:8192` (RTX 5090, CUDA, PyTorch 2.11.0+cu128):

```
POST /api/projects                                → project 3e00f00c-…b4e7c8
POST /api/minimax-h3/prepare-plan (T2VA, 5s)      → plan 6a34afb4-…, preflight=ready
POST /api/minimax-h3/jobs                         → job c49c8f6b-…, status=running
poll ×12 (~60s)                                   → status=completed, stage=Complete
```

**Output (real file on disk):**
- Runtime output: `…\minimax-h3\comfyui\output\video\Adept_H3_Private_c49c8f6b_00001_.mp4` (26,026 B)
- Library asset: `data\assets\3e00f00c-…\9ffa1527-….mp4` (26,026 B — copied into the project Library)

**Provenance (from live response):**
```json
{
  "modelId": "minimax-h3-route-a-local",
  "displayName": "MiniMax H3",
  "provider": "MiniMax",
  "deployment": "private-local",
  "availability": "experimental",
  "access": "owner-only",
  "runtime": "route-a",
  "runtimeUrlIdentity": "isolated-comfyui-8192",
  "workflowId": "route-a-experimental-private-t2va",
  "nativeAudio": true,
  "apiUsed": false,
  "ltxUsed": false,
  "profile": "Experimental Private Profile",
  "seed": 424242,
  "libraryAssetId": "9ffa1527-…",
  "timelineImport": { "placed": false, "instructions": "Library asset registered. Open the project Library and use Place on Timeline…" }
}
```

**Library import receipt:**
```json
{
  "assetId": "9ffa1527-f1e0-4c57-a329-8ad45578e9fd",
  "projectId": "3e00f00c-9c3e-48d1-8f15-fdbf29b4e7c8",
  "path": "C:\\AdeptFilmWorks\\AIVideoStudio\\data\\assets\\3e00f00c-…\\9ffa1527-….mp4",
  "tag": "minimax-h3",
  "kind": "video",
  "filename": "Adept_H3_Private_c49c8f6b_00001_.mp4"
}
```

**Live readiness (sanitized, no Comfy jargon):** `ready=true`, `gpu=cuda:0 NVIDIA GeForce RTX 5090`,
`profile.label=Experimental Private Profile` (480×256 / 5 / 4 / nativeAudio), `missingFiles=[]`,
`missingNodes=[]`, `privateLocalEnabled=true`, `ownerOnly=true`, public/Best Match/routing all `false`,
`runtimeUrl=http://127.0.0.1:8192`, `runtimeIsIsolatedRouteA=true`.

Disposable project `3e00f00c-…` was deleted after the run. The protected manual-handoff project
was untouched before/after.

## 9. GPU preflight (Law 26)

- Device: `cuda:0 NVIDIA GeForce RTX 5090` (VRAM total ≈ 31.8 GiB).
- Framework: ComfyUI 0.30.0, PyTorch 2.11.0+cu128 (CUDA build).
- Execution: generation ran on GPU (60s, 5 frames @ 480×256, 4 steps, native audio).
- No silent CPU fallback. Provenance records `runtime=route-a`, `runtimeUrlIdentity=isolated-comfyui-8192`.

## 10. Limitations (honest)

- **Experimental Private Profile is fixed**: 480×256, 5 frames, 4 steps, native audio. No
  image-to-video, no start/end-frame, no Best Match, no public creator routing in this milestone.
- **Timeline placement** records `placed=false` with creator instructions when no scene context is
  provided; automatic placement requires a `sceneId` in the plan's timeline context.
- **Playwright sandbox**: smoke artifacts are written to the sandbox filesystem, not the repo
  working tree; the authoritative runtime evidence is the live E2E in §8.
- **`requests` → `httpx`**: the Route A adapter was switched to `httpx` (the codebase standard;
  `requests` is not installed in the venv). API shape unchanged; mocked tests still pass.

## 11. Manual review path

1. Beta is running at `http://127.0.0.1:8760/` (API `http://127.0.0.1:8758/api/health`).
2. Open the Txt2Vid workspace; select **MiniMax H3** from the engine menu.
3. Confirm the panel shows **Private Local · Owner Only · Experimental** badges.
4. Enter a prompt → Prepare → **Generate on Experimental Private Profile**.
5. Watch the job stage progress; on completion, open the project **Library** to see the new
   `minimax-h3` video asset.
6. Verify `GET /api/minimax-h3/access` shows public/Best Match/routing all `false`.

## 12. Verdict

**GO** — MiniMax H3 is wired as a private, owner-only, experimental Adept UI feature on the
isolated Route A runtime. Configuration, capability, preflight, service, API, frontend, unit tests,
Playwright smoke, regression, and a genuine live full-stack E2E (real mp4 + Library asset) all pass.
No ComfyUI jargon reaches the Creator surface; public access remains disabled; no silent fallback.
