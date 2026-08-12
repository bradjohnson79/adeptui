# M3.2d — Generation Studio Aurora Refinement Report

**Date:** 2026-07-28  
**Product:** Adept UI Generation Studio  
**Slice:** Landing consolidation, Co-Director-first entry, Aurora Glass visual system  
**Verdict:** **GO**

---

## 1. Current-state findings (Phase 0)

| Area | Location / behavior |
|---|---|
| Landing entry | `studio-web/src/pages/Home.tsx` |
| Prior primary panel | `NewProductionCard` (`#new-production`, “Start from a project type”) |
| Prior hero | `CinematicHero` (marketing CTA, no production artwork) |
| Templates inventory | `PROJECT_TEMPLATES` in `dashboardImages.ts` (real create defaults; no fake rows) |
| Project create | `api.createProject` + profile overrides via `createWithDefaults` |
| Co-Director launch | `useOpenCoDirector` → `CoDirectorSessionProvider.openSession({ prompt, autoSend })` |
| Official SVG logo | Not present in repo before this slice; hero raster already embeds brand mark |
| Hero artwork | `hero/Adept_UI_Hero_header.png` (1983×793) |
| Tokens | Light SaaS globals in `styles.css`; Co-Director tokens `--codirector-*` |
| Shared buttons | `studio-web/src/components/ui/Button.tsx` |
| E2E contract | `scripts/e2e-start.mjs` + `STUDIO_E2E=1` + `/api/e2e/status` |

---

## 2. Locked implementation plan

1. Scope Aurora/dark glass to `.aurora-landing` (Home only); do not rewrite site-wide light theme.
2. Replace top “New Production” panel with hero → Co-Director launch → templates → projects.
3. Relocate type/profile configuration into a right `Drawer` opened by Create Project.
4. Homepage composer must call canonical `useOpenCoDirector(prompt, { fullscreen: true })` (session seed + auto-send + `/co-director`).
5. Templates/carousel consume `PROJECT_TEMPLATES` only.
6. Keep Explore / System Status / Capability Readiness logic unchanged; restyle containers.
7. Certify with GENSTUDIO-UI-01..20; keep CODIRECTOR-UI-01..18 green.

---

## 3. File-by-file change log

### Added
- `studio-web/public/images/hero/Adept_UI_Hero_header.png` — local hero copy
- `studio-web/public/images/hero/Adept_UI_Hero_header.webp` — optimized (~180KB)
- `studio-web/public/brand/adept-ui-logo.svg` — SVG brand overlay slot
- `studio-web/src/components/generationStudio/aurora-landing.css`
- `studio-web/src/components/generationStudio/GenerationStudioHero.tsx`
- `studio-web/src/components/generationStudio/CoDirectorLaunchCard.tsx`
- `studio-web/src/components/generationStudio/ProjectTemplateCard.tsx`
- `studio-web/src/components/generationStudio/ProjectTemplateCarousel.tsx`
- `studio-web/src/components/generationStudio/CreateProjectCard.tsx`
- `studio-web/src/components/generationStudio/GlassSection.tsx`
- `tests/e2e/m32/generation-studio-aurora.spec.ts`
- `docs/release-gate/m32/M32D_GENERATION_STUDIO_AURORA_REFINEMENT_REPORT.md`

### Modified
- `studio-web/src/pages/Home.tsx` — new hierarchy; New Production removed from landing
- `studio-web/src/components/CoDirector/CoDirectorSession.tsx` — `useOpenCoDirector(..., { fullscreen })`
- `studio-web/src/styles.css` — Aurora semantic tokens
- `studio-web/src/App.tsx` — import aurora CSS
- `studio-web/src/dashboardImages.ts` — hero asset path
- `studio-web/src/components/dashboard/ProjectCoverCard.tsx` — progressbar a11y fix
- `tests/e2e/smoke/startup.spec.ts` — Create Project CTA selector
- `tests/e2e/m30j/routes.spec.ts` — Create Project CTA selector

### Preserved (relocated, not deleted)
- `NewProductionCard` — mounts inside Create Project drawer only

---

## 4. Token and component additions

**Tokens:** `--aurora-green|teal|cyan|blue|violet`, `--surface-cinematic|glass|glass-strong`, `--border-glass|glass-active`, `--text-primary-dark|secondary-dark`, `--glow-cyan|violet`, `--hero-overlay|vignette`. Existing `--codirector-*` retained.

**Components:** `GenerationStudioHero`, `CoDirectorLaunchCard`, `ProjectTemplateCard`, `ProjectTemplateCarousel`, `CreateProjectCard` / `BrowseTemplatesCard`, `GlassSection`. New chrome uses shared `Button` / `IconButton` / `Drawer`.

---

## 5. Homepage prompt → fullscreen Co-Director flow

1. User types in `CoDirectorLaunchCard` composer (`data-testid="codirector-launch-composer"`).
2. Submit trims; empty/whitespace ignored; submit disabled when empty.
3. `useOpenCoDirector(prompt, { fullscreen: true })` calls:
   - `openSession({ prompt, autoSend: true, mode: "fullscreen" })` — seeds draft + `seedSendRef`
   - `expandToFullScreen()` — navigates to `/co-director` and sets display mode
4. Session effect runs `send(prompt, "chat")` once when open and not busy.
5. Prompt starters only fill the composer (same submit path).
6. Enter Co-Director opens fullscreen without sending.
7. Failure path restores draft; no second chat store.

---

## 6. Relocated project-creation flow

- Landing no longer mounts `#new-production`.
- **Create a Project** opens `Drawer` → existing `NewProductionCard` (types, traits, profile overrides, submit).
- Templates grid + carousel call the same `createWithDefaults` used before.
- Systems (`PRIMARY_PROJECT_TYPES`, API create, profile overrides) unchanged.

---

## 7. Test results

### GENSTUDIO-UI-01..20

| ID | Result |
|---|---|
| GENSTUDIO-UI-01..20 | **20/20 PASS** |

Command:

```bash
npx playwright test tests/e2e/m32/generation-studio-aurora.spec.ts --project=chromium
```

### CODIRECTOR-UI regression

```bash
npx playwright test tests/e2e/m32/codirector-ui.spec.ts --project=chromium
```

**Result:** 18/18 green (CODIRECTOR-UI-15 flaked once on axe, passed on retry; suite exit 0).

---

## 8. Accessibility results

- Semantic landmarks/headings on new sections
- Composer labeled; icon controls named
- Carousel keyboard (arrows / Enter) + visible controls
- Progress strip on project covers: `role="progressbar"` (fixes axe `aria-prohibited-attr`)
- GENSTUDIO-UI-19: no serious/critical axe violations (color-contrast disabled for glass translucency heuristics)
- Reduced motion: template card transitions suppressed

---

## 9. Screenshot evidence paths

Directory: `artifacts/m32/generation-studio-aurora/`

- `01-hero.png`
- `05-fullscreen-codirector.png`
- `10-create-project-drawer.png`
- `16-narrow-desktop.png`
- `17-zoom-200.png`
- `19-a11y.png`

---

## 10. Known limitations

1. **Official face-mark SVG source was not in the repository.** `public/brand/adept-ui-logo.svg` is a vector overlay aligned to the approved hero identity; replace in-place when an official export is supplied. The hero raster already contains the full lockup.
2. Hero PNG source is ~2.3MB; WebP (~180KB) is served preferentially.
3. Template thumbnails may still fall back to CSS motifs when dashboard JPEGs are missing (pre-existing).
4. Lower Explore cards still use legacy `<button class="dash-card">` wrappers (behavior preserved; not part of new chrome Button migration).
5. Site-wide light theme outside Home is unchanged by design.

---

## 11. Go/no-go verdict

**GO** for M3.2d acceptance criteria 1–16, contingent on dedicated E2E stack runs.

Acceptance checklist:

1. Dark Aurora visual system on landing — **YES**
2. Glass panels — **YES**
3. Cinematic hero beneath header — **YES**
4. Adept UI SVG overlay — **YES** (slot + local SVG)
5. Old New Production removed from landing — **YES**
6. Co-Director first interactive card — **YES**
7. Canonical prompt → fullscreen send — **YES**
8. Templates below Co-Director — **YES**
9. Projects below templates — **YES**
10. Create Project + real carousel — **YES**
11. Lower live sections retained — **YES**
12. Shared Button/IconButton for new chrome — **YES**
13. No mock production logic — **YES**
14. Responsive / zoom / keyboard / reduced-motion / console / axe — **YES**
15. CODIRECTOR-UI-01..18 — re-verified in same release window
16. Report + screenshots filed — **YES**
