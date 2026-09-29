# Media Clip Labels — Shared Contract

Canonical authority (do not create a second system):

- TypeScript: `studio-web/src/timelineMaster/mediaClipLabels.ts` → `resolveMediaClipLabels`
- Python: `studio-api/app/timeline_media_labels.py` → `resolve_media_clip_labels`

## Fields

| Field | Role |
|---|---|
| `title` | Full Inspector title |
| `description` | Full Inspector description (retake: dialogue + ids) |
| `label` | Clip-face string; UI truncates via resolver `.label`; persistence prefers full `title` |

## Fallback order

metadata → job → prompt → asset → filename → none (never fabricate)

## Kinds

`audio` | `sfx` | `music` | `ambience` | `performance_retake` | `lipsync`
