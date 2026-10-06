# Spatial Map ↔ Correct Area — Viewport Parity (Root-Cause Repair)

**Status:** GOVERNING DOCUMENT — Inpaint/Correct Area viewport parity.
**Date:** 2026-09-11 · Branch: `feat/posecraft-v4-human-replacement`
**Mission:** Repair Correct Area / Inpaint so its map display is pixel-for-pixel and viewport-for-viewport identical to the normal Spatial Map display.

> Single governing doc for this milestone (Build Law #30). Supersedes the
> "separate ImageMaskEditor surface" implementation of Correct Area.

---

## 1. Audit finding (root cause)

The divergence was **structural**: Correct Area rendered a **second, independent renderer** (`ImageMaskEditor`) inside `CorrectAreaPanel`, while the normal map rendered `SpatialGrid`. Two render stacks, two sizing/fit code paths:

| Concern | Normal Map (`SpatialGrid`) | Correct Area (old `ImageMaskEditor`) |
| --- | --- | --- |
| Renderer | SVG `<image>` + `<g>` transform | HTML `<canvas>` |
| Fit | `containRect` (contain, native aspect, letterbox) | `scale = min(1, scaleW, scaleH)` (shrink-to-fit) |
| Zoom/pan | shared `zoom` + `BackgroundAlignment` (offset/scale) | **none** (always refit to its own container) |
| Transform state | `liveAlignment` (offsetX/offsetY/scale) | recomputed `dims` from `containerRef.clientWidth/Height` |
| Mask coords | n/a | display pixels → `alignMaskToSourcePixels` upscale pass |

`ImageMaskEditor` computed its own `dims` from its container and the image's
natural size, ignoring `zoom`/`alignment`. Result: different crop/scale/framing,
so mask coordinates could not be trusted. **NO-GO for inpainting.**

## 2. Repair — Single Viewport Authority

Correct Area is now an **overlay/tool mode on the shared `SpatialGrid`**. The
map renderer does not change; only the interaction layer changes.

- **`SpatialGrid`** gained an optional `maskEditor` prop. When present it:
  - renders the SAME atlas `<image>` + `liveAlignment` transform (no re-render);
  - overlays a **source-natural-resolution mask `<canvas>`** positioned over the
    displayed atlas rect using the **same `viewBoxToLocalCss` mapping** the
    resize handles already use (proven parity);
  - routes pointer events through the existing `pointerToViewBox` mapping and
    converts to **source-image pixels** via the shared contract (below);
  - owns the canvas + exposes a `SpatialMaskHandle`
    (`exportPng/clear/restorePng/getSourceSize/measureCoverage`).
- **`CorrectAreaPanel`** no longer renders any map/mask surface. It contributes
  only the floating correction chrome / prompt dock / result overlay, drives
  tool state up to `SpatialMapPanel`, and receives the `SpatialMaskHandle`.
- **`SpatialMapPanel`** renders `SpatialGrid` **always** (Map and Inpaint), and
  overlays `CorrectAreaPanel` chrome when `workspaceTab === "inpaint"`. The
  `zoom`, `alignment`, `backgroundAssetId`, and `imageUrl` are shared — they are
  the SAME component instance. No `mapZoom`/`inpaintZoom`, no second pan state.

### Mask coordinate contract (source pixels)

New pure helpers in `correctArea.ts` are the single source of truth:

- `atlasContainBox(size, sw, sh)` → the contain-fit rect (identical to `imageBox`).
- `displayedAtlasRect(size, sw, sh, alignment)` → rect after the shared
  `BackgroundAlignment` (identical to `transformedImageBounds`).
- `viewBoxToSourcePixel(x, y, size, sw, sh, alignment)` → source px (null off-image,
  boundary epsilon-clamped so the bottom/right source row+col stay paintable).
- `sourcePixelToViewBox(...)` → inverse (round-trips).

Mask is authored **directly in source natural pixels**; the export is
`canvas.toDataURL` at source resolution with **no display upscale pass**
(`upscaledFromDisplay: false`, `alignment: "shared_viewport_source_pixels"`).
The same source pixel is selected regardless of zoom / pan / browser size / DPR.

## 3. Files changed

- `studio-web/src/components/CoDirector/SpatialMap/correctArea.ts` — viewport
  parity contract (`atlasContainBox`, `displayedAtlasRect`, `viewBoxToSourcePixel`,
  `sourcePixelToViewBox`) + boundary-epsilon fix.
- `studio-web/src/components/CoDirector/SpatialMap/SpatialGrid.tsx` — `maskEditor`
  overlay prop, source-res mask canvas + handle, mask pointer handlers, grid
  handler gating in mask mode.
- `studio-web/src/components/CoDirector/SpatialMap/CorrectAreaPanel.tsx` —
  removed `ImageMaskEditor` render stack; overlay chrome only; `SpatialMaskHandle`
  bridge; direct source-res mask export.
- `studio-web/src/components/CoDirector/SpatialMap/SpatialMapPanel.tsx` —
  `SpatialGrid` always rendered; `CorrectAreaPanel` as overlay; mask config bridge.
- `studio-web/src/components/CoDirector/SpatialMap/spatialMap.css` — overlay-only
  stage (transparent, pointer-events routed), mask canvas styles.
- `studio-web/src/components/CoDirector/SpatialMap/types.ts` — `SlotKind` widened
  with `"spin"` (type-strict build fix, pre-existing).
- Tests: `correctArea.test.ts` (+8 parity-contract cases).

## 4. Verification

### Unit / static
- `correctArea.test.ts`: **16/16 PASS** (incl. contain box, displayed rect under
  pan+zoom, source↔viewBox round-trip with no drift, corner mapping, off-image
  null, DPR/browser-size independence).
- Viewport-relevant suites: **94/94 PASS** (`correctArea`, `SpatialGrid`,
  `gridGeometry`, `SpatialMapPanel`, `types`).
- `tsc --noEmit -p tsconfig.json`: clean.
- `npm run build` (`tsc -b`): the Spatial viewport files are **clean**. The build
  as a whole has **137 pre-existing errors in unrelated subsystems**
  (VoiceStudio, SceneCreator `MiniShotModal`/`sceneCreatorMiniApi`,
  `cameraMovementPath`, `SpinCameraPanel`) from prior uncommitted local edits —
  **none in the viewport-parity files**. Flagged as a separate blocker; not
  introduced by this mission.

### Runtime (ComfyUI Protection Law)
- `COMFY BEFORE`: RTX 5090 healthy, VRAM free ~11.75 GB.
- `COMFY AFTER`: RTX 5090 healthy, VRAM free ~11.75 GB.
- `COMFY RESTARTED?` **NO** (ordinary build; Vite HMR only).
- Studio API `:8758` healthz `{"status":"ok"}`; Vite `:5173` 200.

### Live E2E — BLOCKED BY PRODUCT SHELF (not by this change)

The Spatial Map workspace is **deliberately shelved for Adept UI v1.1**. Live in
the browser (`?workspace=spatial`), the surface renders:

> **"Spatial Map unavailable — Spatial Map is shelved for Adept UI v1.1 and will
> return in a later release."** (`targetReturn: v1_2_cloud`)

`studio-web/src/core/featureFlags.ts` → `spatialMap.enabled = false` (hardcoded,
`status: "shelved_v1_1"`). `ProjectEditor.tsx` routes `?workspace=spatial` back to
project home. This gate **predates this mission** (added by prior uncommitted
local edits; verified via `git diff HEAD`) and is an intentional product decision
— code/endpoints preserved, only nav/mount gated. The entire `SpatialGrid`
surface (which hosts both Map and the Correct Area overlay) is therefore
unmounted in the shipped product, so **no live journey can be driven** without
flipping a product flag that is out of this mission's scope and contrary to the
shelf.

A browser agent first attempted the live E2E and was blocked by browser-MCP tab
infrastructure; a second direct attempt reached the surface and hit the shelf
gate above. No DOM/CDP parity evidence could be captured because the surface
does not mount. **No evidence was fabricated.**

## 5. Verdicts

| Gate | Verdict |
| --- | --- |
| SOURCE ASSET PARITY | STRUCTURAL PASS (same `SpatialGrid` `<image>`/`imageUrl` by construction); live N/A (shelf) |
| VIEWPORT BOUNDS PARITY | STRUCTURAL PASS (shared `viewBoxToLocalCss` + `liveAlignment`); unit PASS; live N/A (shelf) |
| ASPECT RATIO PARITY | UNIT PASS (contain-fit preserves source aspect; mask canvas = source dims); live N/A (shelf) |
| ZOOM/PAN PARITY | STRUCTURAL PASS (single shared `zoom`/`alignment` — no separate inpaint state); unit PASS; live N/A (shelf) |
| GRID ALIGNMENT | STRUCTURAL PASS (same `SpatialGrid` grid layer); live N/A (shelf) |
| MASK SOURCE-PIXEL ALIGNMENT | UNIT PASS (round-trip no drift, DPR-independent, corner-exact); live N/A (shelf) |
| MODE-SWITCH STABILITY | STRUCTURAL PASS (no remount — overlay toggles, viewport persists); live N/A (shelf) |
| CORRECTION OUTPUT PARITY | NOT VERIFIED (requires live zimage.inpaint; surface shelved) |
| SAVE / RELOAD | NOT VERIFIED (surface shelved) |
| SPATIAL MAP REGRESSION | UNIT PASS (252/252 Spatial Map tests) |

**Final: E2E BLOCKED — Spatial Map workspace shelved for v1.1 (`spatialMap.enabled=false`).**

The root-cause repair is implemented and unit/static-verified (single viewport
authority; mask authored in source pixels). Live full-stack certification is
blocked by an intentional product gate, not by the repair. To certify live, the
Spatial Map shelf must be lifted (product decision — `targetReturn: v1_2_cloud`)
or this surface must be re-mounted; then the Mess Hall journey in §4 can be run
unchanged. This is **not** a GO and not a code NO-GO — it is an environment
blocker disclosed per the Full-Stack E2E law.
