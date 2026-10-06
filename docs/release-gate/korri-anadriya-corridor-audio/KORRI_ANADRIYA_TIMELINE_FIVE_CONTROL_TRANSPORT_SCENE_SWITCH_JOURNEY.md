# Timeline Five-Control Transport + Scene-Switch Stability Journey

Governing report for this mission addition. Persistence + Comfy ownership remains GO in `KORRI_ANADRIYA_TIMELINE_PERSISTENCE_COMFY_SINGLE_OWNER_JOURNEY.md`. The Venture Corridor audio/dialogue/footstep journey is not reopened.  
Amalgamated with the last three completed builds in [`ADEPT_UI_KORRI_ANADRIYA_LAST_THREE_BUILDS_UNIFIED_REPORT.md`](ADEPT_UI_KORRI_ANADRIYA_LAST_THREE_BUILDS_UNIFIED_REPORT.md).

**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `b6156455e643d5fa430784b3130756f2d8038651` (working tree includes this transport work; not committed unless requested)  
**Review URL:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline`  
**Shareable Walk URL:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline&sceneId=b5282a4c-07eb-40db-9d5b-1512eac74dca`  
**Shareable Scene 1 URL:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline&sceneId=1f46b621-46f9-4b7e-8273-202a49e1ca7c`  
**Studio API:** `http://127.0.0.1:8758/`

## Verdict

**GO — TIMELINE FULL SYSTEM SCENE-SWITCH STABILITY + SCENE MANAGEMENT + FIVE-CONTROL TRANSPORT + PLAYBACK JOURNEY E2E CERTIFIED**

Scene-card Rename / Remove addendum: `KORRI_ANADRIYA_TIMELINE_SCENE_MANAGEMENT_JOURNEY.md`.

## Live IDs

| Field | Value |
|---|---|
| PROJECT ID | `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` (Korri Anadriya) |
| SCENE 1 | `1f46b621-46f9-4b7e-8273-202a49e1ca7c` — 5 batches, board **25s** |
| VENTURE CORRIDOR WALK | `b5282a4c-07eb-40db-9d5b-1512eac74dca` — 1 batch, board **8s** |

No new project. No director overwrite. No batch add/remove on production scenes. No Comfy workflow change. No Comfy restart.

## Canonical timing authority

One board clock. Transport consumes it. It does not invent a second duration.

| Bound | Source | Scene 1 live | Walk live |
|---|---|---|---|
| `sceneStart` | First batch window start (`sceneStartTime`) | **0** | **0** |
| `sceneEnd` | `timelineBoardDurationSec` = sum of batch `plannedDuration` | **25** | **8** |
| `activeBatchStart` | Selected batch start, else playhead window (`batchInTime`) | selected Batch 3 → **10** | **0** |
| `activeBatchEnd` | Selected batch end, else playhead window (`batchOutTime`) | selected Batch 3 → **15** | **8** |

Rejected as Scene End:

- Generator maximum (LTX 2.3 **20s** in the header/dropdown)
- Scene record `duration_sec` (Scene 1 **20**)
- Selected batch end (**15** while Batch 3 is selected)

Live header on Scene 1: `LTX 2.3 — Local · 20s · Ready · 25.0 sec`. The **25.0 sec** is the board clock. Scene End seeks to **25**, not 20.

Commands share `resolveTimelineTransportBounds` → existing `seek()`:

- `seekSceneStart()`
- `seekBatchIn()`
- `togglePlayback()` (unchanged `useTimelineClock`)
- `seekBatchOut()`
- `seekSceneEnd()`

Seek while playing uses the existing clock: playhead updates, preview `data-playhead` follows, `useTimelineAudioPlayback` seeks any live layer whose drift exceeds 0.12s and pauses unused layers. Scene switch always `pause()` + `seek(0)` in `useLayoutEffect` before paint.

## Scene-switch stability

`TimelineEditorShell` does **not** remount when duration changes.

- Master / director caches are keyed by scene id.
- `liveMaster` / `liveDirector` only apply when they belong to the selected scene; otherwise the selected scene’s cache or `null` (board falls back to that scene’s `duration_sec` until hydrate).
- Director overlay on fetch uses **this scene’s** prior timeline, never the previous scene.
- `DirectorTracks` clears stale director chrome on scene id change and does **not** push a saved `director.playhead` into the shell clock (that yank was landing Scene 1 at 0.208s after seek(0)).

Playwright marked `timeline-editor-shell` and confirmed the marker survived 20 Scene 1 ↔ Walk switches.

## Transport cluster

Order: Scene Start · Batch In · Play/Pause · Batch Out · Scene End

Glyphs stay in the existing Timeline family (`|<<` `|<` `▶/⏸` `>|` `>>|`). Tooltips and aria-labels:

- Go to Scene Start
- Go to Batch In
- Play Timeline / Pause Timeline
- Go to Batch Out
- Go to Scene End

## Evidence

| Check | Result |
|---|---|
| Vitest `timelineTransport` + `timelineTransportAuthority` + duration/windows | **9 + 18 related passed** |
| Node `timelineHotkeys.test.ts` | **9 passed** |
| Playwright `tests/e2e/timeline/timeline-five-control-transport.spec.ts` | **1 passed (24.3s)** including 20-switch stress |
| Live browser Scene 1 | Five controls; Batch 3 In=10 Out=15; Scene End playhead **25**; preview **0:25 / 0:25** |
| Live browser Walk | Scene Start/In=0; Scene End/Out=8; playhead 0; no leftover Scene 1 audio |
| Studio API / Vite | `http://127.0.0.1:8758/api/healthz` 200; `http://127.0.0.1:5173/` 200 |

## E2E TRACE

| Stage | Verdict | Note |
|---|---|---|
| User action | PASS | Five transport clicks + scene drawer switch |
| Frontend | PASS | One transport cluster; no remount |
| API | PASS | Existing master + director GETs only |
| Backend | PASS | No new duration endpoint |
| Persistence | PASS | Scene id persist/URL from Journey 1 unchanged |
| Runtime | PASS | Clock + audio layers follow `seek()` |
| Result | PASS | Scene 1 end 25; Walk end 8 |
| Reload | PASS | Direct `sceneId` URL hydrates the matching scene |
| Downstream | PASS | Preview + playhead + audio stay on the same clock |

## COMFY

| | |
|---|---|
| COMFY BEFORE | PID **77152** / health 200 / `owned:true` |
| COMFY AFTER | PID **77152** / health 200 / `owned:true` |
| COMFY RESTARTED? | **NO** |
| WHY? | Ordinary Timeline UI/API work. `:8188` was read-only observation only. |

## NO-GO conditions (all cleared)

- Scene Start is not Batch In under another icon.
- Scene End is not Batch Out (Scene 1: 25 vs selected-batch 15).
- Scene End is not generator maximum (25 ≠ LTX 20).
- Scene switch does not keep the previous scene’s boundaries.
- Seek updates playhead, preview, and audio together.
- Five controls sit in the existing compact cluster; toolbar did not grow a new row.
- Transport consumes `timelineBoardDurationSec` / batch windows. No second duration authority.

## Limitations

- Production Korri scenes were not mutated (no live add/remove batch). Add/remove scene-end math is unit-tested.
- Draft scenes with zero batches are unit-tested (board falls back to director/scene seconds).
- Jacob snap-zoom suite was not re-run; Batch In/Out still call the same `seek()` with playhead windows when no batch is selected.
- Hosted Vercel is out of scope for this local Timeline journey.

## Manual review

1. Open `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline&sceneId=1f46b621-46f9-4b7e-8273-202a49e1ca7c`
2. Select Batch 3. Batch In → 10s. Batch Out → 15s. Scene Start → 0s. Scene End → 25s (not 20s).
3. Play from Scene Start, then switch to Venture Corridor Walk. Playhead 0, Scene End 8s, previous audio stopped.
4. On Walk, Scene Start and Batch In are both 0s; Scene End and Batch Out are both 8s. They remain five separate controls.
