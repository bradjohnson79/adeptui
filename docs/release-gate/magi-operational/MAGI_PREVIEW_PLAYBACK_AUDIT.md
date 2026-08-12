# MAGI Preview & Playback Audit

**Status:** Read-only Phase 0 audit.
**Date:** 2026-08-08

## 1. Viewer component

- `.magi-viewer` section in the monitor region of `TimelineWorkspaceStack` (wrapped by `MagiWorkspaceStack.tsx:19-28`), `MagiEditorWorkspace.tsx:1221-1309`, `data-testid="magi-viewer"`.
- Modes: `viewer` / `compare` / `mask` / `histogram (future, disabled)` / `vectorscope (future, disabled)` (`:1224-1243`).

## 2. Playhead

- `sequence.playheadFrame` is the single playhead source.
- Ruler click/scrub (`MagiSequenceTimeline.tsx:145-154`); transport step buttons (`:1300-1304`); frame-step/Home/End keys (`:590-604`); `setInterval` playback loop (`:438-452`) advancing + wrapping at `durationFrames`.

## 3. CRITICAL DEFECT — viewer is NOT frame-synced to playhead

- The displayed media is **not** tied to `playheadFrame`:
  - `<video>` elements render `autoPlay loop muted` (`:1260, 1284`) — free-running, ignores playhead.
  - `<img>` shows the whole asset.
  - No canvas, no frame-accurate display, no `currentTime` seeking.
- Playhead only affects the transport **timecode readout** (`:1305, 1329-1334`; `MagiSequenceTimeline.tsx:122-130`).
- **User sees a media asset, not the frame at the playhead** — violates the Core Product Law (What You See ≠ What Is Saved).

## 4. What "current frame" means today

- Only the timecode text (`frameToTimecode(sequence.playheadFrame, …)`). No visual frame rendering.

## 5. Fullscreen

- Browser fullscreen via `useWorkspaceFullscreen({workspaceId:"magi",…})` (`:270-274`), `WorkspaceFullscreenControls` (`:1431-1438`), `WorkspaceFullscreenBanner` (`:1420`), prefs in `workspaceViewPrefs.ts:8`, CSS `workspace-fullscreen.css:118`. Ctrl+Shift+F / Esc handled (`useWorkspaceFullscreen.ts:108-143`). **Present — needs regression coverage.**

## 6. Stubs

- `onShuttle: () => undefined` (`:589`); `onJog` jumps a whole second (frameRate frames) rather than nudge (`:585-588`).
- Mask mode embeds `ImageMaskEditor` with no-op callbacks `onExport={() => undefined} onChange={() => undefined}` (`:1274`) — purely cosmetic.
- Histogram/Vectorscope tabs disabled (`:1229-1230`).

## 7. Selected scope (decision)

**Clip-aware playhead preview** — not full canvas compositing:
- Resolve the clip under `playheadFrame`.
- Video: set `currentTime = (playheadFrame − clip.startFrame + clip.inPoint) / frameRate`, `pause` on seek, reflect in viewer.
- Image: static asset; may show trim-aware indication.
- No overlay/transition compositing in the frame (documented limitation).

## 8. Required repairs (m3)

1. Implement clip-under-playhead resolution.
2. Sync video `currentTime` to playhead-derived time; pause while scrubbing.
3. Seeking (ruler/transport/keyboard) updates preview immediately.
4. Scrub/`SetPlayhead` must not bump `editVersion` (no spurious dirty/autosave).
5. Fullscreen regression test (enter/exit, Esc, playback + playhead preserved, no layout corruption).

## 9. Error states

- No failed-media error state in viewer (`onError` missing) — see m2/m8.
- No loading state for slow media.
