# Timeline Preflight — Always Available / Always Online

**Governing document for this gate.**

| Field | Value |
| --- | --- |
| Date | 2026-09-16 |
| Branch | `feat/character-creator-final-closure` |
| HEAD (committed baseline) | `99665cf76693e359cedc60c50c4405daf1b4e3a1` |
| Project | Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Cert scene | Disposable `Preflight Always Available Cert` (created and deleted by Playwright; Scene 1 / 12B / Walk untouched as the cert vehicle) |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |

## Verdict

**GO — TIMELINE PREFLIGHT ALWAYS AVAILABLE RESTORE**

Unanimous three-LLM AGREE after one refresh-path repair. Preflight is a persistent Timeline control. It runs the existing director `run_preflight` plus Co-Director `upsert_scene_readiness` path. Production Readiness is not a second engine.

## Root cause

1. **Two existing systems were disconnected.** Timeline `useTimelinePreflight` already called `GET /api/director-timeline/projects/{id}/scenes/{id}/preflight` → `orchestrator.run_preflight` (generator / prompt / batch / continuity). Co-Director Production Readiness (Cast / Location / References / Voice) lived on `upsert_scene_readiness` / `scene_production_package` and was only written from chat/API scene lifecycle, never from Timeline Preflight.
2. **Production Readiness was Scene-Advanced-only.** Selecting a Batch, clip, Timed Prompt, or Scene hid the panel. The copy said “run Co-Director Preflight” with no Run action on that surface.
3. **Header/toolbar labels said Recheck.** The control existed but did not present as Preflight. DirectorTracks still had a leftover alert-only Preflight (hidden on Timeline v2).
4. **Header/toolbar/auto-preflight did not refresh the context package.** Inspector click did. After reconnect, a first-pass browser walk still showed “not assessed” until Production Readiness listened for the shared hook leaving `checking`.

## Architecture (reconnect, not rebuild)

- **Director findings** — existing `orchestrator.run_preflight` on GET `/preflight`
- **Production Readiness write** — `assess_scene_readiness_from_project` → `upsert_scene_readiness` only
- **Production Readiness read** — existing Timeline context package (`useTimelineContextPackage`)
- **Invoke** — existing `useTimelinePreflight.recheckNow` (header, toolbar, Inspector)
- **Always mounted** — `SceneProductionReadinessPanel` immediately after the Inspector eyebrow, before Scene / Batch / clip branches
- **Offline** — `preflightStatus === "error"` shows `timeline-preflight-offline`; the Preflight button stays

Unassessed copy is allowed only next to a visible Preflight button. UI rewrites “run Co-Director Preflight” to “run Preflight”. Backend unassessed string now matches.

## Implementation

- `assess_scene_readiness_from_project` derives Cast / Location / References / Voice / generation-plan flags from wiki, character profiles, scene references, and the scene row, then calls `upsert_scene_readiness`.
- GET `/preflight` returns `{ ok, findings, productionReadiness, mock: false }`. Assess exceptions do not drop findings.
- Inspector, header (`timeline-header-preflight`), and toolbar (`timeline-toolbar-preflight`) labels are **Preflight**.
- Help catalog title is **Preflight** (not “Co-Director Preflight”).
- Panel refreshes the context package when shared preflight status leaves `checking` (`ready` / `blocked` / `error`), so header, toolbar, auto-preflight, and Inspector all update Production Readiness.
- Alert-only DirectorTracks Preflight is gone.

## Tests

| Suite | Result |
| --- | --- |
| pytest `studio-api/tests/test_timeline_preflight_production_readiness.py` | **2 passed** |
| Vitest `TimelineInspector.preflight` + `TimelineToolbar.preflight` + `useTimelinePreflight` | **3 files, 16 passed** |
| Playwright `tests/e2e/timeline/timeline-preflight-always-available.spec.ts` live `:5173` / `:8758`, `ADEPT_ALLOW_KORRI_MUTATION=1` | **1 passed** (7.9s first; 5.5s after refresh repair) |

## Peer LLM review

Question (verbatim): Is Preflight restored as a persistent, live Timeline capability — always visible and callable whenever Timeline is open, independent of Batch/Take/clip/generation/Co-Director chat/Production Readiness BLOCKED — that runs the existing director preflight + Co-Director upsert_scene_readiness path (no duplicate readiness engine), refreshes Production Readiness immediately, survives selection switch and reload, and shows an offline/error state instead of hiding the control?

| Reviewer | First pass | After context-package refresh repair |
| --- | --- | --- |
| Kimi K3 Max | AGREE | **AGREE** |
| GLM 5.2 Max | AGREE | **AGREE** |
| GPT-5.6 Sol | AGREE | **AGREE** |

Unanimous **AGREE**.

## E2E TRACE

| Step | Result |
| --- | --- |
| User action — open Timeline on Korri; Preflight in header, toolbar, Inspector | PASS |
| Frontend — click Inspector Preflight; no Co-Director chat required | PASS |
| API — GET `/scenes/{id}/preflight` returns `findings` + `productionReadiness` | PASS |
| Backend — `run_preflight` + `assess_scene_readiness_from_project` → `upsert_scene_readiness` | PASS |
| Persistence — lifecycle package no longer `error == "Scene not found"` | PASS |
| Runtime — no GPU generate; Comfy untouched | N/A (readiness only) |
| Result — Production Readiness domains + director findings refresh | PASS |
| Reload — header + Inspector Preflight still visible | PASS |
| Downstream — Batch selection keeps Preflight + Production Readiness mounted | PASS |

Live browser (Korri Scene 1 after HMR): header / toolbar / Inspector all **Preflight**; after shared check settled, Production Readiness showed Status READY, Cast / Location / References / Voice Ready, plus generator and prompt/batch findings. Selecting Batch 1 kept Inspector Preflight and Cast (7).

## Runtime / Comfy

| Check | Result |
| --- | --- |
| COMFY BEFORE | PID **34484** / `GET :8188/system_stats` **200** |
| COMFY AFTER | PID **34484** / `GET :8188/system_stats` **200** |
| COMFY RESTARTED? | **NO** |
| WHY? | Studio API recycle only (`restart_studio_api_only.py`); Vite HMR for UI |
| Studio API | `http://127.0.0.1:8758/api/healthz` **200** (PID 40368 → 45912 → 6748) |
| Creator UI | `http://127.0.0.1:5173/` **200** |

## Limitations

- Auto-preflight still uses the existing signature debounce; the first context-package fetch can briefly show unassessed until the shared check settles and the panel refreshes. The Preflight button is visible during that window.
- Assess writes a lifecycle row for the open scene. Playwright uses a disposable scene. Manual review of Scene 1 may show an already-assessed READY row from this restore.
- Non-English `timeline.json` `preflightTitle` strings were not rewritten (product default is `en`).
- Working tree still contains unrelated uncommitted work from other missions. This gate certifies the Preflight restore only.

## Manual review

1. Open `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline`
2. Confirm **Preflight** in the Timeline header and toolbar immediately (no Batch, Take, or Visual clip required).
3. Open the Inspector → Production Readiness with a **Preflight** button above Scene / Batch fields.
4. Click Preflight → Cast / Location / References / Voice / generator / prompt-batch update without opening Co-Director chat.
5. Select a Batch, a Timed Prompt, then the Scene → Preflight remains.
6. Reload → Preflight remains.
7. Do not restart Comfy.
