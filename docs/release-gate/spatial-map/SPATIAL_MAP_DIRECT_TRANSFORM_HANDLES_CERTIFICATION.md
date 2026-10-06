# Spatial Map Direct Transform Handles

**Governing document for this addendum.**

The Spatial Map image is selected and resized on the canvas, like a picture in Photoshop: a bounding box on the image itself, four corner handles, locked aspect, one transform store.

**Verdict:** `GO — SPATIAL MAP DIRECT TRANSFORM HANDLES + PHOTOSHOP-STYLE RESIZE E2E CERTIFIED`

Prior certs remain governing for their own gates:

- Hand + Resize store: `SPATIAL_MAP_BACKGROUND_ALIGNMENT_CERTIFICATION.md`
- Native-aspect contain-fit: `SPATIAL_MAP_NATIVE_ASPECT_CALIBRATION_CERTIFICATION.md`
- Rectangular workspace: `SPATIAL_MAP_RECTANGULAR_NATIVE_ASPECT_WORKSPACE_CERTIFICATION.md`

Superseded by this addendum: circle/slice-clamped handle positions; center-distance-only resize that did not pin the opposite corner; Resize as a separate +/- abstraction.

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| HEAD SHA | `b6156455` (working tree includes this mission; not committed unless requested) |
| Named project | Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Proof maps | Native Aspect 16:9 `94494dec-8041-497a-941c-8f2add22d865` · Native Aspect 4:3 `04017ede-ee4e-42af-9401-6c0b940ea4f2` |
| Production map (leave-alone) | Venture Corridor Walk `7c7aac85-6932-4945-a13f-4a11fd69b79f` / Atlas `681cc247-8023-46dd-8e16-4446e60cae4e` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |

Success string: `GO — SPATIAL MAP DIRECT TRANSFORM HANDLES + PHOTOSHOP-STYLE RESIZE E2E CERTIFIED`

Failure string: `NO-GO — SPATIAL MAP DIRECT TRANSFORM HANDLES INCOMPLETE`

---

## Canonical transform (unchanged fields)

```json
{
  "backgroundAlignment": {
    "offsetX": 0.0,
    "offsetY": 0.0,
    "scale": 1.0,
    "sourceWidth": 1280,
    "sourceHeight": 720,
    "sourceAspectRatio": 1.7777777777777777
  }
}
```

- One store. Handle drag writes `scale` (uniform). Offset may shift so the **opposite corner stays put**.
- Aspect stays locked. 16:9 stays 16:9. 4:3 stays 4:3. No free-transform modifier in this addendum.
- Grid stays fixed. Workspace zoom is view-only.
- Reset Alignment restores `{0, 0, 1}` and keeps source W/H/aspect. Handles return to the native-aspect corners.

---

## Interaction

```text
Select the picture
→ dashed box on the image bounds
→ four corner handles (NW / NE / SW / SE)
→ drag a corner out to enlarge, in to shrink
→ drag inside the picture (Freehand) to slide it
→ Resize button only shows/activates these handles
```

- Deselect hides handles. Transform is unchanged.
- Handles are HTML hit targets on the image corners so they stay clickable at workspace zoom.
- Window-level pointer tracking continues a drag after the pointer leaves the SVG (corners sit on the viewport edge at scale `1`).
- Selecting a map in the dropdown is not overwritten by a late “most recent map” load.

---

## Live proof

Playwright `tests/e2e/codirector/spatial-map-direct-transform-handles.spec.ts` — **2 passed** (13.6s).

| Step | 16:9 | 4:3 |
| --- | --- | --- |
| Select map → bbox + four handles | PASS | PASS |
| Drag SE outward → scale up, aspect held | PASS | PASS |
| Drag NW inward → scale down, aspect held | PASS | PASS |
| Freehand move → scale held, offset changes | PASS | PASS |
| Resize again | PASS | PASS |
| Save → Library → return / reload | PASS | PASS |
| Source W×H / aspect persist | 1280×720 / 1.778 | 800×600 / 1.333 |

Live browser (Vite `:5173`, Korri, Native Aspect 16:9, Resize on, Reset Alignment): dashed box on the image, four corner handles, `data-aspect=1.777…`, `scale=1`, `offset=0`.

Regression (this run):

| Suite | Result |
| --- | --- |
| Vitest alignment + geometry + panel | **51 passed** |
| Playwright direct handles | **2 passed** (13.6s) |
| Playwright background alignment (help + opposite-anchor threshold) | **2 passed** |
| Playwright native aspect | **2 passed** (12.2s) |
| Playwright rectangular viewport | **1 passed** |

Venture after this mission: scale `0.75`, source 1536×1024. Reset Map was not used.

The 16:9 calibration plate `7a70d734-69d7-4b83-ac1e-61850aa36bb8` was restored when that map had been pointed at a Venture duplicate. Do not treat that duplicate as the 16:9 plate.

---

## Runtime

- `http://127.0.0.1:8758/api/healthz` → 200
- `http://127.0.0.1:5173/` → 200
- `GET http://127.0.0.1:8188/system_stats` → 200 (leave-alone)

**COMFY BEFORE:** PID **69108**, health 200  
**COMFY AFTER:** PID **69108**, health 200  
**COMFY RESTARTED?:** NO  
**WHY?:** Frontend handle/selection work only. No supervisor restart.

---

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — select map; corner drag; Freehand; Save; leave; return |
| Frontend | PASS — bbox + four handles on image bounds; Resize activates them |
| API | PASS — existing `backgroundAlignment` PATCH / Save |
| Backend | PASS — one transform object; source W/H/aspect kept |
| Persistence | PASS — scale + offset + aspect survive Library / reload |
| Runtime | PASS — Comfy untouched; Venture placements untouched |
| Result | PASS — locked-aspect Photoshop-style resize |
| Reload | PASS — exact scale/position return |
| Downstream | N/A — calibration only; no Scene Creator rewrite |

---

## Limitations

- At scale `1` the image corners sit on the visible frame. Dragging a corner **out** needs a little screen room (workspace zoom out, or drag once the image is inset). Window listeners keep the drag alive off-canvas.
- Offset clamp `±0.45` can fight the opposite-corner pin near the limit.
- Size / X / Y fields remain as numeric backup. They are not the primary resize UI.
- No mid-edge handles. No modifier-key free stretch.
- A late “most recent map” fetch no longer overwrites an explicit dropdown choice. Retry / Scene Review accept still force-reload.
- Working tree is not committed unless requested.

---

## Final verdict

**GO — SPATIAL MAP DIRECT TRANSFORM HANDLES + PHOTOSHOP-STYLE RESIZE E2E CERTIFIED**
