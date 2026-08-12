# Timeline Preview Monitor Audit

- **Date:** 2026-08-07
- **Auditor:** Read-only subagent (GLM 5.2)
- **Scope:** Timeline Preview Monitor — playhead-as-source-of-truth, resolution priority order, generation/completed/selected/active clip priority, stale state handling, failed-job preview, prompt overlay timing, media URL resolution, no-library-click requirement.
- **Method:** End-to-end read of `resolveTimelineAtTime.ts`, `TimelinePreviewComposer.tsx`, `LivePreviewMonitor.tsx`, `TimelineEditorShell.tsx`, `contracts.ts`, `DirectorTracks.tsx`, `api.ts`, and the composer unit test. No servers, tests, or builds were run (read-only mandate). Items requiring live runtime evidence are marked **NEEDS RUNTIME VERIFICATION**.

## Files of record (current code)

- `studio-web/src/components/timeline-master/resolveTimelineAtTime.ts` (227 lines)
- `studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx` (327 lines)
- `studio-web/src/components/LivePreviewMonitor.tsx` (533 lines)
- `studio-web/src/components/timeline-master/TimelineEditorShell.tsx` (770 lines)
- `studio-web/src/timelineMaster/contracts.ts` (201 lines)
- `studio-web/src/components/DirectorTracks.tsx` (`DirectorTimeline` type, lines 100-115)
- `studio-web/src/api.ts` (`assetUrl`/`mediaUrl`/`getDirector`/`directorTimelineMaster`)
- `studio-web/src/components/timeline-master/TimelinePreviewComposer.test.ts` (223 lines)

## Per-area verdict table

| # | Area | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Playhead is source of truth (image/prompt/video/batch boundary) | **OK** (image/prompt/batch), **DEFECT** (video relative time) | `resolveTimelineAtTime.ts:71-95,128-143`; `TimelinePreviewComposer.tsx:242-253`; `LivePreviewMonitor.tsx:306-317` seeks to `playheadSec`, not `visualLocalTime` |
| 2 | Resolution priority order; no valid timeline visual coexists with Idle | **OK** (order), **MINOR** (assetless clip → idle) | `TimelinePreviewComposer.tsx:178-256`; `resolveTimelineAtTime.ts:88` gates visual on `clip.assetId` |
| 3 | Generation preview vs completed output vs selected vs active clip | **OK** (gen/completed/active), **NOTE** (selection ignored) | `TimelinePreviewComposer.tsx:175` omits `selection`; `useGenerationState:151-156` prefers queued/running |
| 4 | Stale preview state (reload, scene switch, batch delete) | **DEFECT** (seq/preview leak on scene switch), **OK** (batch delete, reload) | `TimelinePreviewComposer.tsx:90-159` does not reset `preview`/`seq` on `scene?.id` change; `TimelineEditorShell.tsx:127-136` resets playhead/selection only |
| 5 | Failed-job preview state | **DEFECT** (minor) | `TimelinePreviewComposer.tsx:189`; `LivePreviewMonitor.tsx:263-279,447-453` — composed failed state ignores draft preview; overlay text claims preservation |
| 6 | Prompt overlay timing (batch-local prompt segments) | **OK** | `resolveTimelineAtTime.ts:126-143`; `TimelinePreviewComposer.tsx:248`; `LivePreviewMonitor.tsx:455-464` |
| 7 | Media URL resolution (asset id → URL; missing asset) | **OK** (URL build), **NEEDS RUNTIME VERIFICATION** (404 handling) | `api.ts:5724` `/api/assets/{id}/file`; `resolveTimelineAtTime.ts:88` null-asset guard |
| 8 | No Library click required for timeline-driven preview | **OK** | `TimelinePreviewComposer.tsx:237-254`; test `TimelinePreviewComposer.test.ts:156-189` confirms |

## Defect details

### D1 — Video clip in `timeline_frame` seeks to global playhead, not clip-local time
- **Severity:** Medium-High
- **Root cause:** `resolveTimelineAtTime.ts:95` and `:109` correctly compute `visualLocalTime = batchLocalTime - clip.start` (batch-owned) / `t - videoClip.start` (scene-global), and the composer propagates it (`TimelinePreviewComposer.tsx:252`). However, `LivePreviewMonitor.tsx:306-317` (the video seek effect) sets `v.currentTime = playheadSec` unconditionally for every video element, including `timeline_frame` videos. The `visualLocalTime` field is never read by `LivePreviewMonitor.tsx` (grep for `visualLocalTime`/`batchLocalTime` returns no matches).
- **Consequence:** For a video clip starting at global timeline offset `T0` with the playhead at `T0 + k`, the video element is seeked to `T0 + k` seconds (its own internal time), not `k` seconds. The wrong frame is shown, and for clips whose source is shorter than `T0 + k`, the seek clamps to the end / throws (caught and ignored at `LivePreviewMonitor.tsx:313-315`).
- **Two-way sync broken:** `onTimeUpdate` (`LivePreviewMonitor.tsx:384-393`) reports `el.currentTime` back as the playhead, so playback re-feeds the video's internal time as the global timeline time — the playhead jumps to the video's internal clock instead of advancing along the Director timeline.
- **Fix direction:** When `composed?.kind === "timeline_frame"`, seek to `composed.visualLocalTime` (plus `trimStart` if available on the clip) and translate `onTimeUpdate` back to global time via `composed.batchLocalTime`/clip start. The composition already carries `visualLocalTime` and `batchLocalTime` (`TimelinePreviewComposer.tsx:49-50`).
- **Needs runtime verification:** Confirm wrong-frame / wrong-clock behavior with a real video clip in `video_finishing` mode at a non-zero playhead.

### D2 — `preview` and `seq` state leak across scene switches in `useGenerationState`
- **Severity:** Medium
- **Root cause:** `useGenerationState` (`TimelinePreviewComposer.tsx:80-159`) stores `preview` and `seq` in `useState` (lines 91-92) but its effects depend on `[projectId, scene?.id, pauseUpdates]` (line 123) and `[projectId, scene?.id, pauseUpdates, scene?.name]` (line 149) without resetting `preview`/`seq` when `scene?.id` changes. The component is not remounted on scene switch — `TimelineEditorShell.tsx:637-652` renders `<TimelinePreviewComposer>` inline, so React preserves the hook state across scene changes.
- **Consequence A (seq gate):** The poll (`:108`) and SSE (`:135`) both guard with `(p.preview.sequenceNumber || 0) >= seqRef.current`. If scene A drove `seq` to a high value, then scene B's preview stream (starting from low sequence numbers) is rejected until its sequence catches up to scene A's high-water mark. This can suppress scene B's live preview frames for an extended period.
- **Consequence B (stale preview payload):** Between scene switch and the first accepted preview for scene B, the stale `preview` object from scene A remains in state and is passed to `resolvePreviewComposition`. If scene B has a running job, the `generation_draft` branch (`TimelinePreviewComposer.tsx:208-221`) renders `preview.previewSrc` — scene A's source URL — until scene B's preview clears the seq gate. The SSE scene filter (`:134` `p.sceneId !== scene.id`) only blocks *incoming* mismatched payloads; it does not clear the existing `preview`.
- **Fix direction:** Add an effect keyed on `scene?.id` that calls `setPreview(null)` and `setSeq(0)` (and `seqRef.current = 0`) when the scene id changes.
- **Needs runtime verification:** Reproduce by running a generation in scene A, switching to scene B with a queued job, and observing whether B's first preview frames appear promptly.

### D3 — Composed `failed` state does not show the latest draft preview, despite overlay claiming it does
- **Severity:** Low / Minor (copy + behavior mismatch)
- **Root cause:** `resolvePreviewComposition` returns `{ kind: "failed", job: activeJob }` (`TimelinePreviewComposer.tsx:189`). In `LivePreviewMonitor.tsx:263-279`, the `mediaSrc` for `composed` handles `library`, `final_output`, `generation_draft`, `preparing`, `timeline_frame` explicitly; every other composed kind (including `failed`, `cancelled`, `idle`) falls through to `finalSrc || sourceStill`. The streamed `preview?.sourceUrl` / `preview?.localPath` is NOT consulted for the composed `failed` state. The legacy (non-composed) path (`:275-279`) does use `previewSrc` for the failed monitor state.
- **Consequence:** On the Timeline path, a failed render shows the scene's final output or source still, not the last received draft frame. The overlay at `LivePreviewMonitor.tsx:451` still reads "Latest draft preview preserved when available." — inaccurate for the composed path.
- **Fix direction:** Either (a) extend the composed `mediaSrc` ladder to use `preview?.sourceUrl || preview?.localPath ? api.mediaUrl(...) : finalSrc || sourceStill` for `failed`/`cancelled`, or (b) update the overlay copy to match the composed behavior.
- **Needs runtime verification:** Confirm whether the draft frame is actually expected to survive a failure on the Timeline path.

### D4 (minor) — A `timeline_frame` visual clip without an `assetId` falls through to Idle
- **Severity:** Low
- **Root cause:** `resolveTimelineAtTime.ts:88` requires `clip.assetId` to set `activeVisual`; `:102` and `:114` require `asset_id` for the scene-global fallback. If a visual clip exists at the playhead but has a null/empty asset id (e.g., a placeholder/guide clip), `activeVisual` stays null and `resolvePreviewComposition` returns `idle` (`TimelinePreviewComposer.tsx:256`).
- **Consequence:** A clip-shaped placeholder on the timeline produces an Idle monitor rather than a "missing asset" indication. Whether this is a defect depends on product intent — guide/placeholder clips may be expected to show Idle. Flagging because the audit scope asks "no valid timeline visual can coexist with an Idle state"; a clip with no asset is arguably a timeline visual with no media.
- **Fix direction:** If placeholders should be visible, render a labeled empty-state for `activeVisual` with null asset; otherwise document the behavior.

## Confirmations

### C1 — Playhead is the source of truth for image clips and prompts
`resolveTimelineAtTime` reads `playheadSec` (`:71`) and `master.batchBlocks` (`:75`), resolves the active batch by cumulative planned duration (`:52-66`), then resolves batch-owned `visualClips`/`promptSegments` against `batchLocalTime` (`:84-97`, `:128-135`) with scene-global `image_clips`/`prompt_segments` as fallback (`:98-124`, `:136-143`). `TimelinePreviewComposer` calls it with `args.playheadSec` (`:242`) and `TimelineEditorShell` supplies the real `playheadSec` state (`:643`) plus the real `directorTimeline` (`:640`) and `master` (`:641`). The prior milestone fix is intact: the shell fetches the real DirectorTimeline via `api.getDirector` (`:114`) instead of casting `master` (`:108-118`).

### C2 — Crossing a batch boundary switches visual and prompt
`resolveBatchAtTime` (`:52-66`) uses exclusive-end intervals (`t < cursor + len`) with `Math.max(0.1, plannedDuration)` (`:59`), so batches are contiguous with no gaps. When the playhead crosses a boundary, `activeBatch` and `batchLocalTime` change, and the batch-owned `visualClips`/`promptSegments` are re-resolved against the new batch's local time. The `timeline_frame` composition carries the new `batchId` (`TimelinePreviewComposer.tsx:250`).

### C3 — Resolution priority order matches the documented ladder
`resolvePreviewComposition` order (`TimelinePreviewComposer.tsx`): library (`:178-186`) → failed (`:189`) → cancelled (`:190`) → completed output / `done` job (`:193-205`) → active generation / queued|running (`:208-221`) → final scene output with no active job (`:224-235`) → `timeline_frame` (`:237-254`) → idle (`:256`). This matches the scope's stated order. A `timeline_frame` visual cannot coexist with Idle because the `timeline_frame` branch requires `frame.activeVisual && frame.activeVisual.assetId` (`:243`); otherwise it falls through to idle. (See D4 for the assetless-clip edge.)

### C4 — Generation preview priority vs completed output priority vs active clip
`useGenerationState.activeJob` prefers queued/running jobs then falls back to any job for the scene (`TimelinePreviewComposer.tsx:151-156`). Because a job has exactly one status, the `done` branch (`:193`) and the `queued|running` branch (`:208`) are mutually exclusive given a single `activeJob`. When a scene has both a completed job and a new running job (re-take), `activeJob` is the running one, so `generation_draft` wins over the prior `final_output` — correct. The `selection` argument is accepted (`:169`) and included in the `useMemo` deps (`:304`) but never read inside `resolvePreviewComposition` (`:175` destructures only `scene, libraryAsset, activeJob, preview`). So the *selected* clip does not drive the preview — only the *active* (playhead-intersected) clip does. This is consistent with "playhead is the source of truth" and is judged OK, not a defect.

### C5 — Prompt overlay timing follows batch-local prompt segments
`resolveTimelineAtTime` resolves `activePrompt` from `activeBatch.promptSegments` against `batchLocalTime` (`:128-135`), falling back to scene-global `prompt_segments` against global `t` (`:136-143`). The composer forwards `frame.activePrompt?.text` to the `timeline_frame` composition (`:248`). `LivePreviewMonitor` renders the lower-third only when `composed?.kind === "timeline_frame" && composed.promptText` (`:455`), with `data-testid="timeline-prompt-lower-third"` (`:459`). The lower-third is intentionally suppressed for non-`timeline_frame` compositions (library/final_output/generation_draft), which is by design. Note: `resolveTimelineAtTime.ts:133` always sets `label: ""`, so `composed.promptLabel` is effectively dead — harmless.

### C6 — No Library click required for timeline-driven preview
The `timeline_frame` branch (`TimelinePreviewComposer.tsx:237-254`) fires whenever there is no library asset, no active job, no scene output, and an active visual clip exists at the playhead. No `libraryAsset` selection is needed. The unit test at `TimelinePreviewComposer.test.ts:156-189` asserts `timeline_frame` is returned with `libraryAsset: null` and `activeJob: null`. The shell wires `libraryAsset={selectedAsset}` (`:645`) where `selectedAsset` is null unless the creator clicks an AssetTray item (`:102-103`).

### C7 — Media URL resolution
`api.assetUrl(assetId)` returns `/api/assets/${assetId}/file` (`api.ts:5724`). The composer uses it for `timeline_frame` visuals (`TimelinePreviewComposer.tsx:246`) and library assets (`:179`). `api.mediaUrl(absPath)` (`api.ts:5713-5722`) rewrites `\data\` paths to `/media/...` and otherwise falls back to `/api/file?path=...`. Null/empty asset ids are guarded at `resolveTimelineAtTime.ts:88,102,114`, so no broken empty-URL `<img>` is produced by the resolver. **Needs runtime verification:** behavior when the asset id is non-null but the asset record is missing (HTTP 404 on `/api/assets/{id}/file`) — the `<img>`/`<video>` will show a broken media element with no graceful fallback in `LivePreviewMonitor.tsx:399-411`.

### C8 — Batch delete while previewing
`TimelineEditorShell.deleteSelection` (`:260-277`) for a `batch` selection calls `api.directorTimelineDeleteBatch` then `afterMutation` (`:275`), which calls `refreshMaster` (`:198`) and re-fetches both `master` and `directorTimeline` (`:105-119`). The playhead is NOT reset on batch delete. If the playhead was inside the deleted batch, `resolveBatchAtTime` returns null (no batch covers that time), `activeBatch` is null, and resolution falls back to scene-global tracks (`:98-124`, `:136-143`); in batch-owned mode those are typically empty, so the monitor returns to `idle`. This is graceful (no crash, no stale batch shown) but the playhead is left pointing at a now-empty region. Judged OK; optionally the shell could clamp the playhead to the nearest remaining batch.

### C9 — Reload behavior
On full page reload, `master` and `directorTimeline` start as `null` (`TimelineEditorShell.tsx:83-84`). The `useEffect` on `selectedSceneId` (`:127-136`) fires on mount, calls `refreshMaster` (`:134`), which populates both. `playheadSec` starts at `0` (`:81`). The composer's `useMemo` recomputes once `master`/`directorTimeline` arrive, so the preview transitions from `idle` to `timeline_frame` (or `final_output`) after the fetch resolves. No stale preview persists across a hard reload because React state is recreated. (The D2 leak only affects in-app scene switches, not full reloads.)

---

**End of audit.**
