# MAGI Old \| New Split View — Certification

**Governing document (Law 30)** for MAGI Split View (original vs current MAGI treatment). Sibling reports: [`MAGI_PUBLISHED_MASTER_CD_FINISHING_CERTIFICATION.md`](MAGI_PUBLISHED_MASTER_CD_FINISHING_CERTIFICATION.md), [`MAGI_LIBRARY_AUDIO_THUMBNAIL_CERTIFICATION.md`](MAGI_LIBRARY_AUDIO_THUMBNAIL_CERTIFICATION.md).

| Field | Value |
| --- | --- |
| Date | 2026-09-14 (PT) / 2026-09-15 (UTC) |
| Branch | `feat/character-creator-final-closure` |
| HEAD SHA | `99665cf76693e359cedc60c50c4405daf1b4e3a1` (working tree; this mission uncommitted) |
| Project | **Korri Anadriya** `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Scene 12B published master | `a85c2632-dd04-4450-be5d-214aa191e209` (864×480) |
| MAGI 2K bake | `695e1b83-e782-4518-8e96-c0e2e80d0da6` (2560×1440) |
| Review URL | `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?tab=magi&sceneId=d774a22f-2b02-4eb2-b5ab-a98af9ff8f85` |
| Evidence | `docs/release-gate/magi-post/evidence/12b_split_early_4s.png`, `12b_split_mid_15s.png`, `12b_split_late_27s.png` |

## Verdict

**GO — MAGI OLD | NEW SPLIT VIEW CERTIFIED**

## Owner fields

| Field | Result |
| --- | --- |
| COMPARE | **Preserved.** Tab still A vs B. Inspector **Compare asset** defaults to None. Empty copy: “Pick a compare”. Live: Compare selected → `splitPresent: false`. |
| SPLIT VIEW | **Implemented.** Tabs: Viewer \| Compare \| Split View. `MagiSplitView` + two `MagiVideoStage` + shared `timeSeconds` / `playing`. Labels **Original** \| **MAGI**. Default 50/50 + divider (20–80, double-click reset). No `autoPlay`. |
| ORIGINAL SOURCE | 1) `scenePublish.publishedAssetId` 2) `ingestRole: published_master` 3) walk MAGI visual parents and **stop at the published/ingest source** (do not walk Timeline stitch/draft). LEFT = raw `/file`, **filter: none**. Live LEFT: `a85c2632-…` **864×480**. |
| PROCESSED SOURCE | Authority: `finishing.visualResultAssetId` if descendant of LEFT; else playhead MAGI child; else original + live CSS. Live RIGHT: 2K `695e1b83-…` **2560×1440**, `filter: none` (baked cinematic_neutral; no extra CSS). |
| LIVE GRADE | CSS `filter` for brightness/contrast/saturation on Viewer / Split RIGHT only when `liveGrade` is true. Preset-only channels (temperature, teal/orange) labeled bake-only. |
| SYNC | Presentation time (seconds). Measured: both panes **4.000 / 15.00 / 27.00** with timecode `00:00:04:00` / `00:00:15:00` / `00:00:27:00`. Same framing at each beat. |
| FIT | Each pane wraps `MagiPreviewFitFrame`. 864×480 and 2560×1440 share the pane box. Fit pressed. No invented zoom/pan. |
| AUDIO | Both picture stages **muted**. One `MagiPreviewMixer` stream. |
| BEFORE / AFTER | `setViewerMode("split")` — never Compare. Chip kept. Source assertion in `MagiSplitView.test.ts`. |

## Scene 12B live (PASS)

Temporary sliders were available; after CD finish, Split View RIGHT is the **baked 2K** descendant (darker cinematic vs untreated LEFT).

| Beat | Timecode | Both panes `currentTime` | Picture |
| --- | --- | --- | --- |
| Early | `00:00:04:00` | 4.000 / 4.000 | Close-up two-shot; LEFT untreated, RIGHT graded 2K |
| Middle | `00:00:15:00` | 15.00 / 15.00 | Anadriya profile toward Korri; same lock |
| Late | `00:00:27:00` | 27.00 / 27.00 | Wider sofa two-shot; same lock |

**PASS.** Exact time sync, same framing, grade/treatment only on MAGI, no independent drift, one audio mix.

## Tests

- `splitViewSource.test.ts` — publish preference; walk stops at published (not stitch); 2K grandchild selected as processed; sibling not selected.
- `MagiSplitView.test.ts` — MagiVideoStage + timeSeconds; Before/After → split.

Frontend MAGI suite this pass: **26 passed**.

## Runtime

- Studio API **200** / Vite **200**
- **COMFY BEFORE:** PID 45624 healthy
- **COMFY AFTER:** PID 45624 healthy
- **COMFY RESTARTED?:** **NO**
- **WHY?:** Split View is frontend + existing MAGI derivatives.

## Limitations

- Agent Fullscreen API may be blocked; Expand/Fit remain the workspace resize path.
- FFmpeg-only preset look is baked on the 2K file, not faked live via LUT/WebGL.

## Scope freeze

Compare not replaced. Viewer not rebuilt. No second playback engine. Published master file not duplicated or overwritten.
