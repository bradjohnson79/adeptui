# Timeline Video Generator + Library + Zoom Regression Restoration

**Date:** 2026-08-30
**Branch:** `feat/character-creator-final-closure`
**HEAD:** `b6156455e643d5fa430784b3130756f2d8038651` (working tree; not committed)
**Governing document:** this file (Law 30). Do not treat the owner screenshot as a new Timeline design.

**Live URLs left running:**
- Creator UI: http://127.0.0.1:5173/
- Studio API: http://127.0.0.1:8758/
- Retired `:8760` is not product UI.

**Project reused (no `POST /api/projects`):** SenseNova Integration Lab `0ffe56e2-0d58-4926-91bf-0f947898d02e` / Scene `f0b97b96-3456-4ceb-96ce-56bbece7e5b7`.

---

## Verdict

**GO — TIMELINE VIDEO GENERATOR + LIBRARY PICKER + 0.2×–5× ZOOM REGRESSION RESTORED E2E**

Class: newer `TimelineEditorShell` omitted / overwrote certified wiring. Canonical modules were remounted in place. No `TimelineV3`, `DrawerNew`, `Zoom2`, or `LibraryPicker2`.

**Addendum (this pass):** centered Batch transport `|<` `▶/⏸` `>|` is on the same toolbar, driven by the existing `playheadSec` clock. No second Timeline timebase.

---

## Peer review (owner override of Law 27)

Independent remount-vs-parallel review after live Playwright was green.

| Reviewer | Verdict | Gate items | Result |
| --- | --- | --- | --- |
| [Kimi K3](2e370ac1-0e03-4675-8550-718e38be2549) | **REMOUNT** | all six **PASS** | READY FOR PRIMARY REVIEW |
| [GLM 5.2](60b801b6-1d85-49bb-941f-b6a5f6c2ecff) | **REMOUNT** | all six **PASS** | READY FOR PRIMARY REVIEW |

Both peers independently confirmed remount-in-place:

- Video Generator dock sits above Scenes; persist is `applyTimelineSceneGenerator` → `api.directorTimelinePutMaster`
- Library modal + `library_asset_ids` + scoped thumbs
- `timelineZoom.ts` 0.2–5 with `boardWidth = pixelsPerSecond(zoom) * boardDuration`
- `magneticSnapMovingEdge` on pointerdown; Snap testid present
- no hardcoded MiniMax 15 / 5 / 0.21 in the live dock path
- zero `TimelineV3` / `DrawerNew` / `Zoom2` / `LibraryPicker2`
- leftover `[0.5, 3]` in Scene Creator cinematographer is camera-lens math, not Timeline zoom

Kimi noted it did not re-run Playwright (accepted the measured 7/7 from this mission). Zero FAILs. Gate stays closed.

### Transport addendum peer review (same Kimi K3 + GLM 5.2)

Mandatory question: does transport use the existing Timeline clock/playhead, or a second timing authority? A second clock blocks the gate.

| Reviewer | Clock authority | Items 1–6 | Blocking second clock | Result |
| --- | --- | --- | --- | --- |
| [Kimi K3](fb75d36c-af52-4c4d-a421-6bb101d1ad75) | **EXISTING playheadSec** | all six **PASS** | **NO** | READY FOR PRIMARY REVIEW |
| [GLM 5.2](3c7392d0-a30e-4709-a678-cb3a848a30d2) | **EXISTING playheadSec** | all six **PASS** | **NO** | READY FOR PRIMARY REVIEW |

Both peers independently found reuse, not a second clock:

- `useTimelineClock` rAF / `seek` write only `setPlayheadSec`
- `playing` is a boolean, not a timebase
- `LivePreviewMonitor` pauses video and ignores `onTimeUpdate` while Timeline plays
- Batch In/Out use half-open `[start, end)` from `plannedDuration` / `order`, not a hardcoded 5
- Scene end is `timelineBoardDurationSec`
- no `transportPlayhead2` / `previewPlaybackState` / floating transport bar

Zero FAILs. The second-clock blocker does not fire. The addendum stays inside the restoration GO.

---

## What was restored

### Video Generator

- Remounted existing `VideoGeneratorDock` **above** Scenes in the left drawer (`data-testid="timeline-video-generator"`).
- One inventory: `useTimelineVideoGenerators` → Production Control + Timeline join. No new picker / hardcoded engine list.
- Shared persist path `applyTimelineSceneGenerator`: `sceneGeneratorId` + every batch `generatorId` + duration from the existing capability join (`generatorMaxDurationSec`). Inspector Generation uses the same path.
- Missing client method was the persist hole: added `api.directorTimelinePutMaster` (`PUT …/master` body `{ master }`). Dock and Inspector now surface apply errors instead of swallowing them.
- Header meta restored: `data-testid="timeline-scene-header-meta"` with `creatorGeneratorLine` + board duration.
- MiniMax duration was **not** redefined. Live join currently shows MiniMax H3 as `Local · 0.2s`. That number is the join’s `maxDurationSec`, not a new dock constant. Route A was not modified.

### Library

- Backend: `library_asset_ids` restored on `DirectorTimeline` (staging only).
- Frontend type + `mutateTimeline` persist.
- Timeline Library dock: **Library** button `data-testid="timeline-library-open"` opens existing `AddFromProjectLibraryModal`.
- Modal lists `api.library(project.id, { scope: "project" })` (paged so older project media is reachable), image/audio/video filters, multi-select, Add, X/backdrop = close with no write.
- Pane lists only staged IDs. Thumbs: `api.assetUrl(id, null, project.id)`. Shell calls `bindAssetUrlProject(project.id)`.
- i18n: `addFromProjectLibrary`, `libraryAdd`. Modal CSS already in `timeline-v2-shell.css`.

### Zoom (one authority)

- All live Timeline clamps/slider/buttons/wheel use `clampTimelineZoom` / `stepTimelineZoom` / `zoomToSlider` / `sliderToZoom` from `timelineZoom.ts` (0.2–5 log).
- Slider: `min=0 max=1 step=0.001`.
- `boardWidth = pixelsPerSecond(zoom) * boardDuration`. Removed the `Math.max(480, …)` floor and `min-width: 100%` stretch that made 0.2× lie about pixels-per-second (broke snap math).
- Lane width is a CSS variable so the label gutter is outside the timed scale.

### Magnetic snap

- `TrackClipInteractive` uses `magneticSnapMovingEdge` + `buildMagneticSnapTargets`. Listeners attach **on pointerdown** (`dragRef`) so Playwright’s synchronous pointer sequence is received.
- Toolbar Snap: `data-testid="timeline-toolbar-snap"`.
- Batch buttons expose `data-start` / `data-length`.

### Header chrome testids restored (smoke)

- `timeline-viewer-guides`, `timeline-mode-image-planning`, `timeline-mode-video-finishing`, `timeline-header-resume`.
- Resume accessible name: re-queue of cancelled or failed work (not mid-frame resume).

### Batch transport (toolbar center, one clock)

- Existing `playheadSec` in `TimelineEditorShell` remains the only Timeline time. `useTimelineClock` is a rAF driver of that state (`seek` / `setPlayheadSec`). No `transportPlayhead2`, no `previewPlaybackState`.
- Preview Monitor receives the same `playheadSec`. While Timeline is playing, `LivePreviewMonitor` pauses the `<video>` and ignores `onTimeUpdate` playhead writes so native media cannot start a second clock.
- Batch In/Out use `batchWindows.ts` — same cumulative `order` + `plannedDuration` half-open `[start, end)` as `resolveBatchAtTime`. Exact boundary stays on that Batch’s start. Out clamps to `timelineBoardDurationSec`. Duration is not hardcoded to 5.
- One Play/Pause `<button>` on the existing toolbar (3-column grid: add controls | transport | undo/zoom/snap). Not a floating bar.
- Play continues across Batch boundaries until Pause, Scene end, or another explicit transport action. At Scene end: stop, ▶, playhead stays at end. Play at Scene end restarts from 0. In/Out while playing seek the same playhead and keep the same rAF session.
- Space is rebound to Play / Pause Timeline (header “Pause Viewer updates” stays a separate overlay control). Home / End → Batch In / Out.
- `data-playhead` on `#timeline-playhead` and the Preview Monitor is Timeline seconds, not pixels.

---

## Tests

### Live Playwright (authoritative)

```
ADEPT_BETA_TARGET=1
ADEPT_ALLOW_KORRI_MUTATION=1
STUDIO_API_BASE=http://127.0.0.1:8758
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173
npx playwright test tests/e2e/timeline/timeline-master-snap-zoom-generator.spec.ts --project=chromium
```

**8 passed, 0 failed, 0 skipped** (50.7s, chromium) after the transport addendum. Earlier restoration run was **7 passed**.

| Case | Result |
| --- | --- |
| Video Generator above Scenes; LTX from join persists; reload | PASS |
| Library button → modal → multi-select → Add → pane IDs; X adds none; reload | PASS |
| Header duration matches Jacob board (15.0 sec), not a stale scene clock | PASS |
| Zoom slider 0 / 0.5 / 1 → 0.20× / 1.00× / 5.00×; −Z / +Z; clip times unchanged | PASS |
| Snap ON at 0.2× / 1× / 5× acquires Batch edge; Snap OFF free position | PASS |
| Safe visible controls wired; no generate started | PASS |
| Resume accessible name mentions re-queue of cancelled or failed work | PASS |
| Batch transport: In/Out from Batch windows; Play/Pause one button; Scene end; In/Out while playing; 0.2× and 5× | PASS |

Generator test restores master + scene engine/duration in `finally` so SenseNova is not left on LTX. Observed after run: `sceneGeneratorId=minimax-h3`; batches MiniMax / MiniMax / Platform Integrity LTX I2V (original third-batch identity).

### Unit (supporting)

Zoom / magnetic / control contract tests passed. Added source contracts for remount, PUT master client, board-width formula, and pointerdown magnet listeners.

Transport unit: `batchWindows.test.ts` **4 passed**; `timelineTransportAuthority.test.ts` **1 passed** (no second clock symbols; one Play button). Hotkeys `node --test timelineHotkeys.test.ts` **9 passed**.

Pre-existing `trackFlags.test.ts` source-contract misses (`onControlToggle`, `TemperatureControl`, toolbar `timelineActionError`) were **not** weakened and are outside this mission’s binary line.

`test_library_asset_ids_round_trip_dump` passed earlier. `test_library_asset_ids_not_generation_input` still fails on a pre-existing `build_timeline_generation_request(..., scene_prompt=)` TypeError — not weakened.

---

## Browser smoke (live `:5173`)

Opened SenseNova Timeline. Observed:

- `TimelineEditorShell` live route
- Video Generator above Scenes; select shows MiniMax H3 — Local · 0.2s (join, not a hardcoded dock max)
- Header: `MiniMax H3 — Local · 0.2s · 15.0 sec · Video Finishing`
- Library button present
- References dock present
- Scene Prompt, Timed Prompt, Camera tracks
- Inspector Generation bound to the same join
- Snap ON, zoom slider at 1.00×
- Generate / Approve / Re-take / Preview present
- Preview Monitor showed an existing take (`0:04 / 0:04`) — **no new GPU job started**
- Centered toolbar transport `|<` `▶` `>|` between add controls and Undo/Zoom/Snap
- Live Go to In from ~11s → playhead **10** and Preview `data-playhead` **10** (Batch 3 start). Accessible names: Go to Batch In / Play Timeline / Go to Batch Out.

---

## E2E TRACE

| Stage | Video Generator | Library | Zoom | Snap | Transport |
| --- | --- | --- | --- | --- | --- |
| User action | PASS — dock select LTX | PASS — Library → cards → Add | PASS — slider 0 / 1 and −Z / +Z | PASS — drag Timed Prompt toward Batch edge | PASS — `|<` `▶/⏸` `>|` |
| Frontend | PASS — `VideoGeneratorDock` / Inspector | PASS — modal + staged pane | PASS — `timelineZoom` helpers | PASS — `TrackClipInteractive` + magnet | PASS — `useTimelineClock` writes `playheadSec` |
| API | PASS — PUT master `{ master }` | PASS — PUT director `library_asset_ids` | N/A — client layout | PASS — PUT director clip start | N/A — local clock |
| Backend | PASS — `replace_master` | PASS — `library_asset_ids` on `DirectorTimeline` | N/A | PASS — director persist | N/A |
| Persistence | PASS — `sceneGeneratorId` + batch ids | PASS — staged ids survive reload | PASS — zoom does not rewrite clip seconds | PASS — snapped start persisted then restored | N/A — playhead is session UI state |
| Runtime | N/A — no generate | N/A | N/A | N/A | N/A — no new GPU job |
| Result | PASS — select value `ltx-local` | PASS — `asset-library-item-*` | PASS — `0.20×` / `5.00×` / `data-zoom` | PASS — start ≈ batch edge at 0.2 / 1 / 5 | PASS — In/Out = Batch seconds; Play advances; Pause holds; Scene end stops |
| Reload | PASS | PASS | PASS — times unchanged | PASS — director restored in `finally` | N/A |
| Downstream | PASS — header/join line | PASS — pane lists only staged ids | PASS — pixels scale, not clip seconds | PASS — Snap OFF free position | PASS — Preview `data-playhead` matches Timeline |

---

## Files (this restoration)

- `studio-web/src/components/timeline-master/TimelineEditorShell.tsx`
- `studio-web/src/components/timeline-master/VideoGeneratorDock.tsx`
- `studio-web/src/components/timeline-master/AddFromProjectLibraryModal.tsx`
- `studio-web/src/components/timeline-master/TimelineInspector.tsx`
- `studio-web/src/components/timeline-master/TimelineToolbar.tsx`
- `studio-web/src/components/timeline-master/TrackClipInteractive.tsx`
- `studio-web/src/components/AssetTray.tsx`
- `studio-web/src/components/DirectorTracks.tsx`
- `studio-web/src/components/DirectorSelectionContext.tsx`
- `studio-web/src/timelineMaster/applySceneGenerator.ts`
- `studio-web/src/timelineMaster/draftCapabilities.ts`
- `studio-web/src/timelineMaster/workspaceLayout.ts`
- `studio-web/src/timelineMaster/timelineZoom.ts` (authority; not rewritten)
- `studio-web/src/timelineMaster/magneticSnap.ts` (authority; not rewritten)
- `studio-web/src/timelineMaster/trackFlags.test.ts`
- `studio-web/src/timelineMaster/batchWindows.ts`
- `studio-web/src/timelineMaster/batchWindows.test.ts`
- `studio-web/src/timelineMaster/useTimelineClock.ts`
- `studio-web/src/timelineMaster/timelineTransportAuthority.test.ts`
- `studio-web/src/timelineMaster/timelineHotkeys.ts`
- `studio-web/src/timelineMaster/helpCatalog.ts`
- `studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx`
- `studio-web/src/components/LivePreviewMonitor.tsx`
- `studio-web/src/api.ts`
- `studio-web/src/i18n/locales/en/timeline.json`
- `studio-web/src/styles/timeline-master/timeline-editor-shell.css`
- `studio-web/src/styles/timeline-master/timeline-v2-canvas.css`
- `studio-api/app/director_timeline.py`
- `tests/e2e/timeline/timeline-master-snap-zoom-generator.spec.ts`

---

## Limitations (honest, not blockers for this mission)

- MiniMax H3 long-form / up-to-15s capability remains **Platform Integrity Closure**. This mission only consumes the current join (`0.2s` on the live dock).
- Apply-all-batches generator write is the certified persist path; the Playwright generator case restores the original master afterward.
- Pre-existing unit/source-contract drift in `trackFlags.test.ts` and `test_library_asset_ids_not_generation_input` was not part of this binary line.
- Working tree is dirty with unrelated in-progress work. This mission was **not committed**.

---

## Manual review

1. Open http://127.0.0.1:5173/project/0ffe56e2-0d58-4926-91bf-0f947898d02e?workspace=timeline&scene=f0b97b96-3456-4ceb-96ce-56bbece7e5b7
2. Left drawer: Video Generator above Scenes, then Library, then References.
3. Library button opens the project picker; Add stages IDs only.
4. Zoom slider left end `0.20×`, right end `5.00×`. Snap ON pulls a Timed Prompt to a Batch edge.
5. Center transport: `|<` jumps to the current Batch start, `>|` to that Batch end (clamped to Scene end), `▶`/`⏸` plays and pauses the same playhead the Preview Monitor follows.

**GO — TIMELINE VIDEO GENERATOR + LIBRARY PICKER + 0.2×–5× ZOOM REGRESSION RESTORED E2E**
