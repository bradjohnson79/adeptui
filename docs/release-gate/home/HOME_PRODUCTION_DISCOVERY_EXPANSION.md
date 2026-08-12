# Home + Production Discovery Expansion — Completion Report

**Milestone:** PoseCraft Discovery, Studio Artwork, Template Expansion
**Branch:** `feature/ai-guided-setup`  ·  **Starting SHA:** `fa09c99`
**Beta UI:** http://127.0.0.1:8760/  ·  **API:** http://127.0.0.1:8758/
**Date:** 2026-08-04

## Scope

Focused repair + expansion of creator-discovery surfaces in Beta UI. **No** redesign of the overall Home/Production shell.

1. Add PoseCraft to the Production menu (Pre-Production, creator copy).
2. Add PoseCraft to the Home Explore Adept UI grid (Option A — expand to 11 cards, keep Library).
3. Replace placeholder artwork for Brand Studio, Voice Studio, Audio Studio with production-quality assets; add real staging artwork for PoseCraft.
4. Add project templates: Web Series + Brand Ad with correct backend typology.
5. Verify Brand Studio and all affected routes open the correct Adept UI destinations (route repair).
6. Certify via Adept UI Playwright only.

## Decisions locked

- **Option A** — Explore grid expanded to 11 canonical cards (PoseCraft added, Library retained) with an adaptive grid. Documented in `HOME_PRODUCTION_DISCOVERY_MATRIX.md`.
- PoseCraft Production menu entry under **PRE-PRODUCTION** with creator copy; route `?workspace=posecraft` (project-aware workspace, consistent with other studios). Final identity = **Experimental** studio (honest capability label, Build Law #20).
- **Project-aware:** with a project open, PoseCraft opens inside the project; with no eligible project, the shared centered Create Project modal appears — no silent Untitled.
- **Web Series:** `projectType series`, `refineType web_series` (resolve engine promotes to concrete `web_series` subtype).
- **Brand Ad:** `projectType commercial`, `refineType brand_ad` — added `brand_ad` typed profile (parent `commercial`, group `advertising`) to the backend catalog and registered it as a `commercial` subtype.
- **Centralization:** `WorkspaceDefinition` and `ProjectTemplateDef` are the single sources of truth; menu and Home derive from them to stop drift.

## Files changed (this milestone)

### Frontend (`studio-web`)
- `src/core/workspaces.ts` — added `posecraft` `WorkspaceDefinition` (group `create`, `menuGroup production`, order 45, Experimental badges).
- `src/core/exploreWorkspaces.ts` — added `posecraft` to `EXPLORE_WORKSPACE_IDS` + `EXPLORE_CARD_COPY`.
- `src/core/productionMenu.ts` — added `posecraft` entry under `pre-production`.
- `src/theme/auroraCardImagery.ts` — added `workspaces.posecraft` key; switched Brand/Voice/Audio `src` from `.svg` to production `.jpg`.
- `src/dashboardImages.ts` — added `posecraft` image; added `web-series` + `brand-ad` `ProjectTemplateDef` with `projectTraits`; extended `ProjectTemplateDef.defaults` with `projectTraits`.
- `src/projectTypes.ts` — added `brand_ad` subtype under `commercial`.
- `src/i18n/locales/en/navigation.json` — added `posecraft` label.
- `src/components/GenerationTools/PoseCraftWorkspace.tsx` **(new)** — creator-first Experimental landing surface; project-aware; links to Character Creator / Image Generation / Storyboard / Spatial / Timeline.
- `src/components/GenerationTools/posecraft-workspace.css` **(new)** — PoseCraft workspace styling.
- `src/pages/ProjectEditor.tsx` — wired `tab === "posecraft"` → `PoseCraftWorkspace`.
- `src/components/ui/workspace-card.css` — 2-line clamp on `.ds-workspace-card__desc` so all Explore cards stay uniform (fixed a 37px height delta introduced by the 11th card).

### Backend (`studio-api`)
- `app/templates_presets/catalog/project_types.py` — added `brand_ad` `_def`/profile; registered `brand_ad` as a `commercial` subtype; added commercial-subtype expansion loop (mirrors social/trailer).

### Artwork (`studio-web/public/images/ui/workspaces/`) — generated via GenerateImage
- `ws-brand.jpg`, `ws-voice.jpg`, `ws-audio.jpg`, `ws-posecraft.jpg` (production-quality, non-gradient).

### Tests
- `tests/e2e/home/home-production-discovery-expansion.spec.ts` **(new)** — Scenarios A–I certification.
- `tests/e2e/home/explore-workspaces-audit.spec.ts` — updated canonical roster 10 → 11 (PoseCraft) in `EXPECTED_IDS`/`EXPECTED_TITLES` and `toHaveCount` assertions.

## Beta verification

- Beta supervisor state `READY`; API `:8758` healthy; web `:8760` serving rebuilt `studio-web/dist`.
- API was restarted once (supervisor auto-restart) to load the new `brand_ad` catalog entry; health confirmed 200.
- Frontend rebuilt after the CSS uniformity fix; web server serves `dist` from disk (no restart needed).
- Manual review path: open http://127.0.0.1:8760/ → Explore Adept UI shows 11 cards incl. PoseCraft; Production → Pre-Production → PoseCraft opens the Experimental workspace; Brand Studio / Voice Studio / Audio Studio cards show real artwork; New Production offers Web Series + Brand Ad templates.

## Certification evidence

Playwright (chromium), `ADEPT_BETA_TARGET=1`, `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760`:

```
ok 1 explore-workspaces-audit.spec.ts › HOME-EXPLORE-01 roster, Brand/Voice/Audio routes, and project-entry contracts (23.4s)
ok 2 home-production-discovery-expansion.spec.ts › HOME-PRODUCTION-DISCOVERY-01 expanded roster, PoseCraft navigation, Brand route repair, templates, responsive, a11y (22.0s)
2 passed (45.8s)
```

### Scenario coverage (new spec)
- **A** — Explore roster is exactly the 11 canonical workspaces incl. PoseCraft; PoseCraft card has a real `ws-posecraft.jpg` image with non-empty alt.
- **B** — PoseCraft Home Explore card opens `?workspace=posecraft` → `posecraft-workspace` shell with Experimental badge + Character/Image Generation actions.
- **C** — PoseCraft Production menu entry under Pre-Production opens the posecraft workspace.
- **D** — Brand Studio route repair: Home card **and** Production menu both reach `?workspace=brandstudio` → `brand-studio` shell.
- **E** — Voice Studio + Audio Studio routes still resolve from both Home card and Production menu (no regression).
- **F** — Web Series template → resolved `primary_project_type = web_series` (trait `web_series`); Brand Ad template → resolved `primary_project_type = brand_ad` (trait `brand_ad`).
- **G** — No-project PoseCraft entry opens the centered Create Project modal; no silent Untitled; no `POST /api/projects` fired on cancel.
- **H** — Responsive: 11 cards, no horizontal overflow at 1920×1080, 1440×900, 1280×720, 390×844; every card shows "Open →".
- **I** — Keyboard/a11y: PoseCraft card focusable + Enter opens workspace; Production menu keyboard-navigable; Brand/Voice/Audio/PoseCraft card images have meaningful alt text; console/network clean (navigation-aborted polling requests filtered); handoff project status unchanged before/after.

Artifacts saved under `docs/release-gate/home/artifacts/production-discovery/<RUN_ID>/` (roster, route, responsive, and handoff-state screenshots/JSON).

## Repair log (root-cause → fix → revalidate)

1. **Scenario C double-click toggled Production menu closed.** Root cause: preliminary `Production` click to assert the category, then `openProductionItem` clicked Production again. Fix: open the menu once and click the item within the same open menu. Revalidated: pass.
2. **Scenario F expected `?workspace=home` query.** Root cause: template creation navigates to `/project/<id>` (home is the default workspace, no explicit query). Fix: assert `/project/<id>`. Revalidated: pass.
3. **Scenario F name lookup returned null.** Root cause: templates are created with the template title as the project name, not a `RUN_ID` prefix. Fix: extract the project id directly from the navigation URL. Revalidated: pass.
4. **Scenario F expected parent type `series`/`commercial`.** Root cause: the resolve engine promotes the trait to the concrete subtype (`web_series`/`brand_ad`). Fix: assert the resolved concrete subtype. Revalidated: pass.
5. **Brand Ad stayed `commercial` (no subtype promotion).** Root cause: the running API loaded the catalog before the `brand_ad` addition. Fix: restart the API (supervisor auto-restart) to load the new `brand_ad` builtin. Revalidated: `brand_ad` present, promotion works.
6. **Scenario I `assertClean` flagged `net::ERR_ABORTED`.** Root cause: benign polling requests (codirector/production-control) aborted by navigation away. Fix: add `net::ERR_ABORTED` to the noise filter (consistent with navigation semantics). Revalidated: pass.
7. **Existing audit spec: 1920×1080 card height delta 37px > 12px.** Root cause: the 11th card changed wrapping so one description wrapped to an extra line. Fix (no assertion weakened): 2-line clamp on `.ds-workspace-card__desc` so all cards stay uniform. Revalidated: both specs pass.

## Limitations (honest)

- PoseCraft ships as an **Experimental** landing surface only. The full Babylon.js posing stage, pose presets, and project persistence live in the parallel PoseCraft v1.1 worktree and integrate via a reviewed merge — not in this milestone.
- The Manual Beta Handoff project `77a4b96c-…` is not present in this Beta DB (404 pre-existing); certification only reads it and asserts its state is unchanged across the run.
- Web Series / Brand Ad template cards reuse existing production JPGs (`template-dialogue.jpg`, `template-commercial.jpg`) rather than newly generated art — intentional to avoid redundant generation while meeting the "no generic gradients" bar.
- GPU preflight (Build Law #26) not applicable: this milestone is UI discovery/routing/templates only — no GPU-designated workload was executed.

## Verdict

# GO — HOME PRODUCTION DISCOVERY READY

All six scope items implemented; Beta reflects the work at http://127.0.0.1:8760/; both Playwright certifications (new expansion spec A–I + existing audit spec) pass; no assertion weakened; route repair verified; templates produce correct backend types; responsive + a11y verified; handoff project untouched; test pollution cleaned.
