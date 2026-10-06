# MAGI Objects Track Final Convergence

**Date:** 2026-09-15  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf76693e359cedc60c50c4405daf1b4e3a1` (working tree includes this Objects-track mission; uncommitted)  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Scene 12B:** `d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`  
**Published master:** `a85c2632-dd04-4450-be5d-214aa191e209` (`video_published_master`)  
**Overlay composition:** `e613491f-61b1-4eb1-a7d2-42867e1a95f4`  
**Review URL:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=magi&sceneId=d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`  
**Studio API:** `http://127.0.0.1:8758/` (`/api/healthz` HTTP 200, PID `13160`)  
**Local creator UI:** `http://127.0.0.1:5173/` (HTTP 200)  
**Comfy `:8188`:** READ-ONLY. PID `34484` before and after. **COMFY RESTARTED?: NO**  
**API recycle:** `scripts/restart_studio_api_only.py` only (overlay / sequence validation). Comfy PID unchanged.

This is the governing report for MAGI Objects tracks and the visual composition contract.

Sibling reports:

- Overlay **tools** (T / LT / Shape / IMG, inspector, timing, persist, burn plates) — `MAGI_ACTIVE_GRAPHICS_OVERLAY_CERTIFICATION.md`
- Split View live grade — `MAGI_SPLIT_VIEW_LIVE_GRADE_CERTIFICATION.md`
- MAGI final production (console / 4K honesty / CD music+SFX) — `MAGI_FINAL_PRODUCTION_CERTIFICATION.md`

Do not treat those GOs as this Objects-track GO.

---

## Frozen composition and track stack

Canonical visual composition (preview and final burn):

```text
Published Master → Live Grade → Objects 1 → Objects 2 → Viewer Guides
```

Viewer guides are **never** burned.

Permanent MAGI track stack (timeline top → bottom; higher = closer to camera):

```text
OBJECTS 2   (optional)
OBJECTS 1   (always; cannot remove)
VIDEO
AUDIO
MUSIC
SFX
```

Compositing:

```text
Objects 2  over  Objects 1  over  graded Video
```

Combined paint / burn order is `(objectsTrack, zIndex)`. Local `zIndex` is meaningful only inside the same Objects track.

GRAPHICS is a silent load/migrate alias to Objects 1. No creator UI, tip, track label, or Co-Director copy says GRAPHICS.

Canonical store remains `magi.graphics = overlays[]` on the published-master composition (`PUT /api/magi/projects/{id}/overlays/{compositionId}`). Sequence OBJECTS 1 / OBJECTS 2 lanes are structural + projection targets only. `gfx_*` clips are never persisted.

---

## Owner locks (verified)

| Lock | Result |
| --- | --- |
| Objects 2 always renders above Objects 1 | PASS — preview paint Z `2010` (logo) over `1020` (lower third); burn sort is `(objectsTrack, zIndex)` |
| GRAPHICS is alias only | PASS — no `GRAPHICS` string in the live MAGI chrome; migrate maps GRAPHICS / TEXT / T1 → OBJECTS 1 |
| OBJECTS 1 always exists | PASS — cannot remove; `+` lives on Objects 1 only |
| OBJECTS 2 via `+` or Co-Director only | PASS — default blueprint has Objects 1 only; max 2 |
| Remove Objects 2 = move-to-1 then drop | PASS — live: logo + LT landed on Objects 1; lane dropped; `+` returned |
| `gfx_*` never in `sequence.clips` | PASS — save + reload + sequence rev `46` persisted `[]` gfx / graphic rows |
| Preview / Split View architecture untouched | PASS — LEFT raw, no overlay layer; RIGHT existing overlay layer + live grade host |
| CD titles/LT → Objects 1; logo/watermark/bug → Objects 2 | PASS — `test_codirector_magi_graphics_apply` + `_resolve_objects_track` |

---

## Implementation (extend, not replace)

- `MagiTrackKind` `"objects"` + `objectsSlot?: 1 \| 2`
- `visibleMagiTracks` is an explicit stack builder (Objects 2 if present, Objects 1, Video, Audio, Music, SFX)
- Overlay field `objectsTrack: 1 \| 2` (default / missing → 1)
- `mergeGraphicsIntoSequence` projects `gfx_${overlayId}` onto the matching Objects track; `persistableSequenceClips` + backend `strip_projected_graphics_clips` strip before persist
- Timeline headers **OBJECTS 1** / **OBJECTS 2**; `data-testid="magi-objects-add-track"` / `magi-objects-remove-track` / `magi-track-objects-1|2`
- Clip move between Objects lanes patches overlay `objectsTrack` (does not write sequence clips)
- Final burn `_overlay_paint_key` sorts `(objectsTrack or 1, zIndex)`
- Co-Director tool id stays `magi.graphics.apply`; creator title/description say **Objects**

---

## Scene 12B live proof

Project reused (no new project). No Retake / CRS / batches / References.

| Overlay | Slot | Frames (24 fps) | zIndex | Notes |
| --- | --- | --- | --- | --- |
| `txt-2qq5qye6` QUARTERS INTERVIEW | Objects 1 | 0–48 | 10 | Off at ~5s |
| `grp-v3vh14s3` ANADRIYA / Current Adept | Objects 1 | 96–216 (4s–9s) | 20 | Visible at f118 |
| `img-zyek665m` Adept logo / bug | Objects 2 | 0–720 | 10 | Library image `0c7d967f-…` |
| Music — MAGI / Sfx — MAGI | MUSIC / SFX | kept | — | finishing.audio authority |

### A — Lower third on Objects 1

At `00:00:04:22` (f118) the monitor showed **ANADRIYA / Current Adept**. Overlay paint Z for the LT group was `1020` (`1 * 1000 + 20`). Title `QUARTERS INTERVIEW` was off (end 48).

### B — `+` creates OBJECTS 2 above Objects 1

While Objects 2 existed, `+` was hidden. After Remove, `+` (`magi-objects-add-track`, aria **Add Objects 2**) returned on Objects 1. Click restored:

```text
OBJECTS 2
OBJECTS 1
VIDEO
AUDIO
MUSIC
SFX
```

### C — Library logo on Objects 2

`img-zyek665m` sat on `magi-track-lane-objects-2` for the whole scene (0–720). At ~5s it painted at Z `2010` over the lower third and the published master.

### D — Move between Objects tracks

`handleMove` for `gfx_*` patches overlay `objectsTrack`. Live Remove moved every Objects 2 overlay onto Objects 1, then dropped the lane. After restore + reload, logo returned to Objects 2 and the lower third stayed on Objects 1.

### E — Play

Play from ~5s to `00:00:15:05`. Chrome showed **Playing**. Both Split View `<video>` elements used the same published-master URL and stayed `paused: false` (no remount). MUSIC and SFX clips remained on their lanes.

### F — Split View

At `00:00:04:22` / Split View tab selected:

| Pane | Overlay layer | Overlay nodes | ANADRIYA text | Grade filter |
| --- | --- | --- | --- | --- |
| LEFT `magi-split-original` | absent | 0 | no | `none` |
| RIGHT `magi-split-processed` | present | 6 | yes | existing live-grade host |

Screenshot: `docs/release-gate/magi-post/evidence/magi_objects_split_view_5s.png`

### G — Save + reload

Sequence revision **46**. Persisted `sequence.clips` contained **zero** `gfx_*` / `ingestRole: "graphic"` rows. After reload: OBJECTS 2 / OBJECTS 1 / VIDEO / AUDIO / MUSIC / SFX; logo on Objects 2; LT + title on Objects 1; music/SFX/published master kept.

### H — Final burn

`docs/release-gate/magi-post/evidence/magi_objects_12b_burn.mp4`  
`docs/release-gate/magi-post/evidence/magi_objects_overlap_5s.png` — both layers over video at ~5s  
`docs/release-gate/magi-post/evidence/magi_objects_offwindow_2s.png` — bug only (LT off-window)

Viewer guides are not in the file (guides are viewer-only).

### I — Overlap / combined order

Live stack at ~5s:

```text
OBJECTS 2  [Adept logo -----------------------------]
OBJECTS 1          [ANADRIYA lower third]
VIDEO      [Scene 12B --------------------------------]
```

Browser: logo Z `2010` over LT Z `1020`. Both visible over the published master.

Same-track proof (LT moved to Objects 2, `zIndex` 5 vs logo `zIndex` 10) recorded in `docs/release-gate/magi-post/evidence/magi_objects_track_same_track.json`:

```text
(2, 5)  Lower Third
(2, 10) Adept logo
```

That is local z-order on Objects 2, not the track stack. Overlap state was restored (LT Objects 1 / z 20, logo Objects 2 / z 10).

Remove Objects 2 screenshot: `docs/release-gate/magi-post/evidence/magi_objects_2_removed.png`

---

## Tests

| Suite | Result |
| --- | --- |
| `studio-web` vitest `objectsTracks.test.ts` + `tracks.test.ts` + `graphicsClips.test.ts` + `engine.test.ts` | **4 files, 19 passed** |
| `studio-api` pytest `test_m42_w4b_overlays.py` + `test_codirector_magi_graphics_apply.py` + `test_magi_sequence_repairs.py` | **48 passed, 1 failed** |

The single pytest failure is `test_timeline_export_to_existing_batch_places_and_ledgers` → `502 TIMELINE_HANDOFF_FAILED`. Pre-existing Timeline handoff; not an Objects-track regression.

Covered in the green set: default Objects 1 only, max-2, cannot remove Objects 1, Remove = drop Objects 2, `(objectsTrack, zIndex)` including same-track after a move, persistable clips never include `gfx_*`, empty sequence is OBJECTS 1 + VIDEO + AUDIO + MUSIC + SFX, PUT strips `gfx_*`, PUT rejects a third Objects track, CD title/LT → slot 1, CD logo → slot 2.

---

## E2E TRACE

| Stage | Verdict |
| --- | --- |
| User action | PASS — Objects headers, `+`, ×, Play, Split View, Library drop copy |
| Frontend | PASS — selected Objects slot, projection clips, no GRAPHICS chrome |
| API | PASS — overlay `objectsTrack` 1\|2; sequence `kind: objects` + `objectsSlot` |
| Backend | PASS — validate, strip projections, max 2, CD routing |
| Persistence | PASS — overlays[] + sequence tracks; rev 46; zero persisted `gfx_*` |
| Runtime | PASS — published master playback; burn uses same overlay document |
| Result | PASS — overlap at ~5s; off-window bug only; music/SFX intact |
| Reload | PASS — tracks, assignment, timing restored |
| Downstream | PASS — final burn stack; Split View LEFT raw / RIGHT objects |

---

## Limitations (honest, not blockers)

- Live same-track z-order used the overlay document + `_overlay_paint_key` / `compareOverlayPaintOrder`, not a completed pointer-drag in the browser (untrusted synthetic pointer events do not drive the timeline drag). The move handler is wired: `gfx_*` → `patchElement({ objectsTrack })`.
- Official MAGI Render Queue enqueue was not re-clicked this pass. Test H used the same `_maybe_overlay` / full-master burn path the job uses.
- Live Co-Director natural-language send was not repeated. Slot routing is covered by `magi.graphics.apply` tests and `_resolve_objects_track`.
- MAGI **Preview** render profile still burns only the first 3 seconds of the first clip (sibling overlay limitation). Final / production overlay path is the burn authority.
- Sequence storage still carries hidden extra lanes (V2, V3, I1, …). `visibleMagiTracks` does not show them. The frozen creator stack is the six-row list above.

---

## Runtime

```text
COMFY BEFORE: PID 34484 / GET :8188/system_stats HTTP 200
COMFY AFTER:  PID 34484 / GET :8188/system_stats HTTP 200
COMFY RESTARTED?: NO
WHY?: Objects-track layering + routing only; API recycle earlier in the mission; no GPU lifecycle action
API PID: 13160 (:8758 HTTP 200)
VITE: :5173 HTTP 200
```

---

## Verdict

**GO — MAGI OBJECTS TRACK FINAL CONVERGENCE**
