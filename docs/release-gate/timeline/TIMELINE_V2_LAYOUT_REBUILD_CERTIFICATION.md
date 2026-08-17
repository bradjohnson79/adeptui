# Timeline V2 Clean Layout Rebuild — Certification

**Status:** Governing document for this milestone.  
**Date:** 2026-08-17  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`  
**Branch:** `beta`  
**HEAD at evidence:** recorded at commit time in this file’s SHA section  
**Live UI:** `http://127.0.0.1:8760/`  
**Live API:** `http://127.0.0.1:8758/api/health`  
**Served dist:** `index-Dedt-P3R.js` + `index-B5e0arYt.css` (matches `studio-web/dist/index.html`)

Supersedes layout chrome in `TIMELINE_LAYOUT_LIBRARY_REFERENCES_CERTIFICATION.md` (marked historical). Does not replace the Library references / alias-rename product gate.

## Verdict

`GO — TIMELINE SINGLE TIMED PROMPT TRACK CERTIFIED`

Independent visual line: `VERIFIED — ONE TIMED PROMPT ROW / HORIZONTAL CLIPS PASSED`

Overlay drawers remain certified: `GO — TIMELINE TRUE OVERLAY DRAWER WORKSPACE CERTIFIED END TO END`. Prior clean-layout increment remains historically certified below. The retractable-drawer increment is historical **NO-GO** and is not erased.

## Single Timed Prompt Track

**Date:** 2026-08-17  
**Working tree HEAD:** `a03c9cdf5397a5fe70b07539d60c2ac810564393` plus uncommitted Timed Prompt + overlay files  
**Live UI:** `http://127.0.0.1:8760/` HTTP **200**  
**Live API:** `http://127.0.0.1:8758/api/health` HTTP **200**  
**Served dist:** `index-Dedt-P3R.js` + `index-B5e0arYt.css`

One creator-facing Timed Prompt row. `prompt_segments` stay the persistence contract. Prompt + adds a clip on that row, not a new lane. Creator copy is `TIMED PROMPT` via `tracks.timedPrompt` in all 12 locale packs. Scene Prompt remains the whole-Scene field. Image/Video Reference lanes stay retired. Lip Sync stays its own track.

### Timed Prompt verdict

`GO — TIMELINE SINGLE TIMED PROMPT TRACK CERTIFIED`

Independent visual line: `VERIFIED — ONE TIMED PROMPT ROW / HORIZONTAL CLIPS PASSED`

Still: `artifacts/timeline-timed-prompt/one-track.png`

### Timed Prompt wiring

| Control | Result | Evidence |
| --- | --- | --- |
| Exactly one Timed Prompt row | PASS | `timeline-timed-prompt-track` count `1`; label `TIMED PROMPT` |
| Prompt + adds clips, not lanes | PASS | two adds → clip count +2; still one row |
| Horizontal sequencing | PASS | added clips share `y` (`|Δ| ≤ 2`) and differ in `x` |
| Compact row | PASS | row height ≤ 56px |
| Timing edit + reload | PASS | Inspector start `3.5`; both clips + one row after reload |
| Bindings persist | PASS | existing `reference_binding_ids` + `prompt-token-summary-*` survive |
| No reference lanes | PASS | `timeline-image-reference-track` / `timeline-video-reference-track` count `0` |
| Last clip may be deleted | PASS | track remains; `deleteSeg` no longer requires a leftover clip |
| Locale parity | PASS | `packParity.test.ts` **3 passed** |

### Timed Prompt tests

- M30F pack parity: **3 passed**
- `studio-web` production build: passed (`index-Dedt-P3R.js` + `index-B5e0arYt.css`)
- Playwright (Beta UI `http://127.0.0.1:8760/` API `http://127.0.0.1:8758` `ADEPT_BETA_TARGET=1`):

```
npm run test:e2e:beta -- tests/e2e/timeline/timeline-timed-prompt-track.spec.ts tests/e2e/timeline/timeline-v2-layout.spec.ts --project=chromium --retries=0
```

Timed Prompt spec: **1 passed (5.3s)**. Layout overlay + geometry (label testid updated): **2 passed**.

### Timed Prompt E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS (Prompt +, Inspector start edit, reload) |
| Frontend | PASS (one `timeline-timed-prompt-track`; served `index-Dedt-P3R.js` / `index-B5e0arYt.css`) |
| API | PASS (`GET`/`PUT` `/api/projects/:id/scenes/:id/director`; `prompt_segments` unchanged contract) |
| Backend | PASS (no backend files in this increment) |
| Persistence | PASS (new clips + edited start survive reload; original director restored after test) |
| Runtime | N/A (track presentation; no GPU generation) |
| Result | PASS |
| Reload | PASS |
| Downstream | PASS (layout overlay specs still green; Scene Prompt distinct from Timed Prompt) |

## Scope

NEW SHELL, SAME ENGINE. Isolated `.timeline-v2` CSS Grid/Flex chrome. `TimelineEditorShell.tsx` remains the state/handler owner. No dual layout toggle. Image/Video Reference lanes stay retired. Expand removed (`showExpand={false}`). One Full Screen control. Schnick only; no `POST /api/projects`.

Center geometry is literally invariant. Drawers slide over Preview + Timeline. No push columns. No hybrid.

## Overlay Drawer Repair

**Date:** 2026-08-17  
**Working tree HEAD:** `a03c9cdf5397a5fe70b07539d60c2ac810564393` plus uncommitted overlay-drawer files (not committed / not pushed / not deployed, per this increment’s gate)  
**Live UI:** `http://127.0.0.1:8760/` HTTP **200** (`/__beta_web_health` **200**)  
**Live API:** `http://127.0.0.1:8758/api/health` `ok:true`  
**Served dist:** `index-CI5qZcQJ.js` + `index-CNLT0X46.css`

Push/overlay hybrid deleted. Body is `position: relative; display: flex` with a full-width `main.timeline-v2__workspace`. Left/right asides stay mounted (`#timeline-drawer-left` / `#timeline-drawer-right`) and slide with `translateX`. Handles stay on the physical edges at `z-index: 45`. Inner splitters resize only that drawer’s stored width (`220–440` / `260–500`). Defaults both closed; Reset Layout → closed + 280/320.

### Overlay verdict

`GO — TIMELINE TRUE OVERLAY DRAWER WORKSPACE CERTIFIED END TO END`

Independent visual line: `VERIFIED — BOTH CLOSED / LEFT OPEN / RIGHT OPEN / BOTH OPEN / NARROW PASSED`

Observed on Schnick Coffee at `http://127.0.0.1:8760/`:

| State | Observation |
| --- | --- |
| Both closed (1440) | Preview + Timeline fill the body; 14px `›` / `‹` handles on the physical edges; drawers off-canvas |
| Left open | Scenes / Library / References slide over the left of Preview + Timeline; center width unchanged |
| Right open | Inspector / Co-Director / Hot Keys slide over the right; center width unchanged |
| Both open | Both overlays cover the edges; ruler/tracks continue under the drawers; center does not shrink |
| Narrow both open (1100) | Same overlay law; workspace width still ≥ 500 |

Stills: `artifacts/timeline-overlay-drawer/both-closed.png`, `left-open.png`, `right-open.png`, `both-open.png`, `narrow-both-open.png`.

### Overlay wiring

| Control | Result | Evidence |
| --- | --- | --- |
| Center never moves / never shrinks | PASS | Playwright `|Δ| ≤ 1` on workspace / Preview / Timeline canvas / playhead px for closed, left, right, both, and left `280 → ~400` resize (sampled during drag) |
| One mounted instance per side | PASS | `timeline-drawer-left`, `timeline-drawer-right`, `timeline-inspector`, `asset-library-list`, `timeline-hotkeys-pane` count `1` |
| Containment | PASS | Scenes / Library / References inside left box; Inspector + tabs inside right |
| Closed off-canvas / open identity transform | PASS | closed `translateX` past drawer width; open `none` / identity matrix; `transform` transition unless reduced-motion |
| Library / Inspector scroll | PASS | Preview + Timeline `top` unchanged |
| State survives close/open | PASS | Library video filter + scrollTop and Hot Keys tab remain after close/open |
| Focus Timeline closes both, not Full Screen | PASS | both `aria-expanded=false`; Full Screen unpressed; `document.fullscreenElement` null |
| Reset Layout both closed + 280/320 | PASS | localStorage after `timeline-reset-layout` |
| Edge handles always visible | PASS | `timeline-drawer-left-toggle` / `timeline-drawer-right-toggle` |
| Track labels 132px / `#e1e8f2` default + aurora-day | PASS | geometry test |
| No Expand; playhead gutter transparent | PASS | geometry test |
| Library-only references + alias rename | PASS | `timeline-layout-library-references.spec.ts` (inner splitter; center rects unchanged) |

### Overlay tests

- `studio-web` workspaceLayout + hotkeys unit: **18 passed**
- Repo grep after delete: no `resolveDrawerChrome` / `clampPushedDrawerWidth` / `DRAWER_OVERLAY_HYSTERESIS` / `data-left-placement` leftovers
- `studio-web` production build: passed (served `index-CI5qZcQJ.js` + `index-CNLT0X46.css`)
- Playwright (Beta UI `http://127.0.0.1:8760/` API `http://127.0.0.1:8758` `ADEPT_BETA_TARGET=1`):

```
npm run test:e2e:beta -- tests/e2e/timeline/timeline-v2-layout.spec.ts tests/e2e/timeline/timeline-layout-library-references.spec.ts --project=chromium --retries=0
3 passed (22.1s)
```

### Overlay E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS (handles, Focus Timeline, Reset Layout, left 280→400 inner resize, Library/Inspector scroll, tab smoke) |
| Frontend | PASS (overlay asides + full-width workspace; served `index-CI5qZcQJ.js` / `index-CNLT0X46.css`) |
| API | PASS (existing scenes/director/library; no API contract change) |
| Backend | PASS (no backend files in this increment) |
| Persistence | PASS (`leftDrawerOpen` / `rightDrawerOpen` / widths; Reset restores closed + 280/320; Library filter + right tab survive close/open) |
| Runtime | N/A (layout chrome; no GPU generation) |
| Result | PASS |
| Reload | PASS (library-references inner-splitter width + alias rename after reload) |
| Downstream | PASS (library-references alias rename still green; Library asset remains after chip remove) |

## Clean Layout Rebuild (historical GO)

`GO — TIMELINE V2 CLEAN LAYOUT REBUILD CERTIFIED END TO END`

Independent visual line: `VERIFIED — TIMELINE V2 CLEAN LAYOUT + TRACK READABILITY PASSED`

Theme, wiring, and track-label evidence below remain that increment’s record. Overlay Drawer Repair does not reopen that gate.

## Retractable Drawer Workspace (historical NO-GO)

**Date:** 2026-08-17  
**Live UI:** `http://127.0.0.1:8760/`  
**Live API:** `http://127.0.0.1:8758/api/health`  
**Served dist:** `index-fTmX5y19.js` + `index-BDkZK984.css`

Always-on left/right panes are now retractable edge drawers. `TimelineEditorShell.tsx` remains the only shell/state owner. Preference key stays `adept_timeline_workspace_layout_v1`. Overlay is the overflow valve; persisted `leftWidth` / `rightWidth` are never shrunk merely to force dual-push. Focus Timeline closes both drawers and is not browser Full Screen.

### Drawer verdict

`NO-GO — DRAWERS ALTERED CENTER TEMPLATE GEOMETRY`

This increment is historical. The 7-column push/overlay hybrid (`handle | leftWidth | splitter | center | splitter | rightWidth | handle`) changed center width when a drawer opened. It is replaced by Overlay Drawer Repair above. The run below is retained as evidence, not current truth.

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
| Overlay body + inner splitters | PASS | `.timeline-v2__body` flex; splitters inside open drawers |
| Scenes / Library / References docks | PASS | Playwright library-references + live Schnick |
| Preview + toolbar + tracks | PASS | `timeline-focus-viewer`, `timeline-toolbar`, `timeline-track-board` |
| Inspector / Co-Director / Hot Keys tabs | PASS | `timeline-tab-inspector`, `timeline-tab-codirector`, `timeline-tab-hotkeys` |
| Expand removed, one Full Screen | PASS | Playwright + CDP `expand=0` `fs=1` |
| Prompt clip tokens (`@` `#` `*`) | PASS | `timeline-v2__clip-tokens` / `prompt-token-summary-*` |
| Lip Sync speaker + filename | PASS | `timeline-v2__clip-tokens` / `timeline-v2__clip-instruction` on lipsync clips |
| No Image/Video Reference lanes | PASS | DirectorTracks shellMode rows |
| Drawer-local resize persists | PASS | Playwright inner splitter; `--timeline-left-width` / `leftWidth`; center rects unchanged |
| Library-only references + alias rename | PASS | `timeline-layout-library-references.spec.ts` |

## Tests

- `studio-web` workspaceLayout + hotkeys unit: **18 passed**
- `studio-web` production build: passed (served `index-CI5qZcQJ.js` + `index-CNLT0X46.css`)
- Playwright (Beta target UI `http://127.0.0.1:8760/` API `http://127.0.0.1:8758` `ADEPT_BETA_TARGET=1`):

```
npm run test:e2e:beta -- tests/e2e/timeline/timeline-v2-layout.spec.ts tests/e2e/timeline/timeline-layout-library-references.spec.ts --project=chromium --retries=0
3 passed (22.1s)
```

Library-references last assertion uses project asset list (not `GET /api/assets/{id}/file`) so a large Schnick video cannot stall the single Studio API worker.

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS (open Timeline, resize, theme probe, Library/References, alias rename) |
| Frontend | PASS (`.timeline-v2` overlay shell + canvas; served `index-Dedt-P3R.js` / `index-B5e0arYt.css`) |
| API | PASS (scenes, director, references, project assets) |
| Backend | PASS (existing director/reference handlers; no backend contract change in this milestone) |
| Persistence | PASS (drawer widths after reload; renamed alias + binding id) |
| Runtime | N/A for layout chrome (no GPU generation in this gate) |
| Result | PASS |
| Reload | PASS |
| Downstream | PASS (Library asset remains after chip remove) |

## CSS ownership

| File | Owns |
| --- | --- |
| `timeline-v2-shell.css` | header, overlay drawers, edge handles, inner splitters, docks, tabs, right-panel scroll |
| `timeline-v2-canvas.css` | ruler, rows, labels, scroll, clip token text |
| `timeline-editor-shell.css` | toolbar, banner, inspector, ref chips, clip badges — **not** competing layout / `.track-label` / `!important` theme patches |

Old `.timeline-editor-shell__layout` / `.director-tracks--timeline-shell` track-label overrides and the `:root:not([data-theme="aurora-day"]) … !important` block were removed.

## Limitations

- Overlay Drawer Repair is certified on local Beta only. Per this increment’s gate: no commit, push, or Vercel deploy until overlay behavior passed (it has; deploy remains a separate user action).
- Hosted Vercel still serves the prior retractable-drawer hybrid until a later deploy.
- MCP live tab may remain on `data-theme=aurora-day` after a theme probe; refresh restores the creator default.
- Unrelated dirty tree (for example Image Studio / Beta backend pids) is not part of this increment.
- Concurrent `DirectorTracks.tsx` unused-import `void` stubs from other in-flight work were preserved so the production build stays green.

## SHA

- Overlay + Timed Prompt working-tree base: `a03c9cdf5397a5fe70b07539d60c2ac810564393` (uncommitted; not pushed)
- Historical retractable-drawer commit (NO-GO): `94c5292ac2068863edcb47303aa45ed2f7911bad`
- Remote `origin/beta` / Vercel production remain on the prior hosted bundle until a later deploy
- Local Beta UI: `http://127.0.0.1:8760/` bundle `index-Dedt-P3R.js` + `index-B5e0arYt.css`
