# TIMELINE PREVIEW MONITOR AUDIT

**Milestone:** Timeline Multi-Batch + Preview Monitor — Mandatory GO Closure
**Audit type:** Read-only architecture audit (independent)
**Date:** 2026-08-07
**Status:** ROOT CAUSE IDENTIFIED

## 1. Executive summary

**Verdict:** `TimelinePreviewComposer` is **mounted and wired** in the canonical Timeline shell, but **timeline-driven preview is not implemented**. The composer's `resolvePreviewComposition` accepts `timeline`, `selection`, and `playheadSec` yet **never uses them**. The Preview Monitor therefore falls through to `{ kind: "idle" }` whenever there is no library selection, no active generation job, and no scene `output_path` — exactly matching the reported defect.

Additionally, `TimelineEditorShell` passes **`master` (`SceneTimelineMaster`) cast as `DirectorTimeline`**, not the actual director timeline (`image_clips`, `prompt_segments`, etc.). That timeline lives only inside `DirectorTracks` local state and is never shared with the composer.

## 2. Root cause

`resolvePreviewComposition` ([TimelinePreviewComposer.tsx:153-224](studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx)) implements only this priority chain:

1. Library asset (explicit click)
2. Failed / cancelled generation job
3. Completed generation -> scene final output
4. Active generation -> draft preview frames
5. Scene final output (no job)
6. **`idle`**

It **never inspects `image_clips`, `video_clips`, `prompt_segments`, or playhead position**. With an image clip on the timeline and playhead over it, but no library click and no scene output, the composition is always `{ kind: "idle" }`, which drives the "Click a Library image..." empty state.

Additionally, `TimelineEditorShell` passes **`master` (`SceneTimelineMaster`) cast as `DirectorTimeline`**, not the actual director timeline. That timeline lives only inside `DirectorTracks` local state and is never shared with the composer.

## 3. `TimelinePreviewComposer.tsx` — what `resolvePreviewComposition` returns

`PreviewComposition` union ([TimelinePreviewComposer.tsx:32-39](studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx)) — only these kinds exist, **no timeline-clip or prompt-overlay kind**:

```32:39:studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx
export type PreviewComposition =
  | { kind: "idle" }
  | { kind: "preparing"; job: Job }
  | { kind: "generation_draft"; job: Job; previewSrc: string; sourceStill: string }
  | { kind: "final_output"; src: string; mediaKind: "video" | "image"; job?: Job }
  | { kind: "failed"; job: Job }
  | { kind: "cancelled"; job: Job }
  | { kind: "library"; asset: Asset; src: string; mediaKind: "video" | "image" | "audio" };
```

Priority logic ([TimelinePreviewComposer.tsx:153-224](studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx)) — `timeline`, `selection`, and `playheadSec` are in the signature but **not destructured or used**:

```153:224:studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx
export function resolvePreviewComposition(args: {
  scene: Scene | undefined;
  timeline: DirectorTimeline | null;
  selection: DirectorSelection;
  playheadSec: number;
  libraryAsset: Asset | null;
  activeJob: Job | null;
  preview: PreviewPayload | null;
}): PreviewComposition {
  const { scene, libraryAsset, activeJob, preview } = args;
  // ... library, failed/cancelled, completed, generation_draft, final_output ...
  return { kind: "idle" };
}
```

**Finding:** There is **no "active image at playhead" case**. Comments claim the composer resolves from "selection, playhead, active clips" (lines 18-19), but the implementation does not.

Composer passes composition to monitor ([TimelinePreviewComposer.tsx:258-287](studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx)) — wiring is correct; resolution is what's missing.

## 4. `LivePreviewMonitor.tsx` — display logic

Accepts `composition` prop ([LivePreviewMonitor.tsx:45-51](studio-web/src/components/LivePreviewMonitor.tsx)); when provided, treated as sole source of truth (lines 106-109).

Idle state is still the default when `composition.kind === "idle"` ([LivePreviewMonitor.tsx:129-133](studio-web/src/components/LivePreviewMonitor.tsx)):

```129:133:studio-web/src/components/LivePreviewMonitor.tsx
  const monitorState: PreviewMonitorState = (() => {
    if (composed) {
      switch (composed.kind) {
        case "idle":
          return "idle";
```

Idle UI copy ([LivePreviewMonitor.tsx:406-411](studio-web/src/components/LivePreviewMonitor.tsx)):

```406:411:studio-web/src/components/LivePreviewMonitor.tsx
        ) : (
          <div className="director-stage-empty">
            <strong>{monitorState === "preparing" ? "Preparing…" : "Idle"}</strong>
            <span>{scene ? scene.name : "Select a scene"}</span>
            <span className="scene-meta">Click a Library image, video, or audio to preview it here.</span>
          </div>
        )}
```

`mediaSrc` from composition ([LivePreviewMonitor.tsx:261-275](studio-web/src/components/LivePreviewMonitor.tsx)) — only `library`, `final_output`, `generation_draft`, `preparing` contribute media. **`idle` -> empty `mediaSrc` -> idle UI.**

Overlays today ([LivePreviewMonitor.tsx:414-438](studio-web/src/components/LivePreviewMonitor.tsx)): only library metadata, generation draft status, failed render. **No prompt lower-third.**

## 5. Where `TimelinePreviewComposer` is mounted

Canonical Timeline path — **WIRED** ([TimelineEditorShell.tsx:626-640](studio-web/src/components/timeline-master/TimelineEditorShell.tsx)):

```626:640:studio-web/src/components/timeline-master/TimelineEditorShell.tsx
                <TimelinePreviewComposer
                  project={project}
                  scene={selected}
                  timeline={master as never}
                  selection={selection}
                  playheadSec={playheadSec}
                  onPlayheadChange={setPlayheadSec}
                  libraryAsset={selectedAsset}
                  onClearLibraryAsset={() => setLibraryPreviewId(null)}
                  hideOverlay={hideOverlay}
                  onHideOverlayChange={setHideOverlay}
                  pauseUpdates={pauseUpdates}
                  onPauseUpdatesChange={setPauseUpdates}
                  inlineActions={false}
                />
```

**Problems:**
- `timeline={master as never}` — `master` is `SceneTimelineMaster` (batch blocks), **not** `DirectorTimeline` with `image_clips`/`prompt_segments`.
- `DirectorTracks` loads the real timeline via `api.getDirector()` into **local state** (`tl`) and never exposes it to the composer.

`DirectorTracks` embedded stage — **DISABLED in shell** ([TimelineEditorShell.tsx:665-675](studio-web/src/components/timeline-master/TimelineEditorShell.tsx)): `hideEmbeddedStage` + `shellMode` hide the old embedded preview (`showStage = false` at line 869). Users rely entirely on `TimelinePreviewComposer`, which does not show timeline clips.

Legacy `ProjectEditor` path — **NOT using composer** ([ProjectEditor.tsx:267-274](studio-web/src/pages/ProjectEditor.tsx)): other tabs use `LivePreviewMonitor` directly, no `composition` prop.

## 6. Active clip resolver — DOES NOT EXIST

Repo-wide search found **no** `resolveTimelineAtTime`, `clipAtPlayhead`, `activeVisual`, or `activePrompt` in the preview pipeline.

Closest existing patterns (not used by preview):

| Location | Behavior | Playhead-aware? |
|----------|----------|-----------------|
| `DirectorTracks.previewMedia` (857-864) | First image clip with `asset_id`, or video clip, or scene output | **No** |
| `DirectorTracks.activeSeg` (586) | Selected/first prompt segment | **No** (selection-based) |
| `TimelineInpaintWorkspace.resolveWorkspaceTarget` (149-184) | Batch window at playhead for inpaint | **Yes**, but inpaint-only |

`DirectorTracks.previewMedia` ([DirectorTracks.tsx:857-864](studio-web/src/components/DirectorTracks.tsx)) — not playhead-based:

```857:864:studio-web/src/components/DirectorTracks.tsx
  const previewMedia =
    tl.media_mode === "video" && tl.video_clips[0]?.asset_id
      ? api.assetUrl(tl.video_clips[0].asset_id)
      : imageClips.find((c) => c.asset_id)?.asset_id
        ? api.assetUrl(imageClips.find((c) => c.asset_id)!.asset_id!)
        : scene.output_path
          ? api.mediaUrl(scene.output_path)
          : "";
```

This logic only feeds the **hidden** embedded stage, not the Preview Monitor.

## 7. Playhead state flow

`TimelineEditorShell` owns playhead ([TimelineEditorShell.tsx:81](studio-web/src/components/timeline-master/TimelineEditorShell.tsx)). Flows to composer (`playheadSec={playheadSec}` line 631) and `DirectorTracks` (`externalPlayhead`/`onPlayheadChange` lines 670-671). `DirectorTracks` uses playhead for ruler display, seeking, keyboard nudging, persisting to director JSON — **not for preview composition**. Composer receives playhead but ignores it in resolution (included in `useMemo` deps line 269 but unused inside `resolvePreviewComposition`).

## 8. Prompt lower-third overlay — DOES NOT EXIST

Search in preview components found **no** prompt lower-third rendering. Existing overlays in `LivePreviewMonitor` are library / generation / failure only. Lower-third exists only in **Magi Editor** (`magi/overlays/`, `MagiEditorWorkspace.tsx`) — unrelated to Timeline preview. CSS class `.live-preview-overlay` (styles.css lines 2559-2571) is positioned bottom-left and could be reused, but nothing renders prompt text there today.

## 9. Asset URL resolution

Image clips resolve via `api.assetUrl(asset_id)` ([api.ts:5697](studio-web/src/api.ts)): `assetUrl: (assetId: string) => '/api/assets/${assetId}/file'`. Used in composer for library assets (line 166) and generation `sourceStill` (line 198). **Not used for timeline `image_clips`.** `DirectorTracks` uses the same pattern for clip thumbs and embedded stage (lines 859-861, 1473, 1552).

## 10. Does Preview Monitor observe Timeline clips?

| Input | Observed by composer? | Observed by monitor? |
|-------|----------------------|----------------------|
| Library asset click | Yes (priority 1) | Via composition |
| Generation job / SSE | Yes | Via composition |
| Scene `output_path` | Yes | Via composition |
| Timeline `image_clips` at playhead | **No** | **No** |
| Timeline `prompt_segments` at playhead | **No** | **No** |
| `selection` | Passed, **unused** | **No** |
| `playheadSec` | Passed, **unused** | Only video scrub sync (lines 299-310) |

**The Preview Monitor does not observe timeline clips at all** — only library asset, generation state, and scene output.

## 11. Is `TimelinePreviewComposer` dead code?

**No — it is live but incomplete.** Mounted in `TimelineEditorShell`; passes `composition` to `LivePreviewMonitor`; owns generation polling/SSE. But resolves timeline/playhead clips: **No**. Unit tests cover playhead clips: **No**. E2E test for timeline-driven preview: **No** (test 4 only checks visibility). Tests in `TimelinePreviewComposer.test.ts` cover idle, library, jobs, and scene output — **zero playhead/timeline cases**.

## 12. Documentation vs implementation gap

`docs/release-gate/timeline-audit/TIMELINE_AUDIT_REPAIR_PRODUCTION_READINESS_COMPLETION_REPORT.md` (line 36) claims the composer resolves from "selection, playhead, active clips." `scripts/verify_timeline_audit.py` only checks that the file exists and contains the string `PREVIEW_COMPOSER_IS_SOLE_SOURCE_OF_TRUTH` — it does not verify playhead logic.

## 13. Files / functions that must change

1. **New resolver** in `studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx` (or new `resolveTimelineAtTime.ts`): implement `resolveTimelineAtTime(timeline, playheadSec)` returning `{ activeBatch, batchLocalTime, activeVisual, visualLocalTime, activePrompt, activeAudio, audioLocalTime, activeSfx, activeCameraInstruction }` via clip intersection `playheadSec >= start && playheadSec < start+length`; deterministic overlap priority.

2. **Extend `PreviewComposition`** with a `timeline_frame` kind carrying `visualSrc` + optional `promptText` + `batchId` + local times.

3. **Update `resolvePreviewComposition`**: destructure and use `timeline`/`playheadSec`; insert timeline-at-playhead resolution after library, before or alongside generation (priority TBD by product spec — generation-active > completed-output > active-timeline-visual > idle). Resolve image URL via `api.assetUrl(clip.asset_id)`.

4. **`TimelineEditorShell.tsx`**: lift `DirectorTimeline` from `DirectorTracks` (or fetch `api.getDirector()` in shell) and pass real timeline to composer. Replace `timeline={master as never}` with actual `DirectorTimeline`. Keep `master` for batch/inpaint features separately.

5. **`DirectorTracks.tsx`** (optional refactor): expose `tl` to parent via callback/prop, or accept controlled timeline prop. Remove/consolidate duplicate `previewMedia` logic into the composer.

6. **`LivePreviewMonitor.tsx`**: handle new composition kinds in `monitorState` and `mediaSrc`; render **prompt lower-third overlay** when composition includes active prompt text (reuse `.live-preview-overlay` styling); update idle tip copy when timeline has clips but playhead is in a gap.

7. **Tests**: `TimelinePreviewComposer.test.ts` — playhead over image clip -> non-idle composition; playhead over prompt -> overlay text present. E2E — add stage asserting image appears without library click when playhead intersects clip.

8. **Certification scripts**: add static gate verifying `resolveTimelineAtTime` or playhead intersection in composer.

## 14. Bottom line

The defect is **architectural incompleteness**, not a missing mount. `TimelinePreviewComposer` was introduced as the sole source of truth and is wired into the Timeline shell, but **`resolvePreviewComposition` was never implemented for timeline/playhead resolution**. The shell also passes the wrong timeline object. Until a `resolveTimelineAtTime`-style function feeds clip assets and prompt text into `PreviewComposition`, and `LivePreviewMonitor` renders a prompt lower-third, the monitor will remain library/generation/output-driven and show **Idle** for timeline-only image clips.
