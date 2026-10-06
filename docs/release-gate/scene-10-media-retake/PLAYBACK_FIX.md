# PLAYBACK_FIX - Batch visual before lipsync (picture)

## Rule
In `TimelinePreviewComposer` / `resolvePreviewComposition`, when the playhead
intersects a Batch Visual / approved take, that asset is the `<video>` src.
Scene-level `lipsync_output_path` (media retake) applies only when there is **no**
intersecting timeline visual (gap / empty playhead).

This prevents a short one-batch retake file from pinning the preview while the
playhead advances into Batch 2+ (EOF freeze while audio correctly switches).

## Separation
Picture selection (this doc) is independent of original-voice mute
(`SCENE10_ORIGINAL_VOICE_SUPPRESSION.md`). Changing mute must not reorder 3.5 / 3.6.