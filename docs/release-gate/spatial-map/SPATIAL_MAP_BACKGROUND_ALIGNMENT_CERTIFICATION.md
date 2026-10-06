# Spatial Map Freehand Align + Resize Calibration

**Governing document for this milestone.**

Restores Hand Tool (Freehand Align) and adds Resize so the Atlas can be moved and scaled under a stationary 1-meter circle/square grid. Environment Reference Sheets remain frozen to GPT Image 2 API only.

**Verdict:** `GO — SPATIAL MAP MANUAL ALIGNMENT + RESIZE CALIBRATION E2E CERTIFIED`

Prior Freehand-only string (superseded by this addendum): `GO — SPATIAL MAP FREEHAND ALIGNMENT TOOL RESTORED + E2E CERTIFIED`

ERS addendum (provider contract): **GO** — UI + route + handler refuse Qwen. A paid GPT Image 2 success image was not required for this calibration gate.

Native-aspect addendum (supersedes Atlas cover-crop): governing document is `SPATIAL_MAP_NATIVE_ASPECT_CALIBRATION_CERTIFICATION.md`. The Atlas is contain-fit at the source ratio. `_cover_atlas` / “cover-fit into the square” is no longer current truth. This document remains governing for Hand + Resize.

Rectangular viewport addendum (supersedes circular clip): governing document is `SPATIAL_MAP_RECTANGULAR_NATIVE_ASPECT_WORKSPACE_CERTIFICATION.md`. The 1-meter grid stays square; the workspace is no longer a circle.

Direct transform handles addendum: `SPATIAL_MAP_DIRECT_TRANSFORM_HANDLES_CERTIFICATION.md`. Resize is on-canvas corner handles on the Atlas bounds. Circle/slice-clamped handles and center-distance-only resize are superseded. The store remains `backgroundAlignment`.

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| HEAD SHA | `b6156455e643d5fa430784b3130756f2d8038651` (working tree includes this mission; not committed unless requested) |
| Named project | Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Live map | Venture Corridor Walk `7c7aac85-6932-4945-a13f-4a11fd69b79f` / Atlas `681cc247-8023-46dd-8e16-4446e60cae4e` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |
| Earlier cert map (historical) | Adept Stability / ERS Production Cert — superseded for this journey by Venture Corridor Walk |

Success string: `GO — SPATIAL MAP MANUAL ALIGNMENT + RESIZE CALIBRATION E2E CERTIFIED`

Failure string: `NO-GO — SPATIAL MAP MANUAL ALIGNMENT + RESIZE CALIBRATION INCOMPLETE`

---

## Classification

**Freehand Align:** DISCONNECTED + REGRESSED (never on committed HEAD schema). See prior section of this journey.

**Resize / atlas scale:** **MISSING** before this addendum. Never shipped. Nearby lookalikes that must not be reused:

| What | What it actually is |
| --- | --- |
| Placement Precision (`gridScale`) | Grid density only |
| Workspace − / + | Viewport CSS zoom `0.75…1.5` on `.spatial-map__viewport` |
| Entity `scale` | Character/prop size, not the Atlas |
| ERS cover-fit `scale` | Draw math, not a persistable Atlas transform until this addendum |

No historical Resize implementation existed to reconnect. Scale was added to the same `backgroundAlignment` object as Freehand.

---

## Architecture

```text
fixed 1-meter grid = spatial authority (does not move or scale)
Atlas background = one visual registration layer
characters / props / cameras = canonical grid / world placements
  (do not move or scale with the Atlas)
workspace zoom = view only; never writes backgroundAlignment
```

### Unified transform

```json
{
  "backgroundAlignment": {
    "offsetX": 0.0,
    "offsetY": 0.0,
    "scale": 1.0
  }
}
```

- Offsets: canvas fraction of the Spatial Map square. Clamp `±0.45`. Missing → `0`.
- Scale: unitless uniform multiplier. Clamp `0.1…8`. Missing / invalid → `1`.
- No rotation (none existed; do not invent one).
- Creator X/Y: integers in `ALIGNMENT_DISPLAY_SIZE` (480) pixels.
- Creator Size: percent (`100` = scale `1`).
- Render (scale about viewBox center so pan does not drift):

```text
translate(offsetPx, offsetPy) translate(cx, cy) scale(s) translate(-cx, -cy)
```

- `data-offset-x`, `data-offset-y`, `data-scale` on `[data-testid=spatial-map-atlas-layer]`.
- One store only. Do not add a second Freehand/Resize persist path.
- ERS compose (current): `_contain_atlas` letterbox/pillarbox, then the same center + offset. Markers stay unscaled. Historical `_cover_atlas` cover-fit is superseded.
- Scale stays out of `lineage_fingerprint` and in `placement_fingerprint`.

---

## UI

Below Placement Precision, above Grid / Circles / Labels:

```text
Placement Precision
Background Alignment (?)
[ Hand Tool ]  [ Resize ]  X  Y  Size  [ Reset Alignment ]
Grid  Circles  Labels  −  +
```

- Hand ON: grab cursor; drag moves only the Atlas; Resize turns off.
- Resize ON: teal active state; SE/NW/NE/SW handles clamped onto the visible circle; drag outward enlarges, inward reduces; aspect locked (uniform scale). Hand turns off.
- Place / Move turns Hand and Resize off.
- Workspace − / + changes `data-zoom` only.
- **Reset Alignment** writes `{0,0,1}` only. Does not remove the Atlas. Does not clear placements. This is the safe calibration reset.
- **Reset Map** (existing placement wipe, confirm required) now also writes `{0,0,1}` and keeps the Atlas asset. Do **not** accept that confirm on Venture — it still clears Korri / Anadriya / C1 coordinates.

---

## Tests (this run)

| Suite | Result |
| --- | --- |
| Pytest `test_background_alignment.py` + `test_ers_component_pipeline.py` | **13 passed** |
| Vitest `backgroundAlignment.test.ts` + `SpatialMapPanel.test.ts` | **18 passed** |
| Playwright `spatial-map-background-alignment.spec.ts` | **2 passed** (15.8s) on Venture Corridor Walk |
| Playwright `spatial-map-ers-generator.spec.ts` (prior addendum) | **2 passed** |

Playwright live flow (Korri / Venture Corridor Walk):

```text
open Standard Spatial → zoom workspace to 0.75
→ Resize ON → drag SE handle → atlas scale > 1.05
→ grid path + marker transform + workspace zoom unchanged
→ Resize OFF → Hand ON → pan (scale must stay)
→ Resize Size 140 → scale 1.4, offset kept
→ Hand fine-align → Save
→ Timeline → return → reload → scale 1.4 + offset persist
→ Reset Alignment → Save → {0,0,1}
→ Atlas asset + entity snapshot unchanged
```

---

## Live Venture leave-behind

After Playwright leftover offset was observed (`X −23 / Y 4 / Size 100`). **Reset Alignment** restored `{0,0,1}` without touching the Atlas. **Save Spatial Map** committed `version` / `savedVersion` **84 / 84**.

Assigned slots were intact; grid coordinates were empty when this continuation inspected the live document (`gridRow = -1`). That state predates Reset Alignment / Save (those paths only write `backgroundAlignment` or stamp `savedVersion`). Original walk coordinates from this journey were restored and saved:

| Entity | normalizedX | normalizedY |
| --- | --- | --- |
| Korri | `0.40` | `0.62` |
| Anadriya | `0.58` | `0.64` |
| C1 Mid Shot | `0.50` | `0.82` |

Live reload then showed Move (not Place) on Korri / Anadriya / C1, placement + camera markers on the grid, Size `100`, X/Y `0`, Atlas `681cc247-8023-46dd-8e16-4446e60cae4e`. Playwright now requires at least one placed character or camera so an empty-grid baseline cannot silently pass.

---

## ERS addendum

Contract: Spatial Map → ERS compiler → GPT Image 2 API (`gpt-image-2-kie` / `gpt-image-2-image-to-image`) only.

- UI: fixed provider, not a dropdown.
- Stored Qwen ERS choice remaps to GPT Image 2.
- Handler raises if Qwen is selected; unspecified defaults to GPT Image 2.
- Scene Creator Mini may still offer Qwen local. Atlas Image Engine remains a separate catalog.
- Co-Director Scene Review does not PATCH `backgroundAlignment`. It reads the calibrated map as current authority.

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
| User action | PASS — Resize + Hand + Size + Reset Alignment on Venture Corridor Walk |
| Frontend | PASS — Atlas-only translate/scale; grid/markers/zoom fixed; handles on the circle |
| API | PASS — PATCH `backgroundAlignment` `{offsetX, offsetY, scale}` |
| Backend | PASS — hydrate / clamp scale `0.1…8`; no placement mutation |
| Persistence | PASS — Save / navigate / reload / Reset Alignment → `{0,0,1}` |
| Runtime | PASS — Atlas asset unchanged; Comfy untouched |
| Result | PASS — map moves and resizes; grid stays |
| Reload | PASS — transform retained then Reset Alignment to default |
| Downstream | PASS — ERS packet includes full alignment; Scene Review does not overwrite it |

---

## Limitations

- Translation + uniform scale only. No independent map rotation.
- Resize handles are clamped onto the visible circle so they stay clickable.
- **Reset Map** still confirms and clears placements; use **Reset Alignment** for calibration-only reset.
- Workspace zoom is viewport-wide, not Atlas-only.
- Co-Director has no natural-language “nudge / resize the background” command.
- Working tree is not committed unless requested.
- ERS paid success image is a separate Kie/source-URL concern.

---

## Final verdict

**GO — SPATIAL MAP MANUAL ALIGNMENT + RESIZE CALIBRATION E2E CERTIFIED**
