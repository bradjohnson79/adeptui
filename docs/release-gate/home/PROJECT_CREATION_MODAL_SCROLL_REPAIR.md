# PROJECT CREATION MODAL VERTICAL SCROLL: GO

## Summary

- Repaired the centered Create Project modal so expanded Optional settings, Browse templates, and refine-type content scroll inside a constrained body while the header and footer stay fixed and reachable.
- Did not revert to a side drawer.
- Verified on Beta at `http://127.0.0.1:8760/` with Playwright Expanded Content Scroll coverage across desktop, short, narrow, and 200% zoom viewports.

## Branch And Runtime

- Branch: `feature/ai-guided-setup`
- Starting SHA for this pass: `fa09c99d6395c29461cdec4555055faad116c435`
- Beta URL: `http://127.0.0.1:8760/`
- Beta API health: `http://127.0.0.1:8758/api/health`
- Final Beta health: READY (`web` 8760, `api` 8758, external ComfyUI 8188)

## Scope Delivered

- `studio-web/src/components/generationStudio/HomeCreateProjectModal.tsx`
  - portal to `document.body`
  - three-region shell: fixed header, constrained content slot, form-owned body/footer
  - body scroll lock + overscroll containment while open
- `studio-web/src/components/generationStudio/HomeCreateProjectModal.css`
  - panel `max-height: min(720px, calc(100vh - 64px))`
  - flex column + `overflow: hidden` on shell
  - scrollable body owns `overflow-y: auto`, `min-height: 0`, `scrollbar-gutter: stable`
  - footer remains a non-scrolling flex sibling
  - removed nested `max-height: 260px` optional-panel scroll trap
- `studio-web/src/components/dashboard/NewProductionCard.tsx`
  - `data-testid="create-project-modal-body"` on the scroll region
  - Optional settings expand into the scroll body
  - Browse templates instead expands an in-modal template list
  - `scrollIntoView({ block: "nearest", behavior: "smooth" })` after expansion
- `studio-web/src/pages/Home.tsx`
  - template selection from modal stays on Home
- `studio-web/src/components/ui/dialog.css`
  - audited/hardened shared Dialog for max-height, `min-height: 0`, and body scroll
- `tests/e2e/home/project-creation-modal.spec.ts`
  - Scenario J: Expanded Content Scroll

## Structure

```text
Modal shell (max-height, overflow hidden, flex column)
├── Fixed header
├── Content slot (min-height: 0, overflow hidden)
│   └── Form (flex column, min-height: 0)
│       ├── Scrollable body (overflow-y: auto)
│       └── Fixed footer (Cancel / Create Project)
```

## Test Summary

- Passed: `npm --prefix studio-web run build`
- Passed: `npx playwright test tests/e2e/home/project-creation-modal.spec.ts --project=chromium --reporter=line`
- Passed: `npx playwright test tests/e2e/home/home-project-creation-audit.spec.ts --project=chromium --reporter=line`
- Beta restarted after build and remained READY after certification

## Expanded Content Scroll Evidence

Scenario J covered:

- `1440 × 900`
- `1280 × 720`
- narrow `390 × 844`
- `1440 × 900` at 200% CSS zoom

Assertions verified:

- modal remains within the viewport after expansion
- body `scrollHeight > clientHeight`
- body `overflow-y` is `auto` or `scroll`
- final optional / template controls remain reachable after scrolling
- Cancel and Create Project remain visible
- page background remains overflow-locked
- keyboard PageDown and CDP mouse-wheel scrolling move the body

Manual Beta probe after Optional settings expand:

- body `clientHeight=532`, `scrollHeight=723`, `overflowY=auto`
- panel within viewport
- footer visible
- `document.body.style.overflow === "hidden"`

## Hard Requirement Status

- Expanding Optional settings / Browse templates / refine content does not push controls beyond reach
- Modal body owns vertical scrolling
- Page background remains locked
- Header and footer remain visible
- Create Project remains reachable
- Responsive + 200% zoom Playwright coverage passed
- Remains a centered modal (no drawer regression)

## Artifacts

- `docs/release-gate/home/artifacts/project-creation-modal/`
  - `expanded-content-scroll-1440x900.png`
  - `expanded-content-scroll-1280x720.png`
  - `expanded-content-scroll-narrow-390x844.png`
  - `expanded-content-scroll-1440x900-zoom-200.png`
  - `manual-optional-expanded-scroll.png`

## Manual Review Path

1. Open `http://127.0.0.1:8760/`
2. Click `+ Create Project`
3. Expand `Optional settings` and confirm the body scrolls while Cancel / Create Project stay visible
4. Collapse optional settings, expand `Browse templates instead`, and scroll to the last template option
5. Repeat at a short viewport such as `1280 × 720`

## Limitations

- 200% zoom in Playwright is exercised via `document.documentElement.style.zoom = 2` rather than OS-level browser UI zoom.
- Whole-application entry-closure suite was not re-run in this scroll-repair pass; modal + Home creation audit suites were.

## Verdict

**GO**
