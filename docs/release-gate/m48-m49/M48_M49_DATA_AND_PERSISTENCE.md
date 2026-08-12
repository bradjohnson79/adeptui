# M48 / M49 Data & Persistence

Wave 1 contracts for Cinematic Image Studio + Professional Storyboard Studio.

## Packages

| Package | Role |
| --- | --- |
| [`studio-api/app/image_studio/`](../../../studio-api/app/image_studio/) | Cinematic request contracts, Visual Continuity Session store, compile-preview API |
| [`studio-api/app/storyboard_studio/`](../../../studio-api/app/storyboard_studio/) | StoryboardDocument/Page over `storyboard_panels`, script sync map, timeline prep proposals |
| [`studio-web/src/contracts/`](../../../studio-web/src/contracts/) | TS mirrors for FE |

## Visual Continuity Session

**Shape (mandatory):**

```ts
type VisualContinuitySession = {
  id: string;
  projectId: string;
  sceneId?: string;
  characterIds: string[];
  locationIds: string[];
  costumeIds: string[];
  projectStyleVersion?: string;
  referenceAssetIds: string[];
  approvedImageIds: string[];
  createdAt: string;
  updatedAt: string;
};
```

Optional cinematic locks (session-level, not a creator dashboard): `lightingDirection`, `colorTreatment`, `lensLanguage`, `aspectRatio`, `visualEra`, `productionStyle`.

**Persistence:** JSON under `data/visual_continuity/{projectId}/sessions.json`

**API:** `/api/image-studio/projects/{projectId}/continuity-sessions*`

**Creator UX (Wave 3):** Continuity → `[ Inherit from scene ]` → `POST .../inherit-from-scene`

**Compile path:** `image_product/compile.py` merges session extras when `continuitySessionId` / `continuityId` is present. Provenance metadata records `continuitySessionId`.

## Storyboard documents

**Model:** `StoryboardDocument` + `StoryboardPage` (pageSize 6|9|12, default **9**) layered over existing `storyboard_panels` rows. Panel pixels/status remain in SQL; page layout/order in JSON.

**Persistence:** `data/storyboard_studio/{projectId}/documents.json`

**Timeline prep:** `data/storyboard_studio/{projectId}/timeline_proposals.json` — proposal-only; no silent clip generation.

**API:** `/api/storyboard-studio/projects/{projectId}/...`

## Script sync unification

Mission statuses: `linked` | `script_updated` | `override` | `conflict` | `unlinked`

| Legacy panel `script_sync_status` | Mission |
| --- | --- |
| `ok`, `non_visual` | `linked` |
| `script_changed`, `needs_regen` | `script_updated` |
| `override` / `conflict` / `unlinked` | same |

| Scriptwriter `sceneSync` | Mission |
| --- | --- |
| `synced`, `linked` | `linked` |
| `stale` | `script_updated` |
| `unlinked` / `conflict` / `override` | same |

## Cinematic → Image Product mapping

`CinematicGenerateRequest` → `cinematic_to_image_product_body()` → existing `POST /api/image-product/.../generate`. No second queue.

## Do not reinvent

Image Product compile/queue/runtime, certified registry, Production Dock resolve, storyboard_panels SQL, Scriptwriter prepare_timeline shape.
