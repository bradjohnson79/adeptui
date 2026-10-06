# Scene 10 - Original Voice Suppression

## Problem
Timeline preview `<video>` played baked MiniMax / Performance Retake AAC while
`useTimelineAudioPlayback` simultaneously played lipsync dialogue wavs, causing
double voice on Scene 10.

## SINGLE_PATH (reconcile 2026-09-12 PT)
**One mute authority on live AIVideoStudio:**

| Path | Helper | Semantics | Status |
|------|--------|-----------|--------|
| A (consolidator, live) | `shouldSuppressPreviewVideoAudio` | Mute if *any* lipsync dialogue clip exists on timeline (no playhead / no retake path) | **REMOVED** |
| B (Voice Bot worktree) | `shouldMutePreviewVideoSoundtrack` | Mute when `lipsync_output_path` **OR** an **enabled** lipsync clip with audio **intersects playhead** | **WON - landed on live** |

### Live wiring
- Helper: `studio-web/src/components/timeline-master/shouldMutePreviewVideoSoundtrack.ts`
- Composer: `TimelinePreviewComposer` computes `muteVideoAudio` via the helper and passes it to `LivePreviewMonitor`
- Monitor: applies `muted` + `data-suppress-original-voice` (library inspect stays unmuted)
- Do **not** reintroduce `shouldSuppressPreviewVideoAudio*`

### Separate from picture (PLAYBACK_FIX)
Mute authority is not picture source selection. Batch 2 / multi-batch playback fix
keeps **timeline visual / approved Batch take before scene-level `lipsync_output_path`**
in `resolvePreviewComposition` (sections 3.5 then 3.6). Do not regress that order
when touching mute.

### Out of scope
- H3 Comfy workflows are not modified by this mute path (preview-only).