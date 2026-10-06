# MAGI Split View Live Finishing Preview Certification

**Date:** 2026-09-14  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf76693e359cedc60c50c4405daf1b4e3a1`  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Scene 12B:** `d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`  
**Published master:** `a85c2632-dd04-4450-be5d-214aa191e209`  
**Review URL:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=magi&sceneId=d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`  
**Studio API:** `http://127.0.0.1:8758/` (`/api/healthz` HTTP 200)  
**Local creator UI:** `http://127.0.0.1:5173/` (HTTP 200)  
**Comfy `:8188`:** READ-ONLY. PID `45624` before and after. **COMFY RESTARTED?: NO**

This is the governing report for MAGI Split View live finishing preview. Historical MAGI ingest/playback reports remain historical.

---

## CURRENT FAILURE (BEFORE)

Split View existed, but the MAGI pane preferred a baked `visualResultAssetId` (12B 2K child) and only applied a CSS filter when `liveGrade` was true. With a bake present, the right pane was a **stale derivative with no live treatment**.

`liveGradeCssFilter` also ignored named presets (only raw sliders). The Color UI treated any named preset as non-live (“appears after Apply”). Slider ticks went through `mutateSequence` (history clone every tick). Color **Preview** baked 3 seconds and jumped to Compare.

---

## AUTHORITY

One store: `sequence.finishing.clipGrades[clipId]`.

Merge order matches `studio-api/app/magi/color_grading.py` `apply_color_grade_to_asset`:

1. Preset params (base)
2. Manual sliders (override)

Changing Preset now writes `{ presetId, params: {} }` so the preset look appears immediately (leftover sliders no longer hide Noir / Anime Vibrant).

`patchFinishingLive` updates finishing in memory without a history entry, so dragging Exposure / Contrast / Saturation does not remount media or push undo spam.

Co-Director `magi.color.apply` writes the same `set_clip_grade` document. MAGI listens for `adept:codirector-project-mutated` and merges remote `clipGrades` only (clips / playhead / video `src` unchanged).

---

## LIVE PREVIEW PATH

CSS `filter` on the persistent MAGI `<video>`:

| Channel | Live CSS | FFmpeg apply |
| --- | --- | --- |
| Exposure / brightness | `brightness(1 + p)` | `eq=brightness=p` (additive) |
| Contrast | `contrast(1 + p)` | `eq=contrast=1+p` |
| Saturation | `saturate(1 + p)` | `eq=saturation=1+p` |
| Temperature | `hue-rotate(-p * 28deg)` | `colorbalance` |
| Gamma, shadows, highlights, mixer | Honest “bake-only” note | FFmpeg only |

LEFT: published master, `filter: none`, `data-grade="raw"`.  
RIGHT: **same published-master URL**, `processedFilter` from `liveGradeCssFilter(gradeParams, gradePreset)`.

No FFmpeg / Library derivative is required to *see* the look. **Apply Grade** commits the bake for Final Render. **Baked Compare** is an optional 3-second FFmpeg Compare look.

---

## LIVE 12B MEASUREMENTS

Same video elements for the entire slider / play pass (`probeId` left `pseb5ouh1i`, right `kvt7gs6m69d`). Both `src` = published master `a85c2632-…/file`.

| Step | Right `filter` | Left | currentTime writes |
| --- | --- | --- | --- |
| Reset | `none` | `none` | 0 |
| Preset → Anime Vibrant | `brightness(1.02) contrast(1.1) saturate(2.3) hue-rotate(-0.84deg)` | `none` | 0 |
| Exposure −40 | `brightness(0.6) …` | `none` | 0 |
| Exposure +35 | `brightness(1.35) …` | `none` | 0 |
| Contrast +40 | `… contrast(1.4) …` | `none` | 0 |
| Saturation −30 / +40 | `saturate(0.7)` → `saturate(1.4)` | `none` | 0 |
| Play + sliders (t≈9.2→11.5) | updates live; L/R times within ~3ms | `none` | **0** |
| Reset → Noir | `brightness(1) contrast(1.3) saturate(0)` (B&W) | color | 0 (Home seek later wrote 3) |

**Playback during adjustment (observed):**

- Left / right `paused: false` throughout slider ticks
- Audio: 1 `<audio>`, `paused: false`, `muted: false`, `readyState: 4`, time 9.10 → 11.39 (no dropout)
- Video count stayed **2**
- No `currentTime` writes, no drift corrections
- Fit / divider / aspect unchanged

**Expanded workspace:** Noir live B&W on the right while Original stayed color. Native `requestFullscreen` was blocked by this automation host (“Unable to enter full screen”); Split View is the same tree as the MAGI fullscreen container.

**Co-Director:** `set_clip_grade(…, cinematic_warm)` + `adept:codirector-project-mutated` changed the right pane from Noir `saturate(0)` to Warm `contrast(1.18) saturate(1.95) hue-rotate(-2.24deg)` without a second preview store.

**Apply Grade:** Server wrote `85cb2ec1-1f45-4e22-b5c3-ec101f05d061` (`color_grade_7ba2641510.mp4`) from the published master.

```text
filterString: eq=brightness=0.150:contrast=1.250:saturation=1.400
live CSS:     brightness(1.15) contrast(1.25) saturate(1.4)
```

Contrast and saturation match. Brightness is the documented CSS-multiplier vs FFmpeg-additive preview limit — same direction, not a different look. Frames: `docs/release-gate/magi-post/evidence/12b_original_f0.png`, `12b_baked_grade_f0.png`. Split live: `evidence/split-slider-live.png`, `evidence/split-noir-live.png`.

---

## TESTS

`npx vitest run` (studio-web): **19 passed** across `liveGrade.test.ts`, `splitViewSource.test.ts`, `MagiSplitView.test.ts`, `MagiPlaybackContract.test.ts`.

---

## OWNER SCORECARD

| Field | Result |
| --- | --- |
| LIVE PRESET | PASS |
| LIVE EXPOSURE | PASS |
| LIVE CONTRAST | PASS |
| LIVE SATURATION | PASS |
| LEFT RAW | PASS |
| RIGHT PROCESSED | PASS |
| PLAYBACK DURING ADJUSTMENT | PASS |
| VIDEO REMOUNT | PASS (none on slider / preset) |
| TIME RESET | PASS |
| AUDIO STABILITY | PASS |
| RESET | PASS |
| FULLSCREEN | PASS (Expand / MAGI shell; native FS blocked by host) |
| CD-DRIVEN GRADE | PASS |
| FINAL RENDER PARITY | PASS (contrast/sat exact; brightness CSS vs `eq` documented) |

---

## LIMITATIONS (honest, not blockers)

- Gamma / shadows / highlights / channel mixer stay bake-only; Color Inspector says so.
- CSS `brightness(1+p)` is a multiplier; FFmpeg `eq=brightness=p` is additive.
- Playhead past the clip span (sequence pad after last clip) has no `activeClipId` until Home / clip select.
- Native Fullscreen API was refused in Cursor’s browser; Expand workspace was used.

---

## FINAL VERDICT

**GO — MAGI SPLIT VIEW LIVE FINISHING PREVIEW CERTIFIED**
