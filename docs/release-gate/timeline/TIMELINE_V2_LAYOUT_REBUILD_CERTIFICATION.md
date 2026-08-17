# Timeline V2 Clean Layout Rebuild — Certification

**Status:** Governing document for this milestone.  
**Date:** 2026-08-17  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`  
**Branch:** `beta`  
**HEAD at evidence:** recorded at commit time in this file’s SHA section  
**Live UI:** `http://127.0.0.1:8760/`  
**Live API:** `http://127.0.0.1:8758/api/health`  
**Served dist:** `index-fTmX5y19.js` + `index-BDkZK984.css` (matches `studio-web/dist/index.html`)

Supersedes layout chrome in `TIMELINE_LAYOUT_LIBRARY_REFERENCES_CERTIFICATION.md` (marked historical). Does not replace the Library references / alias-rename product gate.

## Verdict

`GO — TIMELINE V2 CLEAN LAYOUT REBUILD CERTIFIED END TO END`

Independent visual line: `VERIFIED — TIMELINE V2 CLEAN LAYOUT + TRACK READABILITY PASSED`

## Scope

NEW SHELL, SAME ENGINE. Isolated `.timeline-v2` CSS Grid/Flex chrome. `TimelineEditorShell.tsx` remains the state/handler owner. No dual layout toggle. Image/Video Reference lanes stay retired. Expand removed (`showExpand={false}`). One Full Screen control. Schnick only; no `POST /api/projects`.

## Retractable Drawer Workspace

**Date:** 2026-08-17  
**Live UI:** `http://127.0.0.1:8760/`  
**Live API:** `http://127.0.0.1:8758/api/health`  
**Served dist:** `index-fTmX5y19.js` + `index-BDkZK984.css`

Always-on left/right panes are now retractable edge drawers. `TimelineEditorShell.tsx` remains the only shell/state owner. Preference key stays `adept_timeline_workspace_layout_v1`. Overlay is the overflow valve; persisted `leftWidth` / `rightWidth` are never shrunk merely to force dual-push. Focus Timeline closes both drawers and is not browser Full Screen.

### Drawer verdict

`GO — TIMELINE RETRACTABLE DRAWER WORKSPACE CERTIFIED END TO END`

Independent visual line: `VERIFIED — BOTH OPEN / BOTH CLOSED / ONE OPEN / OVERLAY PASSED`

Observed on Schnick Coffee at `http://127.0.0.1:8760/`:

| State | Observation |
| --- | --- |
| Both open (1440) | Left Scenes/Library/References and right Inspector push; 14px edge handles; Preview + Timeline stay between them |
| Right closed | Inspector gone from flow; Preview/Timeline widen; right 14px handle remains on the physical edge |
| Both closed (Focus Timeline) | Only the two edge handles remain; Preview/Timeline fill the body; Full Screen control stays unpressed |
| Overlay (~1100) | Last-activated left stays push; right Inspector overlays without remounting; center stays ≥ ~520px |

Stills: `artifacts/timeline-drawer-workspace/both-open.png`, `left-open-right-closed.png`, `both-closed.png`, `overlay-narrow.png`.

### Drawer wiring

| Control | Result | Evidence |
| --- | --- | --- |
| Edge handles always visible | PASS | `timeline-drawer-left-toggle` / `timeline-drawer-right-toggle` |
| Close/open restores width; contents stay mounted | PASS | Playwright `data-keep-alive` on Inspector after close/open; stored widths unchanged |
| Preview grows when a drawer closes | PASS | Preview width +40px after right close |
| Focus Timeline closes both, not Full Screen | PASS | both placements `closed`; `aria-pressed=false`; `document.fullscreenElement` null |
| Reset Layout both-open + 280/320 | PASS | localStorage after `timeline-reset-layout` |
| Overlay does not crush center | PASS | 1100 viewport; last-activated push + other overlay; main width ≥ 500 |
| Inspector/Hot Keys scroll does not pan Preview/Timeline | PASS | `getBoundingClientRect().top` unchanged |
| Library scroll does not hide Scenes/References | PASS | dock tops stay put |
| Track labels 132px / `#e1e8f2` default + aurora-day | PASS | existing geometry test |
| No Expand; playhead gutter transparent | PASS | existing geometry test |

### Drawer tests

- `studio-web` workspaceLayout + hotkeys unit: **22 passed**
- `studio-web` production build: passed (`✓ built in 1.60s`)
- Playwright (Beta UI `http://127.0.0.1:8760/` API `http://127.0.0.1:8758` `ADEPT_BETA_TARGET=1`):

```
npm run test:e2e:beta -- tests/e2e/timeline/timeline-v2-layout.spec.ts tests/e2e/timeline/timeline-layout-library-references.spec.ts --project=chromium --retries=0
3 passed (14.2s)
```

### Drawer E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS (handles, Focus Timeline, Reset Layout, overlay resize, Inspector/Library scroll, tab smoke) |
| Frontend | PASS (7-column body + overlay/closed CSS; served `index-fTmX5y19.js` / `index-BDkZK984.css`) |
| API | PASS (existing scenes/director/library; no API contract change) |
| Backend | PASS (no backend files in this increment) |
| Persistence | PASS (`leftDrawerOpen` / `rightDrawerOpen` / widths; Reset restores defaults) |
| Runtime | N/A (layout chrome; no GPU generation) |
| Result | PASS |
| Reload | PASS (geometry test drag + reload) |
| Downstream | PASS (library-references alias rename still green) |

## Theme regression (cert-blocking)

Computed style on `.timeline-v2__track-label` (`timeline-v2-label-batches`) via live CDP on `http://127.0.0.1:8760/`:

| Theme | `color` | `background-color` | scoped `--timeline-v2-track-label-color` | competing token | Result |
| --- | --- | --- | --- | --- | --- |
| default (`data-theme` unset) | `rgba(225, 232, 242, 0.72)` | `rgba(8, 12, 19, 0.96)` | `#e1e8f2b8` (minified `rgba(225, 232, 242, 0.72)`) | `--timeline-track-label-text` = `#eef6ffeb` (not used) | PASS |
| `aurora-day` | `rgba(225, 232, 242, 0.72)` | `rgba(8, 12, 19, 0.96)` | `#e1e8f2b8` | `--timeline-track-label-text` = `#121f2df0` (near-black 18,31,45 — not used) | PASS |

Also observed: `opacity: 1`, `transform: none`, `filter: none`, `-webkit-text-fill-color` matches scoped color, label width `132px`, 8 V2 labels, `workspace-expand` count `0`, `workspace-fullscreen-controls` count `1`.

Failure in either theme would be cert failure. Both passed.

## Wiring matrix

| Control | Result | Evidence |
| --- | --- | --- |
| Three-column body + splitters | PASS | `.timeline-v2__body`; `timeline-splitter-left/right` |
| Scenes / Library / References docks | PASS | Playwright library-references + live Schnick |
| Preview + toolbar + tracks | PASS | `timeline-focus-viewer`, `timeline-toolbar`, `timeline-track-board` |
| Inspector / Co-Director / Hot Keys tabs | PASS | `timeline-tab-inspector`, `timeline-tab-codirector`, `timeline-tab-hotkeys` |
| Expand removed, one Full Screen | PASS | Playwright + CDP `expand=0` `fs=1` |
| Prompt clip tokens (`@` `#` `*`) | PASS | `timeline-v2__clip-tokens` / `prompt-token-summary-*` |
| Lip Sync speaker + filename | PASS | `timeline-v2__clip-tokens` / `timeline-v2__clip-instruction` on lipsync clips |
| No Image/Video Reference lanes | PASS | DirectorTracks shellMode rows |
| Pane resize persists | PASS | Playwright drag + reload on `.timeline-v2__body` |
| Library-only references + alias rename | PASS | `timeline-layout-library-references.spec.ts` |

## Tests

- `studio-web` workspaceLayout + hotkeys unit: **22 passed**
- `studio-web` production build: passed (`✓ built in 1.60s`)
- Playwright (Beta target UI `http://127.0.0.1:8760/` API `http://127.0.0.1:8758` `ADEPT_BETA_TARGET=1`):

```
npm run test:e2e:beta -- tests/e2e/timeline/timeline-v2-layout.spec.ts tests/e2e/timeline/timeline-layout-library-references.spec.ts --project=chromium --retries=0
3 passed (14.2s)
```

Library-references last assertion uses project asset list (not `GET /api/assets/{id}/file`) so a large Schnick video cannot stall the single Studio API worker.

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS (open Timeline, resize, theme probe, Library/References, alias rename) |
| Frontend | PASS (`.timeline-v2` shell + canvas; served CSS `index-BT9sR1Qn.css`) |
| API | PASS (scenes, director, references, project assets) |
| Backend | PASS (existing director/reference handlers; no backend contract change in this milestone) |
| Persistence | PASS (pane grid after reload; renamed alias + binding id) |
| Runtime | N/A for layout chrome (no GPU generation in this gate) |
| Result | PASS |
| Reload | PASS |
| Downstream | PASS (Library asset remains after chip remove) |

## CSS ownership

| File | Owns |
| --- | --- |
| `timeline-v2-shell.css` | header, drawer body grid, handles, splitters, docks, tabs, right-panel scroll |
| `timeline-v2-canvas.css` | ruler, rows, labels, scroll, clip token text |
| `timeline-editor-shell.css` | toolbar, banner, inspector, ref chips, clip badges — **not** competing layout / `.track-label` / `!important` theme patches |

Old `.timeline-editor-shell__layout` / `.director-tracks--timeline-shell` track-label overrides and the `:root:not([data-theme="aurora-day"]) … !important` block were removed.

## Limitations

- Hosted Vercel SHA alignment is recorded after push/deploy in the SHA section below.
- MCP live tab may remain on `data-theme=aurora-day` after the cert probe; refresh restores the creator default.
- Unrelated dirty tree (for example Image Studio) is not part of this commit.
- Concurrent `DirectorTracks.tsx` unused-import `void` stubs from other in-flight work were preserved so the production build stays green.

## SHA

- Drawer workspace commit SHA: `94c5292ac2068863edcb47303aa45ed2f7911bad`
- HEAD / push SHA: `94c5292ac2068863edcb47303aa45ed2f7911bad`
- Remote `origin/beta`: `94c5292ac2068863edcb47303aa45ed2f7911bad`
- Vercel production: GitHub environment **Production** for `94c5292`, status **success**, inspect `https://vercel.com/anoint/adeptui/4h5x9wXUS1y8SV9ziRFSSpiDpzvJ`
- Hosted UI: `https://adeptui.vercel.app/` HTTP **200**, bundle `index-BBdu2pYf.js` + `index-BDkZK984.css` (drawer testids present in hosted JS)
