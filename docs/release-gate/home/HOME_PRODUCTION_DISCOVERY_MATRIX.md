# Home + Production Discovery Matrix

> Canonical source of truth for which workspaces appear on Home (Explore Adept UI) vs. the global Production menu.
> Generated from `studio-web/src/core/exploreWorkspaces.ts` and `studio-web/src/core/productionMenu.ts`.
> This matrix exists to stop menu-vs-Home drift (Build Law #18: one source of truth).

**Branch:** `feature/ai-guided-setup` @ `fa09c99`
**Beta UI:** http://127.0.0.1:8760/  ·  **API:** http://127.0.0.1:8758/

## Canonical roster (Option A — expanded Explore grid, 11 cards)

| # | Workspace ID | Home Explore card | Production menu | Menu category | WorkspaceDefinition | Route | Artwork |
|---|---|---|---|---|---|---|---|
| 1 | `timeline` | ✅ | ✅ | Production | `workspaces.timeline` | `?workspace=timeline` | — |
| 2 | `magi` | ✅ | ✅ | Production | `workspaces.magi` | `?workspace=magi` | — |
| 3 | `brandstudio` | ✅ | ✅ | Production | `workspaces.brandstudio` | `?workspace=brandstudio` | `ws-brand.jpg` ✨ |
| 4 | `spatial` | ✅ | ✅ | Pre-Production | `workspaces.spatial` | `?workspace=spatial` | — |
| 5 | `posecraft` | ✅ **NEW** | ✅ **NEW** | Pre-Production | `workspaces.posecraft` **NEW** | `?workspace=posecraft` | `ws-posecraft.jpg` ✨ |
| 6 | `imagegen` | ✅ | ✅ | Production | `workspaces.imagegen` | `?workspace=imagegen` | — |
| 7 | `txt2vid` | ✅ | ✅ | Production | `workspaces.txt2vid` | `?workspace=txt2vid` | — |
| 8 | `avatar` | ✅ | ✅ | Production | `workspaces.avatar` | `?workspace=avatar` | — |
| 9 | `voicestudio` | ✅ | ✅ | Production | `workspaces.voicestudio` | `?workspace=voicestudio` | `ws-voice.jpg` ✨ |
| 10 | `audiostudio` | ✅ | ✅ | Production | `workspaces.audiostudio` | `?workspace=audiostudio` | `ws-audio.jpg` ✨ |
| 11 | `library` | ✅ | ✅ | Production | `workspaces.library` | `?workspace=library` | — |

✨ = production-quality artwork added/replaced in this milestone.

## Project templates

| Template ID | Title | primaryProjectType (frontend) | Resolved backend type | projectTraits | Image |
|---|---|---|---|---|---|
| `web-series` **NEW** | Web Series | `series` | `web_series` (subtype promoted by resolve engine) | `["web_series"]` | `template-dialogue.jpg` |
| `brand-ad` **NEW** | Brand Ad | `commercial` | `brand_ad` (subtype promoted by resolve engine) | `["brand_ad"]` | `template-commercial.jpg` |

Backend `brand_ad` profile added to `studio-api/app/templates_presets/catalog/project_types.py` (parent `commercial`, group `advertising`) and registered as a `commercial` subtype; commercial-subtype expansion loop mirrors the existing social/trailer pattern.

## Drift controls (centralization)

- `WorkspaceDefinition` lives once in `studio-web/src/core/workspaces.ts`; both `exploreWorkspaces.ts` and `productionMenu.ts` reference the same IDs/labels, so adding a workspace in one place propagates to both surfaces.
- `ProjectTemplateDef` (with `projectTraits`) lives once in `studio-web/src/dashboardImages.ts`; `projectTypes.ts` mirrors backend subtypes.
- The Explore audit spec (`explore-workspaces-audit.spec.ts`) and the new discovery-expansion spec both assert the canonical 11-card roster, so future drift fails CI.

## Notes / limitations

- PoseCraft is shipped as an **Experimental** creator-first landing surface (`PoseCraftWorkspace`). The full Babylon.js posing runtime is delivered in the parallel PoseCraft v1.1 worktree (`feature/posecraft-v1-1-foundation`) and integrates via a reviewed merge; this milestone wires discovery + routing + honest Experimental labelling only.
- The protected Manual Beta Handoff project `77a4b96c-…` is not present in this Beta DB (404 pre-existing); it is only ever read (GET) by certification, never written or deleted.
