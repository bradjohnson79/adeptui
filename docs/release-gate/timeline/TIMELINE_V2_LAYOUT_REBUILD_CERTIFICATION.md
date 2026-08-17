# Timeline V2 Clean Layout Rebuild — Certification

**Status:** Governing document for this milestone.  
**Date:** 2026-08-17  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`  
**Branch:** `beta`  
**HEAD at evidence:** recorded at commit time in this file’s SHA section  
**Live UI:** `http://127.0.0.1:8760/`  
**Live API:** `http://127.0.0.1:8758/api/health`  
**Served dist:** `index-YPccTX0G.js` + `index-BT9sR1Qn.css` (matches `studio-web/dist/index.html`)

Supersedes layout chrome in `TIMELINE_LAYOUT_LIBRARY_REFERENCES_CERTIFICATION.md` (marked historical). Does not replace the Library references / alias-rename product gate.

## Verdict

`GO — TIMELINE V2 CLEAN LAYOUT REBUILD CERTIFIED END TO END`

Independent visual line: `VERIFIED — TIMELINE V2 CLEAN LAYOUT + TRACK READABILITY PASSED`

## Scope

NEW SHELL, SAME ENGINE. Isolated `.timeline-v2` CSS Grid/Flex chrome. `TimelineEditorShell.tsx` remains the state/handler owner. No dual layout toggle. Image/Video Reference lanes stay retired. Expand removed (`showExpand={false}`). One Full Screen control. Schnick only; no `POST /api/projects`.

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

- `studio-web` workspaceLayout unit: **6 passed**
- `studio-web` production build: passed (`✓ built in 1.66s`)
- Playwright (Beta target UI `http://127.0.0.1:8760/` API `http://127.0.0.1:8758` `ADEPT_BETA_TARGET=1`):

```
npm run test:e2e:beta -- tests/e2e/timeline/timeline-v2-layout.spec.ts tests/e2e/timeline/timeline-layout-library-references.spec.ts --project=chromium --retries=0
2 passed (6.5s)
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
| `timeline-v2-shell.css` | header, 3-column body, splitters, docks, tabs |
| `timeline-v2-canvas.css` | ruler, rows, labels, scroll, clip token text |
| `timeline-editor-shell.css` | toolbar, banner, inspector, ref chips, clip badges — **not** competing layout / `.track-label` / `!important` theme patches |

Old `.timeline-editor-shell__layout` / `.director-tracks--timeline-shell` track-label overrides and the `:root:not([data-theme="aurora-day"]) … !important` block were removed.

## Limitations

- Hosted Vercel SHA alignment is recorded after push/deploy in the SHA section below.
- MCP live tab may remain on `data-theme=aurora-day` after the cert probe; refresh restores the creator default.
- Unrelated dirty tree (for example Image Studio) is not part of this commit.
- Concurrent `DirectorTracks.tsx` unused-import `void` stubs from other in-flight work were preserved so the production build stays green.

## SHA

Fill at commit:

- Commit SHA:
- Remote `origin/beta` SHA after push:
- Vercel deployment SHA:
