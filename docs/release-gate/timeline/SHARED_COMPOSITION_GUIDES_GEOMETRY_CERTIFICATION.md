# Shared Adept Composition Guides Geometry Certification

**Date:** 2026-09-15  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf7`  
**Surfaces:** Timeline Preview Monitor · MAGI Viewer / Compare / Split View  
**Project:** Korri Anadriya · Scene 12B (`d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`)

## Verdict

**GO — SHARED ADEPT COMPOSITION GUIDES GEOMETRY CERTIFIED**

## ROOT CAUSE

Guides were assembled from more than one coordinate authority: host/monitor bounds, leftover MAGI CSS safe-area boxes, overlay-layer recalculation, and primitives that treated an already-offset composition box as a second viewport. At 21:9 that stacked monitor, source-media, composition, and safe-area rectangles, with center lines escaping the selected frame.

## OLD GEOMETRY AUTHORITIES REMOVED

- Timeline no longer binds guides to the video element / painted media rect.
- `MagiOverlayLayer` no longer draws guides (production objects only).
- `.magi-safe-*` geometry CSS deleted.
- `preview-guides.css` emptied; shared CSS owns visuals.
- One overlay renderer: `AdeptCompositionGuides`.

## SHARED GEOMETRY FUNCTION

`studio-web/src/workspace/compositionGuides.ts`

- `fitAspectRect(viewportWidth, viewportHeight, aspectWidth, aspectHeight)`
- `getCompositionRect` → Timeline selected aspect
- `insetRect` / `getSafeAreaRects` — Action Safe 5%, Title Safe 10%
- `getCenterLineSegments` — clipped to master
- `aspectFromDimensions` — MAGI published-master pixels → production class

Unit tests: `compositionGuides.test.ts` + `timelineDrawerFixes.test.ts` — **21 passed**.

## MASTER COMPOSITION RECT

**Timeline `mode=fit`:** viewport (Preview stage) + selected Picture Shape.

Observed Large stage `1245.6 × 400.8` (AR 3.108):

| Aspect | Master (px) | AR |
| --- | --- | --- |
| 16:9 | 712.5 × 400.8 | 1.778 |
| 21:9 | 935.2 × 400.8 | 2.333 |
| 9:16 | 225.5 × 400.8 | 0.562 |
| 1:1 | 400.8 × 400.8 | 1.000 |

**MAGI `mode=fill`:** guides fill the already-fitted published-master frame. No second aspect crop.

## CLIPPING

`.adept-composition-guides { overflow: hidden }`. All primitives are `%` of the master. Center X/Y are `height:100%` / `width:100%` of that clipped box.

## ACTION SAFE / TITLE SAFE / CENTER LINES

Derived only from the master: action `inset: 5%` dashed, title `inset: 10%` dotted, centers 1px thin. Live CDP: action and title rects inside master on every aspect and MAGI pane.

## Visual walk (primary agent)

### 16:9 VISUAL

PASS. One landscape frame; action + title + center nested. Source ~16:9 Take A coincides with the composition frame under Fit.

### 21:9 VISUAL

PASS (owner Scene 12B Large + Guides ON). One centered 21:9 frame. No monitor-sized rectangle, no second 16:9 guide border, no center line spanning the monitor. Existing 16:9 footage remains contain-fit (not stretched).

### 9:16 VISUAL

PASS. One portrait column; safes and crosshair inside it. No horizontal line across the Preview Monitor.

### 1:1 VISUAL

PASS. One square; nested safes + center. Video unchanged.

### SOURCE/COMPOSITION MISMATCH

PASS. 16:9 source + 21:9 / 9:16 / 1:1 selector: video stays native contain; only the selected composition is a guide.

### PREVIEW FOCUS

Timeline product controls are Large / Balanced / Timeline Focus (no “Preview Focus” size). **Timeline Focus PASS:** 1:1 master resized to `189.8 × 189.8` inside a shorter stage; still one nested overlay. MAGI **Viewer Focus PASS**.

### FULLSCREEN

`ResizeObserver` + `fullscreenchange` wired. Embedded cert browser did not enter OS fullscreen (`requestFullscreen` no-op). Geometry path is the same as Timeline Focus resize.

## MAGI

Same `AdeptCompositionGuides` module. Guides toggle `data-testid="magi-viewer-guides"`. Default ON.

### VIEWER

PASS. Fill overlay coincides with published-master fit frame (`864×480` → AR 1.8). Label `16:9`. Nested safes + center. No leftover MAGI safe CSS.

### COMPARE

PASS. One guide instance on the left published-master pane. Empty compare slot draws no overlay. No span across both panes.

### SPLIT VIEW

PASS. Two independent instances (`x=223.7` and `x=871.5`, each `240.3 × 133.5`). Not one overlay across the combined container.

### OBJECTS COORDINATES

Objects stay in `MagiOverlayLayer` (normalized % of the fit frame, z-index 3). Guides are the last child of `MagiPreviewFitFrame` (`mode=fill`, z-index 4). Same composition box; guides are viewer-only.

### FINAL-RENDER EXCLUSION

Guides are not MAGI overlay elements and are not referenced by Studio API final-render. They do not paint into generated media.

## CONSOLE

No leftover `.magi-safe-guides` / `.preview-guides__action-safe` nodes. Overlay `pointer-events: none`. Scene restored to **16:9** after the aspect walk.

## PLAYBACK

Play engaged on Scene 12B. One 16:9 overlay remained (`412.1 × 231.8`, AR 1.778). Published/current take stays `object-fit: contain`. Changing Picture Shape does not stretch the take. Guides do not intercept clicks (`pointer-events: none`).

## Runtime

- Local UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/api/healthz` → 200
- Vite: `http://127.0.0.1:5173/` → 200
- **COMFY BEFORE / AFTER:** `:8188/system_stats` 200 (read-only)
- **COMFY RESTARTED?:** NO
- **WHY?:** Guide geometry only; no GPU lifecycle.

## Tests

`21 passed` (`compositionGuides.test.ts`, `timelineDrawerFixes.test.ts`).
