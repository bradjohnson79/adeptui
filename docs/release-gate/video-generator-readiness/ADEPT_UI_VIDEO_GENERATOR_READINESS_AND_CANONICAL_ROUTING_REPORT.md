# Adept UI — Video Generator Readiness and Canonical Routing

> **SUPERSEDED (2026-09-14) — generator contract.** This report governs its own
> August 2026 readiness milestone only. The canonical video generator contract
> is now: supported local = MiniMax H3 + LTX 2.5; supported API = Seedance /
> Kling / Veo / Runway; WAN, Hunyuan Video, and LTX 2.3 are RETIRED and removed
> from the active product. Current authority: `studio-api/app/hosted_providers/video_registry.py`
> and the Canonical Video Generator Cleanup final report. Do not cite this
> document's generator inventory as current truth (Law 30).

**Governing report** for this mission (Law 30). Do not cite older inventory dumps as current truth.

| Field | Value |
|---|---|
| Date | 2026-08-30 |
| Follow-up recorded | 2026-08-30T07:37Z (Playwright pass; Seedance job still running) |
| Branch | `feat/character-creator-final-closure` |
| HEAD | `b6156455e643d5fa430784b3130756f2d8038651` |
| Project | SenseNova Integration Lab `0ffe56e2-0d58-4926-91bf-0f947898d02e` |
| Scene | Jacob `f0b97b96-3456-4ceb-96ce-56bbece7e5b7` |
| Surface | CURRENT DEVELOPMENT — Vite `:5173` + Studio API `:8758` |
| Retired | `:8760` not used |

**Product law:** Ready is derived and proven. Everything else stays visible, disabled, with the exact reason.

## Verdict

`NO-GO — ADEPT UI VIDEO GENERATOR READINESS NOT YET CERTIFIED`

### Blockers

1. **seedance-fal Ready row is not E2E-complete.** Job `job_36ab9074dbee` / `seedance-api` submitted (`apiUsed=true`, `providerJobId=seedance_a3b2ab486450`) on Jacob `bb_0b02132dff80` and stayed `running` with progress 0 through a 7-minute poll. No candidate, no asset. Retry generate hit `BATCH_ALREADY_IN_FLIGHT`. Evidence: [`evidence/SEEDANCE_FAL_DRAFT.json`](evidence/SEEDANCE_FAL_DRAFT.json).
2. Peer Q1 FAIL stands. [Kimi K3](882fe6c1-f799-496e-befd-bd0284e5aff0) and [GLM 5.2](bdeb163e-70e8-4da8-9dc7-5f94b9fd901d) both **FAIL Q1** and **PASS Q2–Q5**. See [`KIMI_K3_REVIEW.md`](KIMI_K3_REVIEW.md) and [`GLM_52_REVIEW.md`](GLM_52_REVIEW.md).

Playwright readiness spec **passed** after the join-speed repair (1 passed, 22.1s). Studio API `:8758` healthz is **200**. Those are no longer blockers.

WAN is **not** a Ready-row blocker: it is Testing with the certified-graph mismatch. MiniMax is **not** a Ready-row blocker: Route A is Runtime Offline.

## What was already true (not rebuilt)

Canonical inventory remains Production Control `_CATALOG` plus hosted discovery. The join is `generator_authority` → `timeline_generator_snapshot` → `GET /api/director-timeline/generators` → `useTimelineVideoGenerators`.

No hosted WAN row was added. MiniMax duration was not changed. No `POST /api/projects`.

## Root-cause repairs (not label paint)

| Failure | Repair |
|---|---|
| Adapter `executable=True` painted Ready | `derive_video_readiness` is the only Ready gate. Adapter flag means “implementation exists.” |
| Video Setup was persisted | Live disk verify for video, same spirit as images. |
| Missing Runtime Offline | Added. MiniMax Route A down is Runtime Offline, not Checkpoint Missing. |
| LTX 2.5 and Kie/fal identity collapse | Aliases no longer map 2.5 → `ltx-local` or Kie/fal → `*-api` as products. Snapshot does not drop rows by alias. |
| LTX adapter labeled 2.5 | Label is **LTX 2.3 (Local)**. Product id `ltx-local`. |
| WAN / Hunyuan unwired | Real Timeline adapters added. Ready only if facts pass. WAN generate failed graph drift → Testing. Hunyuan stays Testing (uncertified / VRAM). |
| Seedance-kie → fal | `seedance-kie` has no adapter. Selecting it cannot call fal. |
| Dual GPU residency | If Desktop Comfy and Route A are both up, neither family is Ready (handoff required). |

Fact bundle lives in `studio-api/app/production_control/video_readiness.py`.

Normalized creator states: Ready · Requires Setup · Provider Not Configured · Runtime Offline · Testing · Unsupported.

`executable` / `selectable` = Ready only.

## Live matrix (measured 2026-08-30T07:09:08Z)

Evidence: `evidence/LIVE_READINESS_MATRIX.json` (07:09Z join snapshot kept; `followUp` records the failed Playwright + Seedance jobs). Comfy MCP: `evidence/COMFY_MCP.json` (ok, 39 tools). Desktop Comfy `:8188` up. Route A `:8192` down. WAN certified hashes were not rewritten. MiniMax duration was not changed.

| Generator | Canonical ID | Local/API | Installed/Configured | Adapter | Runtime | Workflow | Executable | UI State | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| LTX 2.3 | `ltx-local` | Local | Checkpoint present | `ltx-local` | Comfy `:8188` | `ltx.simple_i2v` / `ltx.scene` | Yes | Ready | Real I2V job `0a4473c0-00ff-4559-b97e-d101adfe2301` done |
| LTX 2.5 Full | `ltx-2.5-full` | Local | Variant files / INT8 path | `ltx-local` (binding only) | Comfy | Built, not certified | No | Testing | Uncertified; not Ready via 2.3 |
| LTX 2.5 Distilled | `ltx-2.5-distilled` | Local | Same | `ltx-local` | Comfy | Built, not certified | No | Testing | Same |
| LTX 2.5 Comfy | `ltx-2.5-comfy` | Local | Same | `ltx-local` | Comfy | Built, not certified | No | Testing | Same |
| WAN 2.2 | `wan-local` | Local | `wan_models` + WAN nodes | `wan-local` | Comfy | `wan.first_last_frame` **drift** | No | Testing | Job `25a584ca-…` WORKFLOW_GRAPH_DRIFT |
| Hunyuan 1.5 | `hunyuan-video-1.5-local` | Local | Weights + HyVideo* | `hunyuan-video-1.5-local` | Comfy | Built, not certified | No | Testing | Uncertified |
| Hunyuan 13B | `hunyuan-video-13b-local` | Local | 32 GB estimate vs 32 GB total | `hunyuan-video-13b-local` | Comfy | Built | No | Testing | `VRAM insufficient — needs ~32 GB, GPU has 32 GB` |
| MiniMax H3 T2V | `minimax-h3` | Local Route A | Weights on disk | `minimax-h3-t2v-local` | `:8192` down | Route A | No | Runtime Offline | Not Ready; no generate |
| MiniMax H3 I2V | `minimax-h3-i2v-local` | Local Route A | Same | `minimax-h3-i2v-local` | `:8192` down | Route A | No | Runtime Offline | Separate product row |
| Kling Kie | `kling-kie` | API | Key may be present | `kling-api` stub | — | — | No | Testing | Stub does not call Kie |
| Kling fal | `kling-fal` | API | fal key | `kling-api` stub | — | — | No | Testing | Stub does not call fal |
| Seedance fal | `seedance-fal` | API | fal key | `seedance-api` | fal | live submit | Join Ready | Ready in UI; E2E **not complete** | Job `job_36ab9074dbee` still `running` after 7 min; no asset |
| Seedance Kie | `seedance-kie` | API | — | **none** | — | — | No | Unsupported | Will not use fal |
| Veo fal / Kie | `veo-fal` / `veo-kie` | API | — | `veo-api` stub | — | — | No | Testing | Stub |
| optional-wan | `optional-wan` | — | — | none | — | — | No | Unsupported | Not a Timeline path |

Adapter-only IDs (`minimax-h3-t2v-local`, `kling-api`, `seedance-api`, `veo-api`) are not product rows.

## Surfaces

One hook: `useTimelineVideoGenerators`. `useVideoGeneratorOptions` is a thin wrapper over that join.

Wired: Video Generator dock, Inspector, toolbar (no raw adapter IDs), Footer `ModelMenuDrawer` (Ready only when `readiness === "Ready"`), `EngineAuthoritySelect` (engine tokens map to PC IDs), Co-Director product IDs, orchestrator preflight `GENERATOR_NOT_READY` + `disabledReason`.

Option line: `LTX 2.3 — Local · Ready` via `creatorGeneratorLine`.

## Tests (measured)

| Suite | Result |
|---|---|
| `studio-api/tests/test_generator_authority.py` + `test_production_dock.py` | **23 passed** (includes WAN drift, MiniMax Runtime Offline vs Checkpoint Missing, seedance-kie ≠ fal, adapter executable ≠ Ready) |
| Playwright `tests/e2e/timeline/timeline-video-generator-readiness.spec.ts` | **1 passed (22.1s)** after join-speed repair. Prior 30s GET timeout superseded. |
| Frontend Timeline generator tests | **11 passed** (`generatorDuration`, `draftCapabilities`, `timelineControlContract`) |
| Co-Director intent tests / M42 discovery | Failures observed earlier look pre-existing; not used as this gate |

## E2E TRACE

| Stage | Result |
|---|---|
| User action | PASS for LTX I2V on Jacob (generate clicked via API equivalent of Timeline generate) |
| Frontend | PASS Playwright 1 passed (22.1s) — dropdown matches join; only Ready enabled |
| API | PASS `:8758` healthz 200; generators 48 ms after fact-cache / fail-fast Route A / no double-apply |
| Backend | PASS authority join + preflight refuse non-Ready |
| Persistence | PASS LTX candidate on `bb_c1eb5212d68b`; WAN failure on `bb_0b02132dff80`; seedance job recorded, no candidate yet |
| Runtime | PASS LTX Comfy job; FAIL WAN graph drift; N/A MiniMax Route A down; seedance hosted job still `running` |
| Result | PASS LTX mp4 job done; FAIL WAN; seedance no asset yet |
| Reload | PASS earlier LTX candidate survived; WAN not Ready so no false success |
| Downstream | N/A Library/Timeline approve not required for this honesty gate |

## GPU

Desktop Comfy owns the RTX 5090 for LTX. Route A was not started (admission: cannot both be Ready). No silent CPU fallback. WAN job failed before GPU work on graph drift.

## Runtime (2026-08-30T07:37Z)

API-only recycle was attempted; Comfy was not stopped. `:8188` is occupied by Desktop Comfy Python PID **69724** (external occupier — not adopted, not killed). Studio API listens as PID **48380** (`uvicorn app.main:app --host 127.0.0.1 --port 8758`).

| Surface | Result |
|---|---|
| Creator UI `http://127.0.0.1:5173/` | HTTP 200 |
| Studio API `http://127.0.0.1:8758/api/healthz` | HTTP 200 |
| Desktop Comfy `http://127.0.0.1:8188/` | HTTP 200 — PID 69724 unchanged |
| Route A `:8192` | down (not started) |
| Retired `:8760` | not used |

**COMFY BEFORE PID:** 69724  
**COMFY AFTER PID:** 69724  
**COMFY RESTARTED?:** **NO**  
**WHY?:** Join/API work only. Guardrails forbid restarting `:8188` for this mission.

## Peers

| Reviewer | Q1 Ready E2E | Q2 mislabel | Q3 substitution | Q4 one authority | Q5 root-cause | Overall |
|---|---|---|---|---|---|---|
| [Kimi K3](882fe6c1-f799-496e-befd-bd0284e5aff0) | FAIL | PASS | PASS | PASS | PASS | READY FOR PRIMARY REVIEW — agrees NO-GO |
| [GLM 5.2](bdeb163e-70e8-4da8-9dc7-5f94b9fd901d) | FAIL | PASS | PASS | PASS | PASS | agrees NO-GO |

One FAIL keeps the gate open.

## Remaining to close GO

1. Wait for `job_36ab9074dbee` to produce a Seedance asset **or** demote `seedance-fal` from Ready until a completed cheap draft exists.
2. Leave `:5173` and `:8758` running. Do not restart Comfy PID 69724.

## Files (this mission)

- `studio-api/app/production_control/video_readiness.py` (new fact authority)
- `studio-api/app/production_control/generator_authority.py`
- `studio-api/app/production_control/model_registry.py` (MiniMax I2V row; live video setup)
- Timeline adapters: `wan_local.py`, `hunyuan_local.py`, `ltx_local.py` label, `seedance_api.py` aliases
- `studio-web` Timeline/Footer/toolbar/EngineAuthoritySelect/hooks
- `studio-api/tests/test_generator_authority.py`
- `tests/e2e/timeline/timeline-video-generator-readiness.spec.ts`
- `docs/release-gate/video-generator-readiness/KIMI_K3_REVIEW.md` (recorded; not rewritten this follow-up)
- `docs/release-gate/video-generator-readiness/GLM_52_REVIEW.md` (recorded; not rewritten this follow-up)
- `docs/release-gate/video-generator-readiness/evidence/SEEDANCE_FAL_DRAFT.json`
- `docs/release-gate/video-generator-readiness/evidence/PLAYWRIGHT_VIDEO_GENERATOR_READINESS.json`
- `docs/release-gate/video-generator-readiness/evidence/RUNTIME_PROBE.json`
- `docs/release-gate/video-generator-readiness/evidence/FAMILY_GENERATES.json`
- `docs/release-gate/video-generator-readiness/evidence/LIVE_READINESS_MATRIX.json` (07:09Z snapshot kept; `followUp` added)
