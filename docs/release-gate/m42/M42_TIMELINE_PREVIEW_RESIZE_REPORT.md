# Timeline Generator Preview Resize Correction — Completion Report

**Date:** 2026-08-01  
**Scope:** Remove redundant `+ Lip Sync Clip` toolbar control; make Preview Monitor vertically resizable with a scrollable timeline track region.

## Verdict

```text
GO
```

Mandatory live Timeline Generator behavior verified on Beta (`http://127.0.0.1:8760`) via Playwright against a real project workspace.

## Files changed

| File | Change |
| --- | --- |
| `studio-web/src/components/timeline-master/TimelineToolbar.tsx` | Removed `+ Lip Sync Clip` button and `addLipSyncClip` handler |
| `studio-web/src/components/timeline-master/TimelineWorkspaceStack.tsx` | Pointer-captured resize, live drag height, keyboard Home/End, project persistence, fullscreen-safe restore |
| `studio-web/src/timelineMaster/workspaceLayout.ts` | Responsive min/max bounds, project-scoped preview height key helpers, default ratio ~48% |
| `studio-web/src/styles/timeline-master/timeline-workspace.css` | Tracks `min-height: 0` so preview expansion is absorbed; stronger divider hit target / active state |
| `studio-web/src/components/timeline-master/TimelineEditorShell.tsx` | Passes `projectId` into workspace stack |
| `studio-web/src/pages/ProjectEditor.tsx` | Passes `projectId` into workspace stack |
| `studio-web/src/components/DirectorTracks.tsx` | `data-testid="timeline-track-scroll"`; empty-state copy no longer references removed button |
| `studio-web/src/timelineMaster/workspaceLayout.test.ts` | Unit coverage for bounds/clamp/persistence key |
| `tests/e2e/m42/m42-timeline-preview-resize.spec.ts` | Full UX Playwright certification + evidence screenshots |
| `tests/e2e/m42/m42-w46-timeline-final-ops.spec.ts` | Asserts Lip Sync `+`/`−` remain and clip button is absent |
| `docs/release-gate/m42/M42_TIMELINE_PREVIEW_RESIZE_REPORT.md` | This report |

## Root cause

1. **Redundant Lip Sync button**  
   W46 Lip Sync tooling added both a Lip Sync track `+`/`−` group and a separate `+ Lip Sync Clip` action. Clip creation was duplicated in the toolbar, so the dedicated button was redundant once track `+`/`−` remained the primary controls.

2. **Divider did not meaningfully resize the Preview Monitor**  
   Resize plumbing existed, but the track region used `min-height: 280px`, which prevented the lower pane from shrinking when the preview grew. The workspace could not absorb height changes, so the divider felt ineffective and the preview stayed cramped.

3. **Timeline area could not absorb expansion**  
   Because the track container refused to shrink below 280px, enlarging the preview pushed layout instead of compressing a scrollable track viewport. Vertical overflow belonged on `.track-board-scroll`, not the page shell.

## Implementation

### Layout structure

```text
.timeline-workspace-stack (column flex, overflow hidden)
  .timeline-workspace-monitor   flex: 0 0 <preview-height>
  .timeline-workspace-divider   separator / resize handle
  .timeline-workspace-tracks    flex: 1; min-height: 0
    toolbar (sticky / flex 0)
    DirectorTracks → .track-board-scroll (overflow auto)
```

### Resize state

- Resolved height from layout ratio + `ResizeObserver` container size
- Live `liveHeightPx` during drag (no persistence per move)
- Commit on pointer up / cancel / lost capture

### Pointer handling

- `pointerdown` + `setPointerCapture`
- `pointermove` uses `startHeight + (clientY - startY)` (down enlarges top pane)
- `pointerup` / `pointercancel` / `lostpointercapture` + unmount cleanup
- Heights clamped every move

### Min / max

- Min ≈ 220–260px (responsive to short workspaces)
- Default ratio ≈ 0.48 of center workspace
- Max ≈ 72–78% of workspace, also capped so ≥140px remains for toolbar + compact tracks

### Persistence

- Project key: `adept-ui.timeline.preview-height.<projectId>`
- Also mirrored into existing `adept_timeline_workspace_layout_v1`
- Saved on drag end / keyboard commit, not every `pointermove`
- Restored on load and clamped to current viewport

### Fullscreen

- Snapshot `lastNonFullscreenLayout` on enter
- Divider hidden while fullscreen
- Exit restores prior height; no stale inline height left behind

### Accessibility

- `role="separator"`, `aria-orientation="horizontal"`, `aria-valuemin|max|now`
- Keyboard: ArrowUp/Down (Shift = larger), Home = min, End = max

## Test results

### Unit

```text
node --test studio-web/src/timelineMaster/workspaceLayout.test.ts
→ 4 passed
```

### Lint

```text
npm --prefix studio-web run lint
→ pre-existing error in src/pages/Home.tsx (useTemplateById in callback); no new lint errors in touched Timeline files
```

### Typecheck / build

```text
npm --prefix studio-web run build
→ tsc -b && vite build  OK
```

### Playwright

```text
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760
npx playwright test tests/e2e/m42/m42-timeline-preview-resize.spec.ts --project=chromium
→ 1 passed

npx playwright test tests/e2e/m42/m42-w46-timeline-final-ops.spec.ts --project=chromium
→ 4 passed (Lip Sync clip control absent; +/- remain)
```

## Evidence

Screenshots under `artifacts/m42/timeline-preview-resize/`:

1. `01-default-preview.png` — compact/default Preview Monitor
2. `02-expanded-preview.png` — enlarged Preview Monitor
3. `03-compact-timeline-scroll.png` — compacted track region with scroll viewport
4. `04-restored-after-reload.png` — height restored after reload

## Manual certification (desktop resolutions)

Automated coverage exercised 1920×1080 plus a 1366×768 bounded-layout check inside the Playwright suite. Manual spot-check checklist for operators:

- [ ] 1366×768 / 1440×900 / 1920×1080 / 2560×1440: default preview usable
- [ ] Drag enlarge/shrink feels correct (down enlarges top pane)
- [ ] Lower toolbar remains visible; tracks scroll vertically
- [ ] Horizontal zoom/scroll + clips still interactive
- [ ] Fullscreen enter/exit restores normal height
- [ ] No generation / provider regressions

## Notes

- Drag direction follows natural top-pane geometry: moving the divider **down** enlarges the Preview Monitor; moving it **up** shrinks it. Keyboard ArrowUp/Home shrink; ArrowDown/End enlarge.
- Lip Sync clip creation via the dedicated toolbar button is removed; Lip Sync track `+`/`−` remain. Clips continue via track drop / inspector paths.
