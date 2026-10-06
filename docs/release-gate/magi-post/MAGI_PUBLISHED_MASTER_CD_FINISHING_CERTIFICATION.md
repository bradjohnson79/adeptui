# MAGI Published-Master Ingest + Co-Director Finishing — Certification

**Governing document (Law 30)** for published-master ingest and Co-Director-led MAGI finishing. Sibling reports: [`MAGI_LIBRARY_AUDIO_THUMBNAIL_CERTIFICATION.md`](MAGI_LIBRARY_AUDIO_THUMBNAIL_CERTIFICATION.md), [`MAGI_OLD_NEW_SPLIT_VIEW_CERTIFICATION.md`](MAGI_OLD_NEW_SPLIT_VIEW_CERTIFICATION.md). Does not replace MAGI finishing pipeline certification (`docs/release-gate/magi-finalization/05-MAGI_EDITOR_FINAL_COMPLETION_CERTIFICATION.md`).

| Field | Value |
| --- | --- |
| Date | 2026-09-14 (PT) / 2026-09-15 (UTC) |
| Branch | `feat/character-creator-final-closure` |
| HEAD SHA | `99665cf76693e359cedc60c50c4405daf1b4e3a1` (working tree; this mission uncommitted) |
| Project | **Korri Anadriya** `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` — reused, no new project |
| Scene 12B | `d774a22f-2b02-4eb2-b5ab-a98af9ff8f85` |
| Published master | `a85c2632-dd04-4450-be5d-214aa191e209` |
| Local creator UI | `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?tab=magi&sceneId=d774a22f-2b02-4eb2-b5ab-a98af9ff8f85` |
| Studio API | `http://127.0.0.1:8758/` |

## Verdict

**GO — MAGI CO-DIRECTOR-LED POST-PRODUCTION MASTERING CERTIFIED**

## Owner fields

| Field | Result |
| --- | --- |
| TIMELINE PUBLISHED MASTER | `a85c2632-…` tag `video_published_master`. **864×480**, 720 frames, **30.048s**, ~24 fps, AAC. SHA-256 `2b517495cd85e3c8e8fc42869e88c519f56c6e0d83a5d68b2572907852cac78d` — **unchanged** after ingest, color, and 2K upscale. |
| MAGI INGEST | `POST /api/magi/projects/{id}/scenes/{sceneId}/ingest-published-master` HTTP 200. Probe duration 720 frames / 30s (not 5s). Re-ingest **idempotent**. Unpublished scenes refused (`PUBLISHED_MASTER_REQUIRED`). |
| BATCH CLIPS PRESENT | **No.** Sequence clips after ingest: VIDEO `published_master` + AUDIO `published_master_audio` only. `batchLeftover: []`. |
| AUDIO EXTRACTION | Same published asset referenced on AUDIO (`ingestRole: published_master_audio`). No second file. `hasAudio: true`. |
| VIDEO TRACK | `video_published_master` / clip `clip_pubv_e6133ea6` / 720 frames / scene 12B. |
| AUDIO TRACK | `video_published_master — Audio` / clip `clip_puba_fcb43e28` / same asset + timing. |
| MUSIC TRACK | Empty after finish. CD override **no music**. |
| SFX TRACK | Empty after finish. CD override **keep original audio**. |
| CO-DIRECTOR VIDEO ANALYSIS | `analyze.video` resolver `_resolve_playable_video_asset_id` prefers `scenePublish.publishedAssetId`. Live 12B resolve = `a85c2632-…` (not Batch 1/2 / stitch). Unit: `test_published_master_wins_over_batch_and_output_path`. `magi.propose_finish` uses that published source. |
| COLOR DECISION | `cinematic_neutral` applied. Derived `magi_color` parent = published master. |
| AUDIO DECISION | Keep original audio. No EQ / limiter / de-ess engine invoked. |
| MUSIC DECISION | **None.** |
| SFX DECISION | **None.** |
| FRAME RATE DECISION | Source fps **reported only** (24). Not changed. `NOT_SUPPORTED` for interpolation. |
| UPSCALE DECISION | **2560×1440** FFmpeg lanczos. Job `08c924ab-89c5-4fd1-900e-36fc0ec90183` **done**. |
| ACTIONS APPLIED | `magi.color.apply` ok → `magi.upscale` queued/done. Receipts attached. `sourcePreserved: true`. |
| FINAL MEDIA | New Library video `695e1b83-e782-4518-8e96-c0e2e80d0da6` tag `magi_upscale`. File `upscale_e07b385dad.mp4`. **2560×1440**, duration **30.048s** (time-locked to source). |
| LIBRARY OUTPUT | Lineage: 2K → color `05f70bb0-…` → published `a85c2632-…`. `sameAsPublished: false`. Published path still on disk. `finishing.visualResultAssetId` = 2K. |

## Honest NOT_SUPPORTED (not faked)

Preview of `magi.propose_finish` listed:

- EQ, compression, limiter, de-ess
- 5.1 / spatial surround
- Frame interpolation / fps conversion

Readiness payload: `previewMix: real`, `notSupported: [eq, surround_5_1, frame_interpolation]`.

## Tests

Backend (this mission): `13 passed` — `test_magi_published_master_ingest.py`, `test_magi_propose_finish.py`, `test_analyze_video_resolution.py`, `test_gpu_apply_endpoint_fails_honestly`.

## Runtime

- Studio API `http://127.0.0.1:8758/api/healthz` **200**
- Vite `http://127.0.0.1:5173/` **200**
- **COMFY BEFORE:** PID **45624** healthy (`GET :8188/system_stats` 200)
- **COMFY AFTER:** PID **45624** healthy
- **COMFY RESTARTED?:** **NO**
- **WHY?:** MAGI ingest / FFmpeg color+upscale / Studio API only. Comfy left read-only.

## Limitations

- `magi.propose_finish` orchestrates existing MAGI tools from published-master + creator overrides. It does not invent EQ/5.1/fps engines.
- Omni/analyze.video is the inspect path (published master first). This live apply used the published source plus explicit “no music / keep original audio / 2K” overrides.
- Final 2K tag is `magi_upscale` (Library row + parent receipts). Example display name “MAGI Finished 2K Master” is not required to overwrite the Timeline publish.

## Scope freeze

Did not implement 5.1 / EQ / frame interpolation. Did not overwrite `a85c2632-…`. Did not regenerate Scene 12B on Timeline. Did not restart Comfy or MiniMax.
