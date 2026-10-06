# MAGI Library + Audio Preview + Thumbnail Convergence — Certification

**Governing document (Law 30)** for the MAGI Library drawer, thumbnail path, and preview mix. Sibling reports: [`MAGI_PUBLISHED_MASTER_CD_FINISHING_CERTIFICATION.md`](MAGI_PUBLISHED_MASTER_CD_FINISHING_CERTIFICATION.md), [`MAGI_OLD_NEW_SPLIT_VIEW_CERTIFICATION.md`](MAGI_OLD_NEW_SPLIT_VIEW_CERTIFICATION.md).

| Field | Value |
| --- | --- |
| Date | 2026-09-14 (PT) / 2026-09-15 (UTC) |
| Branch | `feat/character-creator-final-closure` |
| HEAD SHA | `99665cf76693e359cedc60c50c4405daf1b4e3a1` (working tree; this mission uncommitted) |
| Project | **Korri Anadriya** `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Scene 12B | `d774a22f-2b02-4eb2-b5ab-a98af9ff8f85` |
| Review URL | `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?tab=magi&sceneId=d774a22f-2b02-4eb2-b5ab-a98af9ff8f85` |

## Verdict

**GO — MAGI LIBRARY + AUDIO PREVIEW + THUMBNAIL CONVERGENCE CERTIFIED**

## Owner fields

| Field | Result |
| --- | --- |
| LEFT DRAWER BEFORE/AFTER | Before: PROJECT / MEDIA / ASSETS / RECIPES. After: **PROJECT / LIBRARY / RECIPES**. Legacy `media`/`assets` pane ids normalize to `library`. Redundant ASSETS accordion removed. |
| LIBRARY SOURCE | Same project Library (`api.library` / `AddFromProjectLibraryModal`). One store. No MAGI-only asset DB. |
| LIBRARY BUTTON | Timeline-style **Library** button (`data-testid=magi-library-button`) opens the project Library modal. |
| FILTERS | **All / Video / Image / Audio** live in the drawer. Video filter lists `video_published_master` first among videos. Audio filter lists audio cards only (`Airlock_Slide_Open`, `ambience_gen`, `Tension_Underscore_v1`, …). |
| REFERENCE SECTION | **Absent.** No CRS/ERS/PRS / References tab on MAGI. |
| VIDEO THUMBNAILS | `libraryThumbUrl` → `/thumb?w=256`. Live probe: three videos HTTP **200**. Drawer shows real posters (12B sofa still), not generic “video” tiles. |
| IMAGE THUMBNAILS | Canonical `/thumb?w=256` (not `/file`). Live probe: three images HTTP **200**. |
| AUDIO CARDS | Static audio cards. `libraryThumbUrl(..., "audio"|"music"|"sfx")` returns **null**. Live `/thumb` on audio expected unused (`error:HTTPError` / `expect: not_used`). |
| BROKEN-ASSET HANDLING | Failed ids remembered in session (`failedThumbs`); no 400/404 retry storm. Honest fallback card. |
| AUDIO ROOT CAUSE | Preview silence was hard-muted `MagiVideoStage`, not missing AAC. 12B master already has AAC. |
| SOURCE AUDIO BINDING | AUDIO clip = published master, same 720 frames. `audioLaneOwnsPlayback` true → picture **muted**. |
| PREVIEW PLAYBACK | `MagiPreviewMixer` one `<audio>` on published `/file`. On Play: mixer `paused: false`, `muted: false`, `volume: 1`, `currentTime` advancing. Split picture stages stay muted. |
| MUTE/VOLUME | Mute chip → mixer `muted: true` / paused. Toolbar mute + volume present. Sound chip shows **Muted**. |
| TRACK MIX | Mixer honors track mute/solo. MUSIC/SFX empty after CD “no music” — correct. Adding a Library music/SFX clip uses the same mixer nodes. |
| DUPLICATE AUDIO CHECK | One mixer stream. Both Split View videos `muted: true`. No embedded+extracted double play. |

## Scene 12B

| Check | Result |
| --- | --- |
| Published master loaded | Yes — VIDEO + AUDIO, 30s, no Batch 1/2 on the sequence |
| Audio audible | Mixer playing published AAC (browser cannot certify speakers; element state measured) |
| Thumbnail | Video posters + image thumbs 200; audio cards no `/thumb` |
| Batch clips absent | Sequence clip count **2** |

## Co-Director

| Check | Result |
| --- | --- |
| Library awareness | MAGI knowledge: one project Library; finishing writes new rows |
| Audio awareness | Keep-original / no-music overrides; EQ/5.1 `NOT_SUPPORTED` |
| Post-production routing | Command placeholder: “finish this scene professionally, upscale to 2K, no music, keep original audio” |

## Tests

Frontend: `26 passed` — `libraryThumb.test.ts`, `MagiPreviewMixer.test.ts`, `MagiSplitView.test.ts`, `splitViewSource.test.ts`, `magiCommandParse.test.ts`, `MagiLayoutPersistence.test.ts`.

Live thumb sample (`.runtime/_magi_12b_ingest_live.json`): video 3×200, image 3×200, audio 3× not used.

## Runtime

- Studio API **200** / Vite **200**
- **COMFY BEFORE:** PID 45624 healthy
- **COMFY AFTER:** PID 45624 healthy
- **COMFY RESTARTED?:** **NO**
- **WHY?:** Library/thumbs/mixer are API + Vite only.

## Regression freeze

MAGI color / upscale / four tracks / preview Fit / Timeline Library + References were not redesigned. Timeline References untouched.

## Limitations

- Agent browser cannot prove room speakers. Playback proof is mixer element state (play / mute / single stream).
- MUSIC/SFX were left empty after the CD finish (owner “no music”). Mixer is wired for those lanes when clips exist.
