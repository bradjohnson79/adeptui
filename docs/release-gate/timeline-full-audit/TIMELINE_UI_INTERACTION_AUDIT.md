# Timeline UI Interaction Audit

- **Date:** 2026-08-07
- **Auditor:** Read-only code auditor (subagent)
- **Scope:** Code-level review of Timeline UI in `studio-web/src/components/timeline-master/` (`TimelineMasterPanel`, `TimelineEditorShell`, `TrackClipInteractive`, `TimelineWorkspaceStack`, `TimelineInpaintWorkspace`, `TimelineInspector`, `TimelineToolbar`, `TimelinePreviewComposer`, `CompactRenderQueue`, `SceneStatusStrip`, `TimelineGeneratorBanner`, `TimelineRetakeDrawer`) plus `studio-web/src/components/DirectorTracks.tsx` and `LivePreviewMonitor.tsx`. Method: read code only; no servers/tests run. Every finding cites `file:line`. Items needing visual confirmation marked **needs runtime verification**. Prior reports not trusted; current code read directly.

---

## Per-area verdict table

| # | Area | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Duration/timing display precision | **DEFECT** | `TimelineMasterPanel.tsx:258,266,268,271` raw floats; `TimelineInspector.tsx:758,839,840` raw floats in inputs. Good: `TrackClipInteractive.tsx:158` (`toFixed(2)`), `DirectorTracks.tsx:1535-1536` (`toFixed(1)`), `TimelineEditorShell.tsx:527` (`toFixed(1)`). |
| 2 | Clipped labels / overflow | **OK (caveat)** | `styles.css:1158,1168,1269-1278` ellipsis + `min-width:0`. Batch clip inner `<strong>`/`<span>` inherit `.track-clip span` ellipsis. **Needs runtime verification** for very short batches at high zoom-out. |
| 3 | Batch lane readability + selected clarity | **OK** | `DirectorTracks.tsx:1472` `active` class; `styles.css:498-501` teal outline; `data-testid="timeline-batch-${batch.id}"` present (`:1471`). **Needs runtime verification** for contrast at small widths. |
| 4 | Preview error presentation | **DEFECT (minor)** | `LivePreviewMonitor.tsx:447-453` failed overlay exists; **no cancelled overlay** despite `monitorState="cancelled"` (`:158`) and composer `{kind:"cancelled"}` (`TimelinePreviewComposer.tsx:190`). |
| 5 | Inspector consistency | **DEFECT (minor)** | Same source (`master.batchBlocks`), but `TimelineInspector.tsx:830` renders `Status: {selectedBatch.status}` raw while `TimelineMasterPanel.tsx:11-15,255` humanizes via `statusHint()`. |
| 6 | Queue linkage visibility | **DEFECT (minor)** | `CompactRenderQueue.tsx:71-76` shows raw truncated `batchBlockId` (not label). No Generating/Queued badge on batch clip (`DirectorTracks.tsx:1466-1481`). |
| 7 | Control states + disabled reasons | **DEFECT (minor)** | Most disabled buttons only `disabled={busy}` with no reason (`TimelineMasterPanel.tsx:138,159,177,191,205,284,298,312,324`). Model: `TimelineToolbar.tsx:480-492` Inpaint (`title={inpaintTitle}`). No dead controls found. |
| 8 | 100+ batch virtualization | **DEFECT** | `DirectorTracks.tsx:1449-1482` windowing is playhead/selection-centered, **not scroll-aware**. `WIN=80` mounts up to 80 nodes. No `react-window`/`react-virtual`. **Needs runtime verification** of scroll-mismatch. |
| 9 | Network/API noise | **DEFECT (minor)** | 2.5s loops: `TimelinePreviewComposer.tsx:118`, `LivePreviewMonitor.tsx:205`; 3s: `CompactRenderQueue.tsx:28`. None gate on visibility; no backoff. `DirectorTracks.tsx:486-504` N parallel `getTimelineReferences` per `tl` change. |

---

## Defect details

### D1 — Raw float duration renders in `TimelineMasterPanel` (HIGH, creator-facing)

**Root cause:** `batch.duration.plannedDuration` / `generatedDuration` / `timelineVisibleDuration` are floats interpolated directly into JSX.

**File:line:**
- `studio-web/src/components/timeline-master/TimelineMasterPanel.tsx:258` — collapsed meta: `{batch.duration.plannedDuration}s · …` → e.g. `5.004000000000001s`.
- `studio-web/src/components/timeline-master/TimelineMasterPanel.tsx:266` — `Planned {batch.duration.plannedDuration}s`.
- `studio-web/src/components/timeline-master/TimelineMasterPanel.tsx:268` — ` · Generated ${batch.duration.generatedDuration}s`.
- `studio-web/src/components/timeline-master/TimelineMasterPanel.tsx:271` — ` · Visible ${batch.duration.timelineVisibleDuration}s`.

**Reference good pattern:** `studio-web/src/components/timeline-master/TrackClipInteractive.tsx:158` — `{preview.start.toFixed(2)}s · {preview.length.toFixed(2)}s`.

### D2 — Raw float renders in Inspector inputs (MEDIUM)

**File:line:**
- `studio-web/src/components/timeline-master/TimelineInspector.tsx:758` — Batch Planned Duration number input: `value={selectedBatch.duration.plannedDuration}`.
- `studio-web/src/components/timeline-master/TimelineInspector.tsx:839` — Repair Start: `<input value={selectedRepair.repair.start} readOnly />`.
- `studio-web/src/components/timeline-master/TimelineInspector.tsx:840` — Repair Length: `<input value={selectedRepair.repair.length} readOnly />`.
- Editable number inputs also surface raw floats until focus: `:567,571,575,593,594,610,611,612,619,620,621,627,628,918,932`.

### D3 — No cancelled-state overlay in LivePreviewMonitor (MEDIUM)

**Root cause:** `LivePreviewMonitor.tsx:157-158` sets `monitorState="cancelled"`; composer returns `{kind:"cancelled",job}` (`TimelinePreviewComposer.tsx:190`); but no JSX branch renders a cancelled banner. Only `monitorState==="failed"` has an overlay (`LivePreviewMonitor.tsx:447-453`).

### D4 — Failed overlay empty line when `activeJob.message` undefined (LOW)

**File:line:** `studio-web/src/components/LivePreviewMonitor.tsx:450` — `<div className="scene-meta">{activeJob?.message}</div>` renders empty when undefined.

### D5 — Inconsistent batch status presentation Panel vs Inspector (LOW)

**File:line:** `studio-web/src/components/timeline-master/TimelineInspector.tsx:830` (raw `Status: {selectedBatch.status}`) vs `studio-web/src/components/timeline-master/TimelineMasterPanel.tsx:11-15,255` (`statusHint()` humanization). Same source of truth, different display.

### D6 — Render queue shows raw truncated `batchBlockId`, not label (LOW)

**File:line:** `studio-web/src/components/timeline-master/CompactRenderQueue.tsx:71-76` — `· batch <code>{batchBlockId.slice(0,10)}</code>`. No lookup into `master.batchBlocks` for `batch.label`. Violates Creator-First UI (no implementation jargon as default chrome).

### D7 — No per-batch Generating/Queued badge on batch clips (LOW)

**File:line:** `studio-web/src/components/DirectorTracks.tsx:1466-1481` — batch clip renders only `<strong>{batch.label}</strong>` + time range. `batch.status` not surfaced on the clip. Per-batch status only in `TimelineMasterPanel.tsx:255` and inspector.

### D8 — Disabled buttons lack plain-language reasons (LOW)

**File:line:** `studio-web/src/components/timeline-master/TimelineMasterPanel.tsx:138,159,177,191,205,284,298,312,324` — `disabled={busy}` with no `title`/`aria-label` reason. Model: `TimelineToolbar.tsx:480-492` Inpaint (`disabled={!inpaintEnabled}` + `title={inpaintTitle}`).

### D9 — Batch lane windowing not scroll-aware (MEDIUM for 100+ batches)

**Root cause:** `DirectorTracks.tsx:1449-1482` computes `lo`/`hi` from `playheadIdx` or `selIdx`, never from `boardScrollRef.current.scrollLeft`. Scrolling to a distant batch without moving the playhead/selecting it → those batches are outside `[lo,hi)` and not rendered. `WIN=80` still mounts up to 80 nodes.

**File:line:** `studio-web/src/components/DirectorTracks.tsx:1449-1482` (windowing), `:1356` (scroll container), `:641` (`boardWidth` grows with batch count). **Needs runtime verification.**

### D10 — Polling loops not visibility-gated; no backoff (LOW)

**File:line:**
- `studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx:118` — `setInterval(tick, 2500)` (Timeline path poller).
- `studio-web/src/components/LivePreviewMonitor.tsx:205` — `setInterval(tick, 2500)` (legacy; dormant when `composed` set).
- `studio-web/src/components/timeline-master/CompactRenderQueue.tsx:28` — `setInterval(load, 3000)`.

No `document.visibilityState` check; no backoff; errors swallowed. **Needs runtime verification** of network rate when tab hidden.

### D11 — `DirectorTracks` N parallel `getTimelineReferences` per `tl` change (LOW)

**File:line:** `studio-web/src/components/DirectorTracks.tsx:478-504` — `Promise.all(clips.map(clip => api.getTimelineReferences(...)))` on every `tl` change. Gated by `timelineRefsEnabled` (`:413-417`). Not debounced.

---

## Timeline API dependency list

Endpoint → component → polling?

| Endpoint | Component(s) | Polling? |
|----------|---------------|----------|
| `api.directorTimelineMaster` (`GET /api/projects/:id/scenes/:sid/director-timeline-master`) | `TimelineMasterPanel.tsx:43`; `TimelineEditorShell.tsx:107`; `TimelineInpaintWorkspace.tsx:408,468` | No |
| `api.getDirector` (`GET /api/projects/:id/scenes/:sid/director`) | `TimelineEditorShell.tsx:114,155,208,225,280,314,434`; `TimelineInspector.tsx:135`; `DirectorTracks.tsx:433`; `TimelineInpaintWorkspace.tsx:306` | No |
| `api.putDirector` (`PUT .../director`) | `TimelineEditorShell.tsx:156,212,236,461`; `DirectorTracks.tsx:575` | No |
| `api.directorTimelineSetMode` | `TimelineMasterPanel.tsx:90`; `TimelineEditorShell.tsx:541,550`; `TimelineToolbar.tsx:342` | No |
| `api.directorTimelineGenerateBatch` | `TimelineMasterPanel.tsx:150,287`; `TimelineToolbar.tsx:360`; `TimelineInpaintWorkspace.tsx:501` | No |
| `api.directorTimelineGenerateScene` | `TimelineMasterPanel.tsx:163,180`; `TimelineEditorShell.tsx:573`; `TimelineToolbar.tsx:363` | No |
| `api.directorTimelineCancel` | `TimelineMasterPanel.tsx:194,209`; `TimelineEditorShell.tsx:582,591` | No |
| `api.directorTimelinePatchBatch` | `TimelineMasterPanel.tsx:301`; `TimelineInspector.tsx:379`; `TimelineInpaintWorkspace.tsx:454` | No |
| `api.directorTimelineDuplicateBatch` | `TimelineMasterPanel.tsx:315` | No |
| `api.directorTimelineDeleteBatch` | `TimelineEditorShell.tsx:273`; `TimelineToolbar.tsx:240` | No |
| `api.directorTimelineAddBatch` | `TimelineToolbar.tsx:223`; `DirectorTracks.tsx:1188,1436` | No |
| `api.directorTimelineAddRepair` | `TimelineMasterPanel.tsx:327`; `TimelineInpaintWorkspace.tsx:400` | No |
| `api.directorTimelineAddClipToBatch` | `DirectorTracks.tsx:777` | No |
| `api.directorTimelinePreflight` | `TimelineEditorShell.tsx:560`; `TimelineToolbar.tsx:349`; `DirectorTracks.tsx:1242` | No |
| `api.directorTimelineGenerators` | `TimelineInpaintWorkspace.tsx:307` | No |
| `api.directorTimelineCameraCatalog` | `TimelineInspector.tsx:153` | No |
| `api.updateScene` | `TimelineInspector.tsx:242` | No |
| `api.listJobs` (`GET /api/projects/:id/jobs`) | `TimelinePreviewComposer.tsx:100`; `LivePreviewMonitor.tsx:187`; `CompactRenderQueue.tsx:23` | **Yes** (2.5s / 2.5s / 3s) |
| `api.getJobPreview` | `TimelinePreviewComposer.tsx:107`; `LivePreviewMonitor.tsx:194` | Yes (within 2.5s tick) |
| `api.cancelJob` | `LivePreviewMonitor.tsx:339,505`; `CompactRenderQueue.tsx:86` | No |
| `api.savePreviewFrame` | `LivePreviewMonitor.tsx:343,516` | No |
| SSE `/api/projects/:id/preview/stream` | `TimelinePreviewComposer.tsx:127`; `LivePreviewMonitor.tsx:216` | Stream (always-on) |
| `api.getTimelineReferences` | `DirectorTracks.tsx:489` | No (burst per `tl` change) |
| `api.getTimelineSceneStatus` | `SceneStatusStrip.tsx:24` | No (single fetch) |
| `api.health` | `DirectorTracks.tsx:414` | No (single fetch) |
| `api.uploadAsset` | `DirectorTracks.tsx:709` | No |
| `api.assetUrl` / `api.mediaUrl` | many (asset/media src resolution) | n/a |
| `api.sceneReferences.attach` | `TimelineEditorShell.tsx:472` | No |
| `api.directorSequenceFromScene` / `patchDirectorSequence` / `sendDirectorToEditor` | `DirectorTracks.tsx:540,549,551` | No |
| `api.validateMotionTags` | `DirectorTracks.tsx:2187` | No |
| `api.timelineRetakes.*` | `TimelineRetakeDrawer.tsx:62,70,181,213,269` | No |

**Timeline-critical endpoints** (errors here are Timeline-relevant console noise): `directorTimelineMaster`, `getDirector`, `putDirector`, `directorTimeline*` family, `listJobs`, `getJobPreview`, `/preview/stream` SSE, `getTimelineReferences`, `getTimelineSceneStatus`, `directorTimelineCameraCatalog`, `directorTimelineGenerators`, `updateScene`.

**Unrelated console errors** (not Timeline-critical): `uploadAsset`, `sceneReferences.attach`, `directorSequenceFromScene`/`sendDirectorToEditor` (Editor handoff path), `validateMotionTags`, `timelineRetakes.*` (Re-take drawer only).

---

## Confirmations

- **D1 confirmed in current code** — `TimelineMasterPanel.tsx:258,266,268,271` render raw `batch.duration.*` floats (matches known defect; the audit additionally flags `:268` generatedDuration and `:271` timelineVisibleDuration, plus Inspector inputs at `:758,839,840`).
- **Good precision patterns exist** — `TrackClipInteractive.tsx:158` (`toFixed(2)` drag readout), `DirectorTracks.tsx:1535-1536` (`toFixed(1)` clip label), `TimelineEditorShell.tsx:527` (`toFixed(1)` scene header), `DirectorTracks.tsx:1478` (`formatTimelineTime` for batch lane range), `TimelineInpaintWorkspace.tsx:361-364,585` (`formatTimelineTime`).
- **Selection consistency** — `DirectorTracks.tsx:381-402` syncs local highlight from global `DirectorSelectionContext`; `TimelineEditorShell.tsx:242-255` restores selection on undo/redo. No stale-clip divergence found.
- **No dead controls** — every visible button has an `onClick` handler wired to a real `api.*` call (verified across `TimelineMasterPanel`, `TimelineEditorShell` header, `TimelineToolbar`, `LivePreviewMonitor`, `CompactRenderQueue`, `TimelineInpaintWorkspace`, `TimelineRetakeDrawer`).
- **No mock completion** — all generation/cancel/preview paths call real `api.*` endpoints; no hardcoded success.
- **Polling is bounded** — no interval below 2s; the 2.5s loops are above the aggressive threshold but lack visibility gating and backoff (D10).
- **Items needing runtime verification:** D2 (visual float display in inputs), D3 (cancelled overlay absence), D9 (scroll-mismatch with 100+ batches), D10 (network rate when tab hidden), area 2 (label truncation at small widths), area 3 (contrast at small widths).

---

## Report path

`docs/release-gate/timeline-full-audit/TIMELINE_UI_INTERACTION_AUDIT.md`
