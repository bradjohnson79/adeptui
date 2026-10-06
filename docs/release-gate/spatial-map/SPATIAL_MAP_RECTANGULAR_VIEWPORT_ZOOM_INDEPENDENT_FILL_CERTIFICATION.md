# Spatial Map Rectangular Viewport Zoom-Independent Fill

**Governing document for this zoom correction.**

Workspace zoom is view-only. It must never shrink the Spatial Map transform relative to the rectangular production viewport, and it must never write `backgroundAlignment`.

**Verdict:** `GO — SPATIAL MAP RECTANGULAR VIEWPORT ZOOM-INDEPENDENT FILL E2E CERTIFIED`

Companion repair: `SPATIAL_MAP_RECTANGULAR_ATLAS_CANONICAL_PLACEMENT_GRID_CERTIFICATION.md`.

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| HEAD SHA | `b6156455` (working tree includes this repair; not committed unless requested) |
| Named project | Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Live map | Venture Corridor Walk `7c7aac85-6932-4945-a13f-4a11fd69b79f` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |

---

## Transform domains

```text
source native aspect
      ↓
rectangular viewport base fit (contain in a matching-aspect rect)
      ↓
backgroundAlignment scale / offset   ← calibration only
      ↓
workspace zoom                        ← view only; sizes the production rectangle
```

Workspace zoom is **not** multiplied into `backgroundAlignment.scale`.

---

## Root cause — unused rectangle when zooming out

The rectangular conversion applied workspace zoom as an inner CSS transform:

```ts
style={{ transform: `scale(${zoom})`, transformOrigin: "center center" }}
```

`.spatial-map__viewport` is `position:absolute; inset:0` inside the full-size wrap. Scaling the inner viewport shrank the Atlas and grid inside a still-full black rectangle. That is why 75% zoom showed unused margin.

**Repair:** remove the inner scale. Size the production wrap with `--spatial-map-zoom`. The Atlas still fills the wrap. Calibration is unchanged.

---

## Fit policy

Contain-fit in a native-aspect rectangular CSS box is fill at scale `1`. 16:9 stays 16:9. 4:3 stays 4:3. Venture 3:2 stays 3:2. Below-1 scale remains intentional calibration letterbox. Reset Alignment returns to fill.

Handles continue to operate on the map calibration transform only.

---

## Live proof

Playwright coexistence spec measured Atlas/frame fill at zoom `1`, `0.9`, `0.75`, `0.5`, then back to `1` on Native Aspect 16:9 and Venture. Fill ratio stayed ≥ 0.92 and stable across zooms. `data-scale` did not change.

Live Venture:

- Reset Alignment → Size `100` / API scale `1.0`
- Workspace zoom `75%` — production rectangle shrinks; Atlas still fills that rectangle; Size remains `100`
- Workspace zoom `50%` — same; zoom-out disabled at minimum
- Korri `0.40 / 0.62`, Anadriya `0.58 / 0.64`, C1 `0.50 / 0.82` unchanged

---

## Tests

Covered by `spatial-map-rectangular-atlas-placement-grid.spec.ts` (coexistence + fill) and updated `spatial-map-rectangular-viewport.spec.ts` (zoom must not rewrite calibration; grid density stays).

---

## Runtime

**COMFY RESTARTED?:** NO  
**WHY?:** CSS / view transform only.

---

## Final verdict

**GO — SPATIAL MAP RECTANGULAR VIEWPORT ZOOM-INDEPENDENT FILL E2E CERTIFIED**
