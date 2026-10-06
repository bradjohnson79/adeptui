# Timeline Preview Action Bar Visibility Toggle

**Date:** 2026-09-15  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf7` (implementation uncommitted)  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Scene:** 12B — Quarters Interview `d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`  
**Surfaces:** `http://127.0.0.1:5173/` (Vite), `http://127.0.0.1:8758/` (Studio API)

This is the governing document for the Preview Monitor publish/MAGI action-bar eye toggle.

## Verdict

**GO — TIMELINE PREVIEW ACTION BAR VISIBILITY TOGGLE CERTIFIED**

## What shipped

Visibility-only overlay on the existing Preview Monitor top bar (`CHANGES PENDING` / `UPDATE PUBLISHED` / `UPSCALE WITH MAGI`).

- Default expanded, open-eye control on the **right** of the bar.
- Click hides the full bar and leaves a compact crossed-eye chip in the Preview Monitor **top-right**.
- Click again restores the full bar with the same pending / published / MAGI state. No reload. No take, playhead, or job reset.
- Preference lives on Timeline workspace layout only (`adept_timeline_workspace_layout_v1` → `previewPublishBarVisible`). MAGI split keys are unchanged.
- Reset Layout restores the canonical visible bar.
- While hidden, a yellow attention dot appears on the chip if Changes Pending is true. The bar does not auto-reopen.

## Files

- `studio-web/src/timelineMaster/workspaceLayout.ts` — `previewPublishBarVisible` (default `true`); missing/legacy JSON stays visible.
- `studio-web/src/components/timeline-master/TimelineWorkspaceStack.tsx` — Reset Layout writes `previewPublishBarVisible: true` (Timeline path only; MAGI reset still uses MAGI keys).
- `studio-web/src/components/LivePreviewMonitor.tsx` — eye control, overlay collapse, layout event + persist, a11y, pending badge.
- `studio-web/src/styles.css` — overlay chip / collapsed top-right / focus ring. No workspace geometry change.
- `studio-web/src/timelineMaster/workspaceLayout.test.ts` — persist `false`, Reset Layout restores `true`.
- `studio-web/src/components/timeline-master/timelineDrawerFixes.test.ts` — source contract for the toggle.

## Tests

| Suite | Result |
| --- | --- |
| `npx tsx --test src/timelineMaster/workspaceLayout.test.ts` | **12 passed, 0 failed** |
| `npx vitest run src/components/timeline-master/timelineDrawerFixes.test.ts` | **7 passed, 0 failed** |

## Live Scene 12B

| Step | Result |
| --- | --- |
| 1. Bar visible | PASS — `CHANGES PENDING`, `UPDATE PUBLISHED`, `UPSCALE WITH MAGI`, open eye (`Hide preview actions`) |
| 2–3. Click eye / collapse | PASS — `data-collapsed="true"`, compact chip top-right (`x=1233`, `y=265` on a 1280-wide monitor) |
| 4. Crossed eye remains | PASS — `Show preview actions`, `aria-pressed=true`, pending attention dot |
| 5. Video frame | PASS — video rect unchanged `37,254 1244×231` before and after collapse |
| 6. Timeline / monitor size | PASS — monitor `19,207 1280×296` unchanged; overlay only |
| 7. Playback | PASS — Play while hidden: clock `0:01/0:30` → `0:02/0:30`, playhead `1.88` → `2.18`, `<video>` not paused |
| 8–10. Restore | PASS — same three actions + open eye; Take A still Current; MAGI Upscale still available |
| Navigate away / back | PASS — Characters workspace then return: still collapsed |
| Hard reload | PASS — still collapsed, `previewPublishBarVisible: false` |
| Reset Layout | PASS — full bar restored (`UPDATE PUBLISHED`, `UPSCALE WITH MAGI`, `Hide preview actions`) |

Keyboard: native `<button>` is tab-focusable (`tabIndex=0`). Enter/Space are stopped from Timeline Play/Pause so they activate the eye. Automation Space events are not trusted click-activation; live click + Restore + Reset Layout were used as the product proof.

## Persistence contract

- Storage: `adept_timeline_workspace_layout_v1` only.
- MAGI: `adept_magi_center_split_v1` observed unchanged (`viewerHeight` only) while hiding the Timeline bar.
- Default / missing field / Reset Layout: visible.
- Hidden preference survives Timeline remount, other workspaces, and hard reload.

## E2E TRACE

| Stage | Verdict |
| --- | --- |
| User action | PASS — click eye on Scene 12B Preview Monitor |
| Frontend | PASS — overlay collapse / restore, no geometry push |
| API | N/A — visibility only |
| Backend | N/A |
| Persistence | PASS — Timeline workspace localStorage |
| Runtime | N/A — MAGI Upscale not invoked; availability restored correctly |
| Result | PASS — compact chip or full bar as selected |
| Reload | PASS — hidden state restored |
| Downstream | PASS — playback, take, pending, published, MAGI CTA unchanged |

## Runtime

- Studio API `:8758/api/healthz` **200**
- Vite `:5173/` **200**
- Comfy `:8188/system_stats` **200** (read-only)

```
COMFY BEFORE: running http://127.0.0.1:8188 / health 200
COMFY AFTER:  running http://127.0.0.1:8188 / health 200
COMFY RESTARTED?: NO
WHY?: Frontend overlay only. Vite HMR. No API recycle. No supervisor action.
```

## Artifacts

- `.runtime/preview-bar-visibility/preview-bar-expanded-12b.png`
- `.runtime/preview-bar-visibility/preview-bar-collapsed-12b.png`

## Limitations

- The bar exists only when Timeline `publishChrome` is present. MAGI, Text to Video, and other monitors do not get this chip and do not write the Timeline key.
- Hiding the bar while the MAGI chooser is open hides the chooser with the bar; restoring shows the same open chooser. The upscale action is not disabled.
- Automation-injected Space does not equal a trusted user keypress; the control is a real button with stopPropagation for Timeline hotkeys.

## Manual review

1. Open `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline&sceneId=d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`
2. Confirm the eye on the right of the Preview action bar.
3. Hide / restore. Confirm the video and Timeline do not jump.
4. Reset Layout if you want the default visible bar.

Not committed unless requested.
