# Spatial Map Native-Aspect Calibration

**Governing document for this addendum.**

Spatial Map must render the Atlas at the source asset’s natural aspect ratio. The circular/square placement grid stays the calibration frame. The map image is not cropped, stretched, or normalized to 1:1 merely to fill that frame.

**Verdict:** `GO — SPATIAL MAP NATIVE-ASPECT CALIBRATION E2E CERTIFIED`

Prior alignment cert remains governing for Hand + Resize: `SPATIAL_MAP_BACKGROUND_ALIGNMENT_CERTIFICATION.md`. Cover-crop / `_cover_atlas` language in that document is superseded by this addendum.

Rectangular viewport addendum (supersedes circular clip / Circles chrome): governing document is `SPATIAL_MAP_RECTANGULAR_NATIVE_ASPECT_WORKSPACE_CERTIFICATION.md`. The workspace is a rectangle at the source aspect. This document remains governing for contain-fit native ratio.

Direct transform handles addendum: `SPATIAL_MAP_DIRECT_TRANSFORM_HANDLES_CERTIFICATION.md`. Corner handles sit on the Atlas image bounds and write the same `backgroundAlignment` object.

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| HEAD SHA | `b6156455` (working tree includes this mission; not committed unless requested) |
| Named project | Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Proof maps | Native Aspect 4:3 `04017ede-ee4e-42af-9401-6c0b940ea4f2` (atlas `d435dcdc-795d-45ce-8c5f-7489a152be70`, 800×600) |
|  | Native Aspect 16:9 `94494dec-8041-497a-941c-8f2add22d865` (atlas `7a70d734-69d7-4b83-ac1e-61850aa36bb8`, 1280×720) |
| Production map (leave-alone) | Venture Corridor Walk `7c7aac85-6932-4945-a13f-4a11fd69b79f` / Atlas `681cc247-8023-46dd-8e16-4446e60cae4e` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |

Success string: `GO — SPATIAL MAP NATIVE-ASPECT CALIBRATION E2E CERTIFIED`

Failure string: `NO-GO — SPATIAL MAP NATIVE-ASPECT CALIBRATION INCOMPLETE`

---

## Classification

**Forced square crop of the Atlas:** REGRESSED / WRONG before this addendum.

| Layer | Defect |
| --- | --- |
| `SpatialGrid.tsx` | `<image width={size} height={size} preserveAspectRatio="xMidYMid slice">` cover-cropped into the square viewBox |
| ERS compose | `_cover_atlas` used `max(size/sw, size/sh)` into a square |
| CSS | `.spatial-map__grid-wrap { aspect-ratio: 1/1 }` is the **grid workspace**, not a license to square-crop the picture |
| Persist | Transform stored `{offsetX, offsetY, scale}` only — no source width / height / aspect |

The 1-meter circle/square grid remains the spatial authority. That workspace may stay square. The picture must contain-fit inside it.

---

## Architecture

```text
source width / source height
  → native aspect
  → contain-fit rectangle inside the square viewBox
  → full image bounds visible (letterbox / pillarbox)
  → initialize transform from that natural ratio

fixed 1-meter grid = spatial authority (does not move or scale)
Atlas background  = visual registration layer at native aspect
workspace zoom    = viewport CSS only; never writes backgroundAlignment
Freehand Align    = position only
Resize            = uniform scale; aspect locked
```

### Canonical transform

```json
{
  "backgroundAlignment": {
    "offsetX": 0.0,
    "offsetY": 0.0,
    "scale": 1.0,
    "sourceWidth": 800,
    "sourceHeight": 600,
    "sourceAspectRatio": 1.3333333333333333
  }
}
```

- Offsets: canvas fraction of the Spatial Map **square**. Clamp `±0.45`.
- Scale: unitless uniform multiplier about viewBox center. Clamp `0.1…8`.
- `sourceWidth` / `sourceHeight`: measured native pixels. `0` = unknown until load.
- `sourceAspectRatio`: `width / height` when both > 0, otherwise `1`.
- No rotation (none existed; do not invent one).
- Do **not** persist a fake square crop as canonical map state.
- PATCH that omits source dims must **keep prior** measured source (Hand/Resize afterEach safety).
- Reset Alignment writes `{0,0,1}` and **keeps** source width/height/aspect.
- Reset Map still wipes placements. Do **not** accept that confirm on Venture.

### Render

```text
containRect(size, aspect) → {x, y, w, h}
image: preserveAspectRatio="xMidYMid meet"
layer:  translate(offset) translate(cx,cy) scale(s) translate(-cx,-cy)
grid / markers: unscaled, untranslated
```

ERS compose uses `_contain_atlas` (`min(size/sw, size/sh)` letterbox/pillarbox), then the same offset + scale.

---

## Live proof (required 4:3 + 16:9)

Playwright `tests/e2e/codirector/spatial-map-native-aspect.spec.ts` — **2 passed**.

| Map | Source | `data-fit` | `data-aspect` | Image box (not 1:1) | After Resize Size 130 | After Hand | Save / reload |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Native Aspect 4:3 | 800×600 | contain | ≈1.333 | 1598×1198.5 | scale 1.3, aspect held | position only | source + scale persist |
| Native Aspect 16:9 | 1280×720 | contain | ≈1.778 | 1598×898.9 | scale 1.3, aspect held | position only | source + scale persist |

Live API after Playwright + visual open:

```text
Native Aspect 4:3   scale=1.3  src=800×600    aspect=1.333  ox≈0.022  oy≈0.009
Native Aspect 16:9  scale=1.3  src=1280×720   aspect=1.778  ox≈0.022  oy≈0.009
```

Browser (Vite `:5173`, Korri project):

- 16:9 blue plate is a wide rectangle inside the circle (letterbox top/bottom). Grid squares stay square. Circles stay round.
- 4:3 orange plate is a shorter landscape rectangle (taller than 16:9, still not square). No stretch. No square crop.
- Size field `130` = scale `1.3`. Hand Tool still moves X/Y only.

Venture Corridor Walk was opened read-only for source measure. **Reset Map was not accepted.** Placements stayed:

| Entity | normalizedX | normalizedY |
| --- | --- | --- |
| Korri | `0.40` | `0.62` |
| Anadriya | `0.58` | `0.64` |
| C1 Mid Shot | `0.50` | `0.82` |

Opening Venture persisted native Atlas `1536×1024` (aspect `1.5`) and kept leftover Size `75` (`scale=0.75`). That scale predates this addendum.

---

## Tests (this run)

| Suite | Result |
| --- | --- |
| Pytest `test_background_alignment.py` + `test_ers_component_pipeline.py` | **15 passed** |
| Vitest `backgroundAlignment.test.ts` | **10 passed** |
| Playwright `spatial-map-native-aspect.spec.ts` | **2 passed** (8.4s + 6.6s) |

---

## Runtime

- `http://127.0.0.1:8758/api/healthz` → 200
- `http://127.0.0.1:5173/` → 200
- `GET http://127.0.0.1:8188/system_stats` → 200 (leave-alone)

**COMFY BEFORE:** PID **69108**, health 200  
**COMFY AFTER:** PID **69108**, health 200  
**COMFY RESTARTED?:** NO  
**WHY?:** Ordinary UI/API Spatial Map work. No supervisor restart.

---

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — open 4:3 and 16:9 maps; Resize Size 130; Freehand pan; Save |
| Frontend | PASS — contain-fit; `data-fit=contain`; image W≠H; grid path unchanged |
| API | PASS — PATCH includes sourceWidth / sourceHeight / sourceAspectRatio |
| Backend | PASS — hydrate + clamp; PATCH merge keeps prior source; ERS contain |
| Persistence | PASS — 800×600 / 1280×720 + scale 1.3 after reload |
| Runtime | PASS — Comfy untouched; Venture placements untouched |
| Result | PASS — native ratio, no stretch, no square crop |
| Reload | PASS — ratio + transform survive |
| Downstream | PASS — ERS `_contain_atlas` letterbox; Scene Review does not overwrite alignment |

---

## Limitations

- Translation + uniform scale only. No independent map rotation.
- The workspace / clip path remains a circle inside a square. That is the grid frame, not a crop of the picture.
- Resize handles stay clamped onto the visible circle so they remain clickable.
- **Reset Map** still confirms and clears placements; use **Reset Alignment** for calibration-only reset.
- Working tree is not committed unless requested.

---

## Final verdict

**GO — SPATIAL MAP NATIVE-ASPECT CALIBRATION E2E CERTIFIED**
