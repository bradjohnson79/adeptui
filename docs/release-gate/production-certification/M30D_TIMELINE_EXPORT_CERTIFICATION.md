# M3.0d Timeline and Export Certification

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Register items | B18 (primary), B5/B17 (related) |
| Export contract | `m30d-canonical-timeline-v1` |
| Implementation SHA | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |

## Certification statement

The native Director timeline and export path is **GREEN** for the bounded Manual User Beta contract:

- Director timeline proposals persist through scene `director_json`.
- Imported audio cues with gain/syncEvent appear in timeline data.
- Export packs include `director_json` per scene.
- Export jobs complete with non-empty media files (PNG, WAV, MP4).

Generative audio and LTX/WAN native video are **not** claimed.

## B18 â€” Export includes director_json (Closed)

### Problem

Export packs previously omitted `director_json`, losing Director plan state in delivered artifacts.

### Fix

`studio-api/app/queue_worker.py` export path emits scene records with `director_json` under contract `m30d-canonical-timeline-v1`.

### Proof

`artifacts/m30-situations/phase18-final-validation.json`:

| Field | S01â€“S12 |
|-------|---------|
| `export.jobStatus` | `done` (all 12) |
| `export.exists` | `true` |
| `export.projectJson` | `true` |
| `export.directorJson` | `true` |
| `export.mediaFiles` | PNG + WAV + MP4 non-empty |

## Capability matrix

| Capability | Status | Evidence |
|------------|--------|----------|
| Read director timeline | **VERIFIED** | Timeline API/UI + M2.9 tests |
| Apply timeline operations | **VERIFIED** | M2.9 persistence tests |
| Audio clips on timeline | **VERIFIED** | `test_m30_audio_timeline.py`, B13 syncEvent |
| Export pack structure | **VERIFIED** | 12/12 situation exports |
| Provider fal motion on timeline | **VERIFIED (reused)** | Seedance MP4 in all packs |
| Multi-scene editorial continuity | **PENDING** | Not beyond 12 bounded situations |
| Generative audio on timeline | **UNAVAILABLE** | Import-only honest path |

## Implementation surfaces

- `Timeline.tsx`, `DirectorTracks.tsx`, `EditorWorkspace.tsx`
- `studio-api/app/codirector/m29/audio/service.py`
- `studio-api/app/queue_worker.py`

Prior M3.0c baseline: `docs/m3.0c/TIMELINE_AND_EDITOR_CERTIFICATION.md` â€” M3.0d elevates Directorâ†’Editor and export to **Closed** with situation artifacts.

## Status

| ID | Status |
|----|--------|
| B18 | **Closed** |
| Timeline read/apply | **Verified** |
| Export delivery | **Verified (12/12)** |
