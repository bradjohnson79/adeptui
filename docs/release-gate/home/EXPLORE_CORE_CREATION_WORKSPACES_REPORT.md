# Explore Core Creation Workspaces — Completion Report

**Milestone:** Home Discovery Addendum — Expand Explore Adept UI  
**Branch:** `feature/ai-guided-setup` · **Working SHA:** `fa09c99` (uncommitted local changes)  
**Beta UI:** http://127.0.0.1:8760/ · **API:** http://127.0.0.1:8758/  
**Date:** 2026-08-04

## Scope

Expand **Explore Adept UI** on Home with four canonical creation workspaces integrated into the existing visual system:

1. **1 Frame** — Animate a single keyframe into a cinematic shot.
2. **3 Frame** — Build motion from start, middle, and end frames.
3. **Character Creator** — Design character identity, appearance, wardrobe, voice, and continuity.
4. **Scriptwriter** — Write and organize professional scripts, scenes, and dialogue.

All prior Explore cards retained. Library remains last. Roster order:

`Timeline → MAGI Editor → Brand Studio → Spatial Map → PoseCraft → Image Generation → Text to Video → 1 Frame → 3 Frame → Character Creator → Scriptwriter → Avatar Studio → Voice Studio → Audio Studio → Library` (**15 cards**).

Centralization: roster driven from `exploreWorkspaces.ts` + `WORKSPACES` registry — no Home-only hardcoding.

## Files changed

### Frontend (`studio-web`)

| File | Change |
|---|---|
| `src/core/exploreWorkspaces.ts` | Added `one`, `three`, `characters`, `scriptwriter` to `EXPLORE_WORKSPACE_IDS` + `EXPLORE_CARD_COPY` |
| `src/theme/auroraCardImagery.ts` | Added `workspaces.oneFrame`, `threeFrame`, `characterCreator`, `scriptwriter` imagery keys |
| `src/dashboardImages.ts` | Wired `oneFrame`, `threeFrame`, `characterCreator`, `scriptwriter` dashboard images |
| `public/images/ui/workspaces/ws-one-frame.jpg` | **new** production card art |
| `public/images/ui/workspaces/ws-three-frame.jpg` | **new** production card art |
| `public/images/ui/workspaces/ws-character-creator.jpg` | **new** production card art (no mannequins) |
| `public/images/ui/workspaces/ws-scriptwriter.jpg` | **new** production card art |
| `public/images/ui/LICENSE.md` | Recorded new artwork license entries |

### Tests

| File | Change |
|---|---|
| `tests/e2e/home/explore-core-creation-workspaces.spec.ts` | **new** — 13-scenario certification for core creation expansion |
| `tests/e2e/home/explore-workspaces-audit.spec.ts` | Roster updated 11 → 15 cards |
| `tests/e2e/home/home-production-discovery-expansion.spec.ts` | Roster count updated 11 → 15 cards |

## Routes verified

| Explore card | Workspace param | Shell test id |
|---|---|---|
| 1 Frame | `?workspace=one` | `one-frame-panel` |
| 3 Frame | `?workspace=three` | `three-frame-panel` |
| Character Creator | `?workspace=characters` | `character-profile-workspace` |
| Scriptwriter | `?workspace=scriptwriter` | `scriptwriter-studio` |

Project-aware contract preserved: no eligible project → centered Create Project modal; Cancel creates nothing; submit continues into selected workspace with explicit name (no silent Untitled).

## Beta verification

- Beta restarted via `Restart-AdeptUI-Beta.ps1 -NoBrowser -Force` after `npm run build` in `studio-web`.
- Supervisor state: **READY**
- `GET http://127.0.0.1:8760/` → **200**
- `GET http://127.0.0.1:8758/api/health` → **200**
- Manual review: open http://127.0.0.1:8760/ → scroll to **Explore Adept UI** → confirm 15 cards in order with new JPG artwork on the four additions.

## Certification evidence

Playwright (chromium), `ADEPT_BETA_TARGET=1`, `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760`:

```
ok 1 explore-core-creation-workspaces.spec.ts › HOME-EXPLORE-CORE-01 roster, routes, project-entry, responsive, a11y (1.3m)
1 passed (1.3m)
```

```
ok 1 explore-workspaces-audit.spec.ts › HOME-EXPLORE-01 roster, Brand/Voice/Audio routes, and project-entry contracts (37.1s)
1 passed
```

### Scenario coverage (`explore-core-creation-workspaces.spec.ts`)

1. **Roster** — exactly 15 cards in canonical order with correct titles  
2. **Artwork/alt** — four new cards serve distinct JPGs with non-empty alt text  
3. **1 Frame route** — Home card → `?workspace=one` → `one-frame-panel`  
4. **3 Frame route** — Home card → `?workspace=three` → `three-frame-panel`  
5. **Character Creator route** — Home card → `?workspace=characters` → `character-profile-workspace`  
6. **Scriptwriter route** — Home card → `?workspace=scriptwriter` → `scriptwriter-studio`  
7. **No-project modal** — 1 Frame opens Create Project modal without POST  
8. **Cancel** — Character Creator cancel creates no project  
9. **Continue after create** — Scriptwriter flow creates named project and lands in scriptwriter workspace  
10. **Responsive** — 1920×1080, 1440×900, 1280×720, 390×844 — no overflow; Open → visible on all cards  
11. **Keyboard** — Enter and Space activate 3 Frame / 1 Frame cards  
12. **Existing cards** — Timeline, Library, PoseCraft spot-check routes still resolve  
13. **Console/network** — clean on 1 Frame open; protected handoff project `77a4b96c-…` status unchanged (404 pre-existing)

Handoff artifact: `docs/release-gate/home/artifacts/explore-core-creation/EXPLORE-CORE-2026-08-04T21-31-27-623Z/handoff-state.json`

## Regression note (out of scope)

`home-production-discovery-expansion.spec.ts` Scenario B fails on `posecraft-experimental-badge` visibility — PoseCraft workspace UI is under parallel PoseCraft mandatory GO work (badge/shell changed). This workstream did **not** modify PoseCraft figure/engine code. Explore roster count updates in that spec are correct; PoseCraft shell assertions are owned by the PoseCraft agent.

## Limitations (honest)

- GPU preflight (Build Law #26) not applicable — UI discovery/routing only.
- Protected project `77a4b96c-8e3f-4501-897c-51bab99bedb7` absent in Beta DB (404 pre-existing); certification asserts status unchanged only.
- Headless Playwright filters benign WebGPU/Babylon console noise when asserting clean console on lightweight workspaces.
- Changes are **uncommitted** per mission instructions.

## Verdict

**GO — EXPLORE ADEPT UI CORE CREATION WORKSPACES READY**
