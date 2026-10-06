# MAGI Active Graphics + Overlay System Certification

**Date:** 2026-09-14  
**Branch:** `feat/character-creator-final-closure`  
**HEAD (starting):** `99665cf76693e359cedc60c50c4405daf1b4e3a1`  
**Working tree:** this mission’s overlay reconnect + fade-burn repair (uncommitted at report time)  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Scene 12B:** `d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`  
**Published master:** `a85c2632-dd04-4450-be5d-214aa191e209` (`video_published_master`)  
**Overlay composition:** `e613491f-61b1-4eb1-a7d2-42867e1a95f4`  
**Review URL:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=magi&sceneId=d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`  
**Studio API:** `http://127.0.0.1:8758/` (`/api/healthz` HTTP 200)  
**Local creator UI:** `http://127.0.0.1:5173/` (HTTP 200)  
**Comfy `:8188`:** READ-ONLY. PID `45624` before and after. **COMFY RESTARTED?: NO**  
**API recycle:** `scripts/restart_studio_api_only.py` only (fade-burn + transparent-plate). Last healthy PID `30336`. Comfy PID unchanged.

This is the governing report for MAGI overlay **tools** (T / LT / Shape / IMG, inspector, timing, persist, burn plates).

**SIBLING (2026-09-15):** Track labels, max-2 Objects lanes, `objectsTrack`, and the frozen composition stack are governed by `MAGI_OBJECTS_TRACK_FINAL_CONVERGENCE.md`. GRAPHICS is a silent load/migrate alias only. Do not cite the GRAPHICS track stack in this file as current product truth.

`MAGI_SPLIT_VIEW_LIVE_GRADE_CERTIFICATION.md` remains the governing report for Split View live grade. Do not treat that GO as this graphics GO or as the Objects-track GO.

---

## OWNER LAW

MAGI is post-production finishing. Timeline keeps generation, Retake, and production decisions.

Visible Preview Monitor tools must be production controls. Decorative / proposal-only graphics buttons are a fail.

One canonical store:

`magi.graphics = overlays[]` on the published-master composition  
(`PUT /api/magi/projects/{id}/overlays/{compositionId}` → `data/image_product/{projectId}/overlays/`).

GRAPHICS track clips are a **display projection** (`gfx_${overlayId}`). They are not persisted into `sequence.clips`.

---

## TOOLBAR AUDIT (before reconnect)

| Control | First classification | After reconnect |
| --- | --- | --- |
| **T** | PARTIALLY WIRED (`queueProposal("overlay_text")`) | **EXISTS** — immediate `addText()` |
| **LT** | PARTIALLY WIRED (proposal) | **EXISTS** — immediate lower third |
| **▢** | PARTIALLY WIRED (proposal) | **EXISTS** — immediate shape |
| **IMG** | MISSING (overlapping-squares was Duplicate) | **EXISTS** — Library image picker |
| **⧉** | EXISTS — Duplicate | **EXISTS** — `duplicateSelected()` |
| **⌫** | EXISTS — Delete | **EXISTS** — `deleteSelected()` / Delete key (graphics only) |
| **Fit** | DISCONNECTED click; automatic contain | **EXISTS** as viewer **status** (`role="status"`). Not a dead button. Contain remains `MagiPreviewFitFrame`. |

No CRS / ERS / PRS / Retake / generation batch was added to MAGI.

---

## ARCHITECTURE

1. **One overlay document** — `text | lower_third (group) | vector | image`. Shared timing, transform, z-index, persistence, preview, and burn.
2. **Tracks** — VIDEO, GRAPHICS, AUDIO, MUSIC, SFX. `clipUnderPlayhead` skips GRAPHICS so the published master stays picture authority.
3. **Timing** — `startFrame` / `endFrame` on the overlay. Default create = 5s from playhead. Preview and FFmpeg `enable='between(t,START,END)'` use the same window.
4. **Viewer stack** — published video → live CSS grade → overlay layer. Overlays do not remount `<video>`.
5. **Split View** — LEFT = published master only (no grade, no graphics). RIGHT = same URL + live grade + overlay layer.
6. **Co-Director** — `magi.graphics.apply` writes this same `overlays[]`. MAGI reloads on `adept:codirector-project-mutated`.
7. **Final burn** — each top-level overlay → transparent PNG plate → timed FFmpeg overlay. Fade plates are **looped for the edit duration** so `fade=st=START` is not applied to a still whose only timestamp is `t=0`.

---

## LIVE SCENE 12B

Composition after Save (and after undo restored the title):

| Overlay | Type | Frames (24 fps) | z | Notes |
| --- | --- | --- | --- | --- |
| `txt-2qq5qye6` | text | 0–120 (0–5s) | 10 | `QUARTERS INTERVIEW` at x=0.10, y=0.10 |
| `grp-v3vh14s3` | lower_third | 120–240 (5–10s) | 20 | ANADRIYA / Current Adept, fade |
| `vec-4nvwzka1` | rounded_rectangle | 120–240 | −1 | Translucent plate behind LT |
| `img-zyek665m` | image | 120–240 | 30 | Library asset `8593f29e-…` (upper right) |

### Test A — Text

T created the title immediately on the monitor, GRAPHICS clip, and Text Inspector. Font / box edits updated live. Playhead at 5s hid the title (end-exclusive).

### Test B — Lower Third

LT at ~5s. GRAPHICS “Lower Third”. Inspector Name / Title. Visible only in 5–10s. Lower safe-area placement.

### Test C — Shape

Rounded rectangle on GRAPHICS. **Behind** set `zIndex = -1`. Shape sits under the lower third.

### Test D — Image overlay

IMG → MAGI Library (not Timeline References) → image selected → composited, movable, Inspector Fit = contain. Transparency retained on the PNG plate.

### Test E — Playback

Play through overlays. Title leaves at 5s; LT / shape / image appear; they leave after their window. Published master continued. Video element was not remounted. Volume control stayed intact. Video is muted when the AUDIO lane owns playback (`audioLaneOwnsPlayback`) — not a graphics remount.

### Test F — Split View

At ~2s: LEFT clean master; RIGHT same shot + `QUARTERS INTERVIEW`.  
At ~6s: LEFT clean; RIGHT grade path + LT bar + image chip.

### Test G — Save / reload

Reload returned GRAPHICS clips and the same overlay document (`GET …/overlays/by-asset/a85c2632-…`). Title at 0.10 / 0.10 after the undo restore.

### Test H — Final render

Proof script: `.runtime/_magi_graphics_proof.py`  
Uses production `_maybe_overlay` on an 8s extract of the Scene 12B published master. Audio copied (`hasAudio: true`).

| Artifact | Result |
| --- | --- |
| `docs/release-gate/magi-post/evidence/magi_graphics_scene12b_proof.mp4` | 864×480, 24 fps, ~8s, H.264 + AAC |
| `evidence/frame_02s_title.png` | Full **QUARTERS INTERVIEW** on the 12B master (not a black plate) |
| `evidence/frame_06s_lt.png` | Master + ANADRIYA / Current Adept + purple accent + dark bar + Library image UR |
| `evidence/frame_06s_original.png` | Clean master control |

**Root-cause repair (would have been NO-GO if left):** faded still PNGs were timestamped at `t=0`, so `fade=t=in:st=5` kept the entire lower-third group transparent. The visible 6s bar was only the separate shape. Fix: loop faded plates for the edit duration. Regression: `test_faded_overlay_stays_visible_mid_window`.

Font scale (`designCanvasWidth` vs render width) keeps 80px / 40px design sizes readable at 864×480.

Preview-profile MAGI jobs still burn only the first 3 seconds of the first clip — too short for the 5s LT. Test H used the production overlay burn, not that preview stub.

---

## DIRECT MONITOR EDITING

Pointer drag on the Preview Monitor moved `QUARTERS INTERVIEW` from `(0.10, 0.10)` to `(0.457, 0.386)` in video-normalized coordinates. NW / SE handles appeared. Inspector switched to Text.

Undo restored `(0.10, 0.10)`. Redo returned the dragged position. Second undo left the certified persist at `0.1 / 0.1`.

Coordinates are video-relative (`x`/`y`/`width`/`height` 0–1), not browser pixels.

---

## CO-DIRECTOR

`magi.graphics.apply` is registered (`definitions.py`, `registry.py`, `handlers/magi.py`). It appends `text | lower_third | shape | image` to the same overlay store. MAGI calls `overlays.reloadFromServer()` on `adept:codirector-project-mutated`.

`tests/test_codirector_magi_graphics_apply.py` — preview + apply + lower-third group.

Live NL chat send from this host was not executed (browser send blocked as an external message). No second CD graphics store exists.

---

## TESTS

**Frontend** (`studio-web` vitest): **14 passed**  
`MagiPlaybackContract.test.ts`, `MagiSplitView.test.ts`, `MagiEditorCommandStack.test.ts`, `graphicsClips.test.ts`  
(includes Fit-as-status contract and no `queueProposal` on T).

**Backend:** `tests/test_m42_w4b_overlays.py` **10 passed** (transparent plate + faded mid-window burn).  
`tests/test_codirector_magi_graphics_apply.py` included in the **13 passed** overlay+CD run.

Pre-existing: `test_magi_sequence_repairs.py::test_timeline_export_to_existing_batch_places_and_ledgers` 502 `TIMELINE_HANDOFF_FAILED` — not this mission.

---

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | T / LT / ▢ / IMG / drag / Undo / Save |
| Frontend | Immediate overlay create; GRAPHICS projection; Inspector context |
| API | `GET/PUT` overlay composition; no `gfx_*` in sequence save |
| Backend | Overlay validate (`image` + `assetId`); graphics track kind |
| Persistence | `overlays/e613491f-….json` |
| Runtime | Interactive CSS overlay; FFmpeg timed composite for final |
| Result | Preview + proof MP4 match timing / layering |
| Reload | Overlays and GRAPHICS clips return |
| Downstream | Split View MAGI pane; Co-Director same store |

---

## OWNER SCORECARD

| Field | Result |
| --- | --- |
| T TOOL | PASS |
| LOWER THIRD | PASS |
| SHAPE | PASS |
| IMAGE OVERLAY | PASS |
| GRAPHICS TRACK | PASS |
| DIRECT MONITOR EDITING | PASS |
| TIMING | PASS |
| Z-ORDER | PASS (Behind → z=−1) |
| INSPECTOR | PASS |
| UNDO/REDO | PASS (live drag undo/redo) |
| SAVE/RELOAD | PASS |
| NORMAL VIEWER | PASS |
| SPLIT VIEW ORIGINAL | PASS |
| SPLIT VIEW MAGI | PASS |
| PLAYBACK | PASS |
| AUDIO | PASS (no remount; proof has audio) |
| FINAL RENDER | PASS (composited proof frames) |
| CO-DIRECTOR | PASS (same-object apply path + tests; live NL chat not sent) |
| CONSOLE | PASS (no error banner; no captured overlay console errors) |
| REGRESSIONS | PASS (Split live-grade contract tests still green) |

---

## LIMITATIONS (honest, not blockers)

- MAGI **Preview** render profile still burns only the first 3 seconds of the first clip. Use Final profile or the production `_maybe_overlay` path for overlays after 3s.
- Official UI “Render” enqueue for a full Final job was not required; Test H called the same `_maybe_overlay` the job uses.
- Live Co-Director natural-language send was not completed from this host. Apply/reload are wired to the same overlay document.
- Fit is a contain status chip, not a Fit/Fill toggle.
- CSS grade remains the live preview; graphics burn is Pillow + FFmpeg, not a temporary baked movie on every drag.

---

## RUNTIME

```text
COMFY BEFORE: PID 45624 / GET :8188/system_stats HTTP 200
COMFY AFTER:  PID 45624 / GET :8188/system_stats HTTP 200
COMFY RESTARTED?: NO
WHY?: ordinary MAGI graphics work; API-only recycle
```

---

## FINAL VERDICT

**GO — MAGI ACTIVE GRAPHICS + OVERLAY SYSTEM CERTIFIED**
