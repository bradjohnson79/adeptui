# M42 — Production Categorized Creator Menu Report

**Status:** GO  
**Date:** 2026-07-31  
**Revision:** v2 — creator naming + Co-Director panel + Create flow + Recent  
**Runtime under test:** Adept UI Beta (`http://127.0.0.1:8760/`, API `:8758`)  
**Companion artifact:** [M42_PRODUCTION_MENU_ROUTE_MAP.md](./M42_PRODUCTION_MENU_ROUTE_MAP.md)

---

## Verdict

```text
GO — The Production menu is organized around production stages and creator
language: Create → Profiles → Pre-Production → Creative Studios → Post,
with a featured Co-Director panel and Recent jump list.
```

v2 refinements replace “DNA / Profiles / Scene Generation / Studios” developer framing with filmmaker-facing labels and flow. Storyboard sits with Timeline under **Create**. Co-Director is a featured action panel (Continue Project, Review Timeline, Generate Assets, Open Chat). Playwright suite covers the updated structure.

---

## Objective

Rebuild the **Production** dropdown into a categorized creator menu that:

1. Scans like a creative suite launcher (not a developer registry dump)
2. Uses creator-facing labels (`Text to Video`, `Image Generation`, `Timeline Generator`, `Storyboard`, …)
3. Removes **Identity Registry** as a competing standalone destination
4. Binds **Avatar Studio** to a selected Character Profile
5. Preserves project context, legacy routes, and honest availability badges
6. Meets keyboard, HelpTip, and responsive requirements

---

## Delivered architecture

| Layer | Path | Role |
|---|---|---|
| Declarative catalog | `studio-web/src/core/productionMenu.ts` | Labels, routes, help, availability keys; `buildProductionMenu(...)` — no HTTP |
| Availability resolver | `studio-web/src/core/productionAvailability.ts` | Named `ProductionAvailability` keys with dependency reasons |
| Launcher UI | `studio-web/src/components/dashboard/ProductionMenu.tsx` | Featured Co-Director + five category groups |
| Styles | `studio-web/src/components/dashboard/production-menu.css` | ≥1100 / 760–1099 / &lt;760 breakpoints |
| Chrome wiring | `studio-web/src/components/dashboard/AppChrome.tsx` | Replaces flat `productionItems` merge |
| Help | `studio-web/src/components/HelpTip.tsx` | Shared hover / focus / click / Escape pattern |
| Route map | `docs/release-gate/m42/M42_PRODUCTION_MENU_ROUTE_MAP.md` | Label → workspace → route → aliases |
| E2E | `tests/e2e/m42/m42-production-menu.spec.ts` | Structure, identity, avatar, responsive, keyboard |

```text
Production trigger
  → resolveProductionAvailability(health)
  → buildProductionMenu({ availability, projectId, selectedCharacterId })
  → ProductionMenu panel
       ├── ✦ Co-Director (featured)
       ├── scene-generation
       ├── production-profiles
       ├── pre-production-tools
       ├── studios
       └── post-production
```

Catalog and availability are intentionally separated: navigation definitions never fetch health.

---

## Locked category identifiers (v2)

```ts
type ProductionCategoryId =
  | "create"
  | "profiles"
  | "pre-production"
  | "creative-studios"
  | "post-production";
```

Test IDs: `production-cat-{id}` (e.g. `production-cat-create`).

---

## Locked menu structure (v2)

```text
Production
│
├── ✦ Co-Director                         (featured panel)
│   ├── Continue Project
│   ├── Review Timeline
│   ├── Generate Assets
│   └── Open Chat
│
├── Create
│   ├── Text to Video
│   ├── Image Generation
│   ├── 1 Frame
│   ├── 3 Frame
│   ├── Storyboard
│   └── Timeline Generator
│
├── Profiles
│   ├── Character Creator
│   ├── Project Profile
│   └── Production Bible
│
├── Pre-Production
│   ├── Continuity
│   ├── Scriptwriter
│   ├── Scene Master Sheet
│   └── Spatial Map
│
├── Creative Studios
│   ├── Avatar Studio
│   ├── Brand Studio
│   └── Audio Studio
│
├── Post
│   └── MAGI Editor
│
└── Recent
    └── (session jump list)
```

### Removed from Production menu (compat retained)

| Prior entry | Disposition |
|---|---|
| Identity Registry | `menuHidden`; legacy route → Character Profiles → Approved Look |
| Generation Tools | `menuHidden`; command palette / direct route remain |
| Lip Sync (hard-coded) | Removed from Production menu |

---

## Creator terminology

| Prior visible label | Current visible label | Workspace ID |
|---|---|---|
| Txt2Vid | Text to Video | `txt2vid` |
| ImageGen | Image Generation | `imagegen` |
| Timeline / Director | Timeline Generator | `timeline` |
| Script / Storyboard | Storyboard (under **Create**) | `script` |
| Production DNA Profile / Profiles | Project Profile | `profiles` |
| Character Profile(s) | Character Creator | `characters` |
| Scene Generation | Create | *(category)* |
| Studios | Creative Studios | *(category)* |
| Continuity Workspace | Continuity | `continuity` |
| Identity Registry | *(not a Production menu item)* | `identityregistry` → Approved Look tab |

Primary nav surfaces updated to match: workspace registry, `navigation.json`, Home explore cards, Project Home TAB_LABELS.

### Why these names

- **Project Profile** — clearer than “DNA” for new users  
- **Character Creator** — names the activity, not the data structure  
- **Create** — covers concepts, props, environments, stills — not only “scenes”  
- **Creative Studios** — room for Voice / Enhancement / Motion studios later  
- **Storyboard → Timeline** under Create — natural pre-edit assembly flow

---

## Identity Registry consolidation

| Rule | Implementation |
|---|---|
| No standalone Production menuitem | `identityregistry.menuHidden = true`; absent from catalog |
| Legacy route lands deterministically | `?workspace=identityregistry` → `CharacterProfileWorkspace` with `initialTab="identityRegistry"` |
| Tab rename | **Approved Look** (embedded registry UI retained) |
| Empty state | Creator “Choose a character” when no character selected |
| Context preserved | `projectId`, `characterId`, `identityId`, `return` via query/session |

Continuity CTA copy: **Open Character Profiles — Approved Look** (compat route still `identityregistry`).

---

## Avatar Studio binding

| Rule | Implementation |
|---|---|
| Requires selected Character Profile | No character → gate UI |
| Gate copy | “Choose a character to create an avatar.” |
| Actions | Choose Character / Open Character Profiles (+ project character select) |
| No orphan authority | Does not create “New Avatar Session” without a Character Profile id |
| Selection source | `?profile` / `?characterId` / `adept_selected_character` / `adept_avatar_profile` |

Character Profile selection writes `adept_selected_character` and dispatches `adept:selected-character` for chrome/menu awareness.

---

## Availability honesty

Named keys only:

```ts
textToVideo | imageGeneration | oneFrame | threeFrame | timeline | audioStudio
```

- Comfy-dependent generation tools receive Comfy/model dependency reasons when offline
- Timeline remains Available without Comfy (planning UI)
- Audio Studio uses audio-production operator readiness
- Badges explain the dependency; workspaces remain navigable when the UI is real

---

## UX / a11y / responsive

| Requirement | Result |
|---|---|
| Featured Co-Director | `data-testid="production-menu-codirector"` first menuitem |
| Shared HelpTip | `label` + `content`; hover, focus, click, Escape; portal positioning |
| Close on outside / navigate / Co-Director / Escape / project change | Implemented in ProductionMenu + AppChrome |
| Focus restore | Only when closing **without** navigating |
| Keyboard | Arrow / Home / End / Enter / Escape |
| SR categories | `role="group"` + `aria-labelledby` per locked category id |
| ≥1100px | Two-column launcher |
| 760–1099px | Single-column compact |
| &lt;760px | Full-width sheet / controlled scroll |

---

## Gate flags

| Flag | Result |
|---|---|
| `productionMenuCatalogOperational` | PASS |
| `productionMenuFiveCategoriesOperational` | PASS |
| `productionMenuCoDirectorFeatured` | PASS (featured panel + quick actions) |
| `productionMenuCreatorLabelsOperational` | PASS (Project Profile / Character Creator / Create) |
| `productionMenuIdentityRegistryStandaloneRemoved` | PASS |
| `productionMenuLegacyIdentityRedirectOperational` | PASS |
| `productionMenuAvatarProfileBindingOperational` | PASS |
| `productionMenuAvailabilityHonest` | PASS |
| `productionMenuHelpOperational` | PASS |
| `productionMenuKeyboardOperational` | PASS |
| `productionMenuResponsiveOperational` | PASS |
| `productionMenuProjectContextPreserved` | PASS |
| `productionMenuRecentOperational` | PASS |
| `productionMenuNoDeadDestinations` | PASS |
| `productionMenuPlaywrightPassed` | PASS (6/6) |

### Automatic NO-GO checks (none triggered)

- Identity Registry still a standalone Production item — **no**
- Avatar can create orphan character authority — **no**
- Legacy identity route loses project/character context — **no**
- Availability badges hardcoded / blanket Comfy for unrelated tools — **no**
- Categories from uncontrolled workspace auto-merge — **no**
- Narrow layouts clip required links — **no**
- Keyboard focus trapped/lost — **no**
- Help inaccessible without mouse — **no**
- Visible item opens dead/mock workspace — **no**

---

## Playwright evidence

**Suite:** `tests/e2e/m42/m42-production-menu.spec.ts`  
**Command:**

```bash
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760 npx playwright test tests/e2e/m42/m42-production-menu.spec.ts --project=chromium
```

**Result:** **6 passed**

| Test | Coverage |
|---|---|
| categorized menu: Co-Director panel + five locked categories | Create/Profiles structure, Storyboard under Create |
| legacy identityregistry lands on Approved Look with project context | Redirect + tab rename |
| Avatar Studio gates when no character selected | Binding rule |
| responsive: wide, compact, sheet | 1280 / 900 / 640 viewports |
| keyboard: open, arrow, Escape restores focus | Focus restore without navigate |
| Character Creator navigation preserves projectId and records Recent | Project context + Recent list |

Assertions use menu `data-testid`s and menuitem roles — not repository-wide text matching (avoids false fails on “Co-Director”, compatibility copy, etc.).

---

## Files touched (summary)

| Area | Files |
|---|---|
| Catalog / availability | `productionMenu.ts`, `productionAvailability.ts` |
| UI | `ProductionMenu.tsx`, `production-menu.css`, `AppChrome.tsx`, `HelpTip.tsx` |
| Labels | `workspaces.ts`, `i18n/locales/en/navigation.json`, `Home.tsx`, `ProjectHome.tsx` |
| Identity / Avatar | `CharacterProfileWorkspace.tsx`, `IdentityRegistryWorkspace.tsx`, `ProjectEditor.tsx`, `AvatarStudioWorkspace.tsx`, `ContinuityWorkspace.tsx` |
| Docs / tests | `M42_PRODUCTION_MENU_ROUTE_MAP.md`, `M42_PRODUCTION_CATEGORIZED_MENU_REPORT.md`, `m42-production-menu.spec.ts` |

---

## Out of scope (unchanged)

- Brand-new Production DNA product surface (label/bind of existing `profiles` only)
- Fully relocating Avatar Studio into Character Profile tabs
- Enhancement Studio / Phase 4.7 post-production entries

---

## Operator notes

1. Hard-refresh Beta UI after `studio-web` production build so static dist picks up the launcher.
2. Comfy down → Scene Generation badges may show **Local runtime offline**; UI/API remain usable (DEGRADED).
3. Select a Character Profile before opening Avatar Studio from Production, or use the gate’s Choose Character path.

---

## Final result

```text
GO — Production Categorized Creator Menu
```
