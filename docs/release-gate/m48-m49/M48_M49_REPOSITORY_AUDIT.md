# M48 / M49 Repository Audit

## M4.8–M4.9 Cinematic Image + Storyboard Studio — Wave 0 Audit Gate

| Field | Value |
| --- | --- |
| Mission | M4.8–M4.9 Cinematic Image + Storyboard Studio |
| Branch | `feature/m4-8-m4-9-cinematic-image-storyboard` |
| Repository | `C:\AdeptFilmWorks\AIVideoStudio` |
| Audit mode | Consolidation only (no feature implementation in Wave 0) |
| Verdict | **AUDIT_COMPLETE** |

---

## 1. Active image generation path

```
ImageGenPanel (workspace=imagegen)
  → api.imageProduct.generate
  → POST /api/image-product/projects/{id}/generate
  → apply_image_dock_preference → compile_image_request
  → Job(kind=imagegen|imagegen_edit)
  → queue_worker._imagegen
  → image_runtime contract + Comfy / hosted
  → Asset + provenance + optional storyboard panel writeback
```

### Frontend entry

- [`studio-web/src/pages/ProjectEditor.tsx`](../../../studio-web/src/pages/ProjectEditor.tsx) — mounts `ImageGenPanel` for `workspace=imagegen`
- [`studio-web/src/core/workspaces.ts`](../../../studio-web/src/core/workspaces.ts) — key `imagegen`, label `"Image Generation"`
- [`studio-web/src/components/ImageGenPanel.tsx`](../../../studio-web/src/components/ImageGenPanel.tsx) — active still-generation UI
- [`studio-web/src/api.ts`](../../../studio-web/src/api.ts) — `api.imageProduct.*`

### Backend product layer

- [`studio-api/app/image_product/api.py`](../../../studio-api/app/image_product/api.py)
- [`studio-api/app/image_product/service.py`](../../../studio-api/app/image_product/service.py) — `generate_images`, dock preference injection
- [`studio-api/app/image_product/compile.py`](../../../studio-api/app/image_product/compile.py) — creative context: cinematography, lighting, continuity, scene/shot/panel IDs
- [`studio-api/app/image_product/recommend.py`](../../../studio-api/app/image_product/recommend.py)
- [`studio-api/app/image_product/references.py`](../../../studio-api/app/image_product/references.py)
- [`studio-api/app/image_product/prompt_intel.py`](../../../studio-api/app/image_product/prompt_intel.py)

### Queue + runtime

- [`studio-api/app/queue_worker.py`](../../../studio-api/app/queue_worker.py) — `_imagegen`, asset commit, panel writeback
- [`studio-api/app/image_runtime/`](../../../studio-api/app/image_runtime/) — contract, certified registry, production gate, readiness, provider registry
- Config: [`config/image-workflows/`](../../../config/image-workflows/), [`config/image-runtime/`](../../../config/image-runtime/)

### Dock bridge

- [`studio-api/app/production_control/runtime_map.py`](../../../studio-api/app/production_control/runtime_map.py) — `apply_image_dock_preference`

### Findings

1. Creator route is still legacy `workspace=imagegen` (must be replaced by `CinematicImageStudio` at same workspace key).
2. Queue/runtime spine is robust — do not reinvent.
3. `compile.py` already accepts cinematography/lighting/continuity/scene/panel hooks.
4. **Mismatch:** `families()` omits `qwen2512` while recommend + certified registry prefer/include it.

---

## 2. Active storyboard path

```
ScriptStoryboardWorkspace (workspace=script / storyboard label)
  → api.storyboardGenerate / panel CRUD
  → routers/extra.py + script_storyboard.py
  → prepare_storyboard_generate (storyboard_jobs.py)
  → generate_images (image_product) → imagegen job
  → panel.asset_id writeback
  → storyboard_send_director → Scene creation
```

### Frontend

- [`studio-web/src/components/ScriptStoryboardWorkspace.tsx`](../../../studio-web/src/components/ScriptStoryboardWorkspace.tsx)
- Workspace: strip + shot list — **not** 6/9/12 page sheets; no storyboard PDF

### Persistence / jobs

- [`studio-api/app/script_storyboard.py`](../../../studio-api/app/script_storyboard.py) — `script_docs`, `script_segments`, `storyboard_panels`
- [`studio-api/app/storyboard_jobs.py`](../../../studio-api/app/storyboard_jobs.py)
- [`studio-api/app/routers/extra.py`](../../../studio-api/app/routers/extra.py) — generate + send-director

### Findings

1. Storyboard generation is already a specialized caller of Image Product (correct reuse).
2. Panels are segment-centric; Scriptwriter v2 is a separate store.
3. Director handoff creates Scenes directly — no proposal-first Timeline prep in this workspace.
4. No page model (6|9|12) or storyboard PDF export.

---

## 3. Scriptwriter linkage

| Surface | Path |
| --- | --- |
| UI | [`studio-web/src/components/scriptwriter/ScriptwriterStudio.tsx`](../../../studio-web/src/components/scriptwriter/ScriptwriterStudio.tsx) (`workspace=scriptwriter`) |
| API/store | [`studio-api/app/scriptwriter/`](../../../studio-api/app/scriptwriter/) — `script_documents_v2`, transactions, snapshots |
| Migration | [`scriptwriter/migration.py`](../../../studio-api/app/scriptwriter/migration.py) — legacy segments → elements with `legacySegmentId` |
| Timeline prep | `prepare_timeline` / `apply_timeline_prep_metadata` — proposal-shaped (reuse for M4.9) |
| Split confession | Scriptwriter storyboard tab tells users to open dedicated Storyboard workspace |
| Gen-tools risk | [`generation_tools/ops.py`](../../../studio-api/app/generation_tools/ops.py) still writes scripts to legacy `script_storyboard` |

**Dual sync systems:** panel `script_sync_status` vs Scriptwriter `sceneSync` — Wave 1 must unify mapping (Linked / Script Updated / Override / Conflict / Unlinked).

---

## 4. Production Dock / readiness truth

### Frontend

- [`studio-web/src/components/production-dock/`](../../../studio-web/src/components/production-dock/)

### Backend

- [`studio-api/app/production_control/`](../../../studio-api/app/production_control/) — status, gate, preferences, resolve, models, provider switch

### Truth-source split (do not invent a third)

1. Image Product / Image Runtime — certified registry, production gate, fingerprints, provider-registry.json
2. Production Dock — model_registry, hosted discovery, project preferences

M4.8 model UX must **consume** dock + image_runtime truth, not fork readiness labels.

---

## 5. Reusable inventory

### Keep / extend

| Area | Assets |
| --- | --- |
| Image product | `image_product/{api,service,compile,recommend,references,presets,prompt_intel}.py` |
| Runtime | `image_runtime/*`, `config/image-workflows/*`, `config/image-runtime/*` |
| Queue | `queue_worker._imagegen` + asset/provenance commit |
| Storyboard | `script_storyboard.py`, `storyboard_jobs.py`, send-director |
| Scriptwriter | migration, sceneSync, prepare_timeline |
| Continuity UI seed | `studio-web/src/components/continuity/GenerateContinuitySection.tsx` |
| Dock | production_control + production-dock FE |

### Continuity hooks already present

- Image intent: `continuityId`, `panelId`, `sceneId`, `shotId`, `cameraId`
- Compile creative context: `continuity`, `approvedReferences`, cinematography, lighting
- **Missing:** persisted `VisualContinuitySession` contract/store

---

## 6. Gap matrix vs mission

| Requirement | Current | Gap |
| --- | --- | --- |
| Replace `workspace=imagegen` with CinematicImageStudio | `ImageGenPanel` at `imagegen` | New shell; same workspace key; retire primary UX |
| Best Match / Choose Model / All Models | recommend + dock menus + family buttons | Tri-mode UX; unify inventories; fix qwen2512 families omit |
| Cinematic lens/lighting/color | Compile accepts fields; no primary UI | First-class request fields + artist controls; Advanced for jargon |
| Visual Continuity Session | continuity packet / continuityId only | New shared contract + optional persist; UI: Continuity [Inherit from scene] |
| Storyboard pages 6\|9\|12 | Strip + shot list | Document/Page model over panels; default 9 |
| Storyboard PDF / contact sheet | Scriptwriter PDF only | Storyboard export pipeline |
| Script sync statuses | Dual systems | Unified Linked/Updated/Override/Conflict/Unlinked |
| Timeline prep proposal | Scriptwriter has it; storyboard send-director is direct | Proposal-first for storyboard→timeline |
| HiDream + FLUX Schnell/Dev | Partial registry coverage | Install/detect/license slots; honest not_installed |
| Native vs upscaled honesty | Incomplete labels | 1K/2K/4K/8K native vs upscale truth |

---

## 7. DO-NOT-REINVENT

1. Do not replace Image Product compile → queue → runtime → asset pipeline.
2. Do not invent a second workflow registry.
3. Do not bypass Production Dock route resolution.
4. Do not create a second reference-image store.
5. Do not create a second provenance system.
6. Do not replace storyboard generation with a parallel queue path — extend `storyboard_jobs`.
7. Do not discard Scriptwriter `prepare_timeline` shape.
8. Do not fabricate provider-readiness labels in the UI.
9. Do not create a second Director handoff path — evolve send-director toward proposal-first.
10. Do not assume Scriptwriter v2 alone owns storyboard truth yet — layer pages on `storyboard_panels`.

---

## 8. Recommended Wave 1 contract surfaces

| Contract | Python | TypeScript |
| --- | --- | --- |
| Visual Continuity Session | `studio-api/app/image_studio/continuity.py` | `studio-web/src/contracts/visualContinuity.ts` |
| Cinematic image request | `studio-api/app/image_studio/contracts.py` | `studio-web/src/contracts/cinematicImageStudio.ts` |
| Image provider descriptor | `studio-api/app/image_studio/providers.py` | (same FE contracts) |
| Storyboard document/page/panel | `studio-api/app/storyboard_studio/contracts.py` | `studio-web/src/contracts/storyboardStudio.ts` |
| Script sync | `studio-api/app/storyboard_studio/script_sync.py` | `studio-web/src/contracts/scriptSync.ts` |
| Timeline prep | `studio-api/app/storyboard_studio/timeline_prep.py` | `studio-web/src/contracts/timelinePrep.ts` |
| Persistence doc | `docs/release-gate/m48-m49/M48_M49_DATA_AND_PERSISTENCE.md` | — |

Packages (thin orchestration over existing stores):

- `studio-api/app/image_studio/`
- `studio-api/app/storyboard_studio/`

### Mandatory Continuity Session shape

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

Creator UX (Wave 3): **Continuity → [ Inherit from scene ]** — no continuity dashboard in primary Image Generator.

---

## 9. Verdict

### AUDIT_COMPLETE

Reusable image and storyboard spines exist. M4.8/M4.9 should layer contracts, provider unification, cinematic UX, page storyboard, and continuity sessions on top — not fork execution.

### Wave-0 blockers for feature work (resolved by Waves 1–5)

1. ~~Branch identity~~ — created `feature/m4-8-m4-9-cinematic-image-storyboard`
2. Dual script/storyboard stores — unify via sync contract + pages over panels
3. Missing `VisualContinuitySession` — Wave 1
4. `qwen2512` families mismatch — Wave 2
5. No page-set / storyboard PDF / unified sync / timeline proposal — Waves 1+4
6. `workspace=imagegen` still legacy shell — Wave 3 replace-in-place
7. Dock vs image_runtime inventory adjacency — Wave 2 ImageProviderRegistry

**Gate status:** Wave 0 artifact landed — Waves 1+ may proceed.
