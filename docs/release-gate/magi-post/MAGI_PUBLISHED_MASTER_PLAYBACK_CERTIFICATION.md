# MAGI Published-Master 409 + Smooth Playback Certification

**Date:** 2026-09-14  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf76693e359cedc60c50c4405daf1b4e3a1`  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Review URL:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=magi&sceneId=d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`  
**Studio API:** `http://127.0.0.1:8758/` (recycled only; new PID `22768`)  
**Comfy `:8188`:** READ-ONLY. PID `45624` before and after. **COMFY RESTARTED?: NO**

This is the governing report for this repair. Historical MAGI ingest/finishing reports remain historical.

---

## PUBLISHED MASTER ROOT CAUSE

**A — URL sceneId was not required to be the published Timeline scene, while MAGI is project-scoped.**

MAGI keeps one sequence per project. Scene 12B was already correctly bound:

- VIDEO `published_master` → `a85c2632-dd04-4450-be5d-214aa191e209`
- AUDIO `published_master_audio` → same asset
- `finishing.activeSceneId` → 12B

Opening MAGI with any *other* project `sceneId` (commonly Scene 1 via last-selected workspace scene) called ingest for that unpublished scene. Timeline `scenePublish.publishedAssetId` is empty there, so the API returned **409 `PUBLISHED_MASTER_REQUIRED`** even though the Preview Monitor was showing the real 12B master.

Clip label `video_published_master` was never treated as publication proof. The 409 was an honest unpublished lookup on the **wrong scene**.

A second defect made the banner unreadable: `req()` read MAGI `{ detail: { error: { message } } }` as a flat object and used the **raw JSON body** as `Error.message`.

Unpublished scenes with no correctly bound published master still 409. The guard was not weakened.

---

## IDs

| Field | Value |
| --- | --- |
| URL SCENE ID | `d774a22f-2b02-4eb2-b5ab-a98af9ff8f85` (12B — Quarters Interview) |
| SCENEPUBLISH ID | Embedded on 12B master (`scenePublish.version=1`, publishedAt `2026-09-14T02:46:25Z`) |
| PUBLISHED ASSET ID | `a85c2632-dd04-4450-be5d-214aa191e209` |
| VIDEO TRACK ASSET | `a85c2632-dd04-4450-be5d-214aa191e209` (`ingestRole=published_master`) |
| AUDIO TRACK SOURCE | `a85c2632-dd04-4450-be5d-214aa191e209` (`ingestRole=published_master_audio`) |
| LINEAGE RESULT | published master ← stitch `9170c85b-…` ← MiniMax H3 draft `3277533f-…` |

Only 12B of 14 Korri scenes has `publishedAssetId`. All five contract slots agree for 12B.

---

## 409 BEFORE / AFTER

**409 BEFORE:** Scene 1 ingest → HTTP 409, raw JSON banner, while 12B master stayed on the tracks. 12B ingest was already 200/idempotent.

**409 AFTER:**

- 12B ingest → 200, no banner
- Scene 1 ingest while 12B is correctly bound → 200 `alignedSceneId=12B` (frontend rewrites `sceneId`)
- Fresh unpublished scene with no bound published master → **still 409** (`test_ingest_rejects_unpublished_scene`)
- Creator unpublished copy: “This scene has not been published from Timeline yet.” + Open Timeline. No nested JSON.

---

## PLAYBACK CLOCK BEFORE / AFTER

**BEFORE:** `setInterval` incremented `sequence.playheadFrame` every frame and listed `sequence` as a dependency, tearing down the timer every tick. `MagiVideoStage` / mixer wrote `currentTime` whenever drift exceeded **80ms**. Classic seek-on-every-tick stutter. Compare videos used independent `autoPlay loop`.

**AFTER:** Primary video (Viewer / Split left / Compare left) is the clock authority. Playhead follows `requestAnimationFrame` media time. `currentTime` writes only on user scrub (`seekGeneration`) or drift **> 300ms**. AUDIO / MUSIC / SFX follow the same rule. Video stays muted when the AUDIO lane owns the stem.

---

## LIVE MEASUREMENTS (Scene 12B)

| Metric | Observed |
| --- | --- |
| CURRENTTIME WRITES (20s play) | **0** |
| SEEK LOOP | **NO** |
| DUPLICATE VIDEO ELEMENTS (Viewer) | **1** authority |
| EMBEDDED AUDIO | Video **muted** |
| AUDIO TRACK | **1** `<audio>`, playing, ~130ms of video (under threshold, no correction) |
| SYNC STRATEGY | Video clock + bounded drift (0.3s). Audio follows. |
| REACT REMOUNTS | Same `<video>` identity during play; no playhead/grade keys |
| DROPPED/STUTTER RESULT | `getVideoPlaybackQuality().droppedVideoFrames = 0` / 649 decoded. Time advanced 20.05s in 20.05s wall. No pause/jump/reset. |
| Scrub 5 / 10 / 20 | `currentTime` 5.00 / 10.00 / 20.00. **2 writes per scrub** (video + audio). Then Play from 20 → 22.96 after 3s. |
| Drawers while playing | Bins + Inspector toggle. Playback continued; writes unchanged; drift 0. |
| Compare | 1 transport-bound video (no second compare asset). Exit → Viewer 1 authority. |
| Split View | 2 videos (authority + follower) both 2.4s. Exit → Viewer 1 authority at 2.7s. |
| Console / network | **0** 409, **0** ingest during play, **0** JSON banners |

LIVE 20s PLAYBACK: **PASS**

---

## TESTS

- Backend: `test_magi_published_master_ingest.py` → **6 passed** (including align-when-bound + unpublished still 409)
- Frontend: `magiPlaybackClock`, `MagiPlaybackContract`, `MagiPreviewMixer`, `MagiSplitView`, `errors`, `api.detail`, `splitViewSource` → **28 passed**

---

## FILES

- `studio-api/app/magi/published_master_ingest.py` — align to Timeline-verified bound master
- `studio-api/tests/test_magi_published_master_ingest.py`
- `studio-web/src/api.ts` — unwrap MAGI error envelope; never surface raw JSON
- `studio-web/src/magiSequence/errors.ts` — `PUBLISHED_MASTER_REQUIRED` creator copy
- `studio-web/src/components/magi/magiPlaybackClock.ts` + tests
- `studio-web/src/components/magi/MagiVideoStage.tsx`
- `studio-web/src/components/magi/MagiPreviewMixer.tsx`
- `studio-web/src/components/magi/MagiSplitView.tsx`
- `studio-web/src/components/magi/MagiPreviewFitFrame.tsx`
- `studio-web/src/components/magi/MagiEditorWorkspace.tsx`
- `studio-web/src/components/magi/magi-editor.css`

---

## LIMITATIONS

- Genuine unpublished MAGI open (empty sequence, no bound published master) still 409s by design. Live Korri cannot demonstrate that banner without wiping the 12B sequence; unit/HTTP tests cover it.
- Compare without a second Inspector asset shows one video. That is not a hidden Viewer player.
- Live grade remains CSS filter on the persistent video element.

---

## COMFY

```text
COMFY BEFORE: PID 45624 / health 200
COMFY AFTER:  PID 45624 / health 200
COMFY RESTARTED?: NO
WHY?: Ordinary MAGI API + frontend repair. Studio API recycle only.
```

---

## FINAL VERDICT

**GO — MAGI PUBLISHED-MASTER + SMOOTH PLAYBACK CERTIFIED**
