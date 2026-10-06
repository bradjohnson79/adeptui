# Preview authority — Lip Sync demotion (Re-Take-only)

**Status:** READY-for-primary-review delta (Generation / Preview authority owner)  
**Date:** 2026-09-12 (PT)

## Visual authority

- **Sole Visual playback authority:** composed Visual track = director timeline ideo_clips (Hop 6 
eplace_visual_range → 
tclip_* A|Retake|B).
- **lipsync_output_path:** demoted. May remain on the scene row for MAGI/legacy provenance. **FE must not prefer it for Timeline Preview** when ideo_clips exist (and must not fall through to it as Visual authority).
- **	imeline.lipsync.tracks:** demoted for Timeline dialogue playback. Timeline UX owns Lip Sync strip UI separately.

## Audio authority

- Under 
tclip_* Re-Take windows, **retake media owns AV** (baked AAC). Do not layer obsolete Lip Sync dialogue wavs underneath; do not mute retake AAC for legacy lipsync tracks.
- collectTimelineAudioAtTime does not push Lip Sync dialogue layers.
- shouldMutePreviewVideoSoundtrack returns false for Timeline Re-Take-only (never mutes solely for lipsync_output_path / lipsync clips).

## API fields FE should stop reading for Preview

| Field | Preview Visual | Preview dialogue |
|-------|----------------|------------------|
| scene.lipsync_output_path | **STOP** | **STOP** |
| 	imeline.lipsync.tracks | n/a (strip UI OK) | **STOP** for playback |
| 	imeline.video_clips / 
tclip_* | **USE** | retake AAC owns window |
| scene.output_path | leftover gap only | n/a |

## Quarantine

- LatentSync/Qwen engine: studio-api/app/workflows/lipsync_magi_quarantine.py (shelf; not deleted).
- Env STUDIO_TIMELINE_LIPSYNC_PLAYBACK default off — Timeline must not enable for Preview.
