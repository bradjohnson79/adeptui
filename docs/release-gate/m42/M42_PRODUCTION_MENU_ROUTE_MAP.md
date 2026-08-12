# M42 — Production Menu Route Map

Declarative catalog: `studio-web/src/core/productionMenu.ts`  
Availability resolver: `studio-web/src/core/productionAvailability.ts`  
Recent list: `studio-web/src/core/productionRecent.ts`  
UI: `studio-web/src/components/dashboard/ProductionMenu.tsx`

## Locked category IDs (v2 — production-stage oriented)

```text
create
profiles
pre-production
creative-studios
post-production
```

Legacy IDs (retired): `scene-generation`, `production-profiles`, `pre-production-tools`, `studios`.

## Menu structure

```text
✦ Co-Director (featured panel)
  Continue Project · Review Timeline · Generate Assets · Open Chat

CREATE
  Text to Video · Image Generation · 1 Frame · 3 Frame · Storyboard · Timeline Generator

PROFILES
  Character Creator · Project Profile · Production Bible

PRE-PRODUCTION
  Continuity · Scriptwriter · Scene Master Sheet · Spatial Map

CREATIVE STUDIOS
  Avatar Studio · Brand Studio · Audio Studio

POST
  MAGI Editor

Recent
  (session jump list)
```

## Route map

| Visible label | Workspace ID | Canonical route | Legacy aliases / notes |
|---|---|---|---|
| Co-Director | *(action)* | `/co-director?projectId={id}` | Featured panel + chrome trailing |
| Continue Project | `home` | `workspace=home` | Co-Director quick action |
| Review Timeline | `timeline` | `workspace=timeline` | Co-Director quick action |
| Generate Assets | `imagegen` | `workspace=imagegen` | Co-Director quick action |
| Open Chat | *(action)* | `/co-director?projectId={id}` | Co-Director quick action |
| Text to Video | `txt2vid` | `workspace=txt2vid` | text-to-video, txt2vid |
| Image Generation | `imagegen` | `workspace=imagegen` | image, image-gen |
| 1 Frame | `one` | `workspace=one` | one-frame |
| 3 Frame | `three` | `workspace=three` | three-frame |
| Storyboard | `script` | `workspace=script` | story; prior “Script / Storyboard”; now under **Create** |
| Timeline Generator | `timeline` | `workspace=timeline` | director; sits after Storyboard |
| Character Creator | `characters` | `workspace=characters` | prior “Character Profiles”; identityregistry → Approved Look |
| Project Profile | `profiles` | `workspace=profiles` | prior “Production DNA Profile” / Profiles |
| Production Bible | `bible` | `workspace=bible` | production-bible |
| Continuity | `continuity` | `workspace=continuity` | Continuity Workspace |
| Scriptwriter | `scriptwriter` | `workspace=scriptwriter` | script-writer |
| Scene Master Sheet | `mastersheet` | `workspace=mastersheet` | scene-sheets |
| Spatial Map | `spatial` | `workspace=spatial` | blocking |
| Avatar Studio | `avatar` | `workspace=avatar` | requires Character Creator selection |
| Brand Studio | `brandstudio` | `workspace=brandstudio` | brand |
| Audio Studio | `audiostudio` | `workspace=audiostudio` | audio |
| MAGI Editor | `magi` | `workspace=magi` | magi-editor, editor |

## Gate flags

| Flag | Intent |
|---|---|
| `productionMenuCatalogOperational` | Declarative catalog (not workspace auto-merge) |
| `productionMenuFiveCategoriesOperational` | Locked v2 category IDs |
| `productionMenuCoDirectorFeatured` | Featured Co-Director panel with quick actions |
| `productionMenuCreatorLabelsOperational` | Project Profile / Character Creator / Create labels |
| `productionMenuIdentityRegistryStandaloneRemoved` | No standalone Identity Registry item |
| `productionMenuLegacyIdentityRedirectOperational` | identityregistry → Character Creator → Approved Look |
| `productionMenuAvatarProfileBindingOperational` | Avatar requires selected character |
| `productionMenuAvailabilityHonest` | Named availability keys |
| `productionMenuHelpOperational` | Shared HelpTip |
| `productionMenuKeyboardOperational` | Arrow / Escape / focus restore |
| `productionMenuResponsiveOperational` | ≥1100 / 760–1099 / &lt;760 |
| `productionMenuProjectContextPreserved` | Navigations keep projectId |
| `productionMenuRecentOperational` | Recent jump list |
| `productionMenuNoDeadDestinations` | Visible items open real workspaces |
| `productionMenuPlaywrightPassed` | `tests/e2e/m42/m42-production-menu.spec.ts` |

## Design note — production stages

Long-term launcher orientation follows filmmaker stages rather than software modules:

```text
Develop idea → Design project → Build characters → Create content
→ Assemble timeline → Edit → Finish
```

Create → Profiles → Pre-Production → Creative Studios → Post mirrors that journey.
