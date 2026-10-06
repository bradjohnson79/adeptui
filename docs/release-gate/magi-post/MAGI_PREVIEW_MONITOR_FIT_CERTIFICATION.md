# MAGI Preview Monitor Fit Certification

Governing document for MAGI Preview Monitor **Fit / contain** presentation. Workspace geometry is unchanged.

**Date:** 2026-09-14  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf7`  
**Review URL:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?tab=magi`  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Scene 12B published master:** `a85c2632-dd04-4450-be5d-214aa191e209`

## Verdict

**GO — MAGI PREVIEW MONITOR FIT CERTIFIED**

## Evidence

| Field | Result |
| --- | --- |
| SOURCE DIMENSIONS | Scene 12B published master **864×480**. 2K graded master **2560×1440**. |
| MONITOR DIMENSIONS | Owner viewport 1318×843. Stage at drawers-open ~**755.6×219.6**. |
| BEFORE SCALE | Intrinsic **1:1 source pixels** (`max-height: 100%` did not constrain `<video>`). Frame overflowed the stage. |
| AFTER FIT SCALE | Scene 12B **0.4534** (`217.6/480`) into 755.6×219.6. 2K compare pane **0.1110** (`159.9/1440`). |
| MEDIA RENDER PATH | `.magi-viewer` → `.magi-viewer-stage` → `MagiPreviewFitFrame` (`mediaContainRect`) → `<video>`/`<img>` + `MagiOverlayLayer` inside the fitted frame. Not a 1:1 canvas transform. |
| OVERLAY/GUIDE RESULT | Safe title/action/center guides match the fitted frame (0px delta). Guides sit on displayed picture, not the letterbox. |
| DRAWER RESIZE | Left closed, right closed, both open: frame stayed contained. Stage widened; Fit recentered. No manual refresh. |
| SPLITTER RESIZE | Viewer/timeline divider 368→380→340 px: scale 0.4534→0.4784→0.3951. Always contained. |
| FULLSCREEN | Browser Fullscreen API was blocked in the agent tab. Expand workspace still refit (stage 207.6→231.6, scale 0.4284→0.4784, contained). |
| 2K TEST | `graded_2k_master` 2560×1440 displayed at **284×160** in Compare (same pane height as 1920×1056 at **291×160**). Viewer did not grow with source pixels. |
| TRACK VISIBILITY | VIDEO / AUDIO / MUSIC / SFX remained visible through drawer and splitter changes. Inspector remained visible when open. |

## Tests

`13 passed` — `mediaFit.test.ts`, `videoRetake.test.ts`, `magi-editor.css.test.ts`.

## Runtime

- Studio API `http://127.0.0.1:8758/` 200
- Vite `http://127.0.0.1:5173/` 200
- **COMFY BEFORE:** PID 45624 healthy  
- **COMFY AFTER:** PID 45624 healthy  
- **COMFY RESTARTED?:** NO  
- **WHY?:** Preview CSS/Fit only.

## Scope freeze

No MAGI color, upscale, audio/music/SFX, Co-Director, track semantics, or Timeline production changes. Preview presentation only.
