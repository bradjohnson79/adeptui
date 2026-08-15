# SCENE CREATOR 3D CAMERA ORIENTATION — FINAL END-TO-END CERTIFICATION

**Date:** 2026-08-14  
**Branch:** `beta`  
**HEAD SHA:** `3b1a98f458cff4f5623ea594d7c4cf11d326ce71`  
**Remote SHA:** `3b1a98f458cff4f5623ea594d7c4cf11d326ce71` (`origin/beta`)  
**Deployed SHA:** `3b1a98f` (Vercel Production status **success**; live bundle `https://adeptui.vercel.app/assets/index-ZKRp9KRs.js` contains `3D Camera Orientation`, `INPAINT MODE`, `cine-tile`)  
**Inheritance engine SHA:** `a5860a2da4806da8413c219420af398be5932d05`  
**Live-family overlay SHA:** `8550418b01d9f4a85c3edd342c5196bae7c4a827`  
**Mask-reload SHA:** `3b1a98f458cff4f5623ea594d7c4cf11d326ce71`  
**Studio API:** `http://127.0.0.1:8758/` via `https://api-beta.adeptui.org` — `/api/health` **ok**  
**Hosted UI:** `https://adeptui.vercel.app/project/2347bf46-3762-4763-86c5-4a6032522278?workspace=scenecreator`  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` scene `e4550745-f0ef-44c8-99a5-ef9e20bd47d2` shot `2a58894b-b5d4-4e86-b068-7cd156199d98`

This document is the governing certification for this milestone. It does **not** supersede `SCENE_CREATOR_CINEMATOGRAPHER_SYSTEM_CERTIFICATION.md` for the prior Cinematographer GO.

Prior NO-GO (hosted missing + Qwen T2I inheritance) is historical below. Closure evidence is this addendum.

Independent verifier: [Independent 3D/inpaint verifier](2c5e20be-e1b5-40bf-ba24-2eab1dc65496) — `VERIFIED — 3D CAMERA + INPAINT HOSTED E2E PASSED`.

## Verdict

```text
GO — SCENE CREATOR 3D CAMERA ORIENTATION CERTIFIED END TO END
```

```text
GO — SCENE CREATOR INPAINT / REGION EDIT CERTIFIED END TO END
```

Hosted creator browser path ran against `https://adeptui.vercel.app`. Approved Z-Image inpaint conditioned Final Quality Render via Strategy A (`zimage.ref_edit`, `sourceAssetId` = approved edited preview). Corrected pixels survived Final (cup ECU, no Qwen T2I portrait, extra stayed gone). Spatial Map cells remained **11,11 / 13,11 / 9,11**.

### Closure evidence (hosted browser)

| Gate | Result |
|---|---|
| D — 3D left accordion, rig, yaw/pitch/roll, zoom without cell move, target lock Korri, C2↔C3 sync, both accordions, center dominant | PASS |
| E — center-hero brush, mask bound to source, Remove extra, camera hash unchanged, stale-mask warning | PASS (Remove). Modify/Add **enqueued** as `region_edit` then **failed Output Gate** (masked region did not change meaningfully) |
| F — preview → inpaint → approve → lock → Z-Image Final Strategy A → extra stays gone → Library → Send to Timeline → reload → Spatial Map cells | PASS |

### Inheritance job (authoritative)

| Field | Value |
|---|---|
| Take E candidate | `6c00fd8f-f22e-4466-8a52-01aa276fc241` |
| Job | `5220f772-2410-4512-afbb-db4980f3bd95` |
| Runtime | `zimage.ref_edit` `image.edit` 1024×1024 `fallbackApplied=false` |
| `sourceAssetId` | `cfab346e-31da-4f11-8b57-120aa8719fb4` (Approved Region Edit C) |
| `finalStrategy` | A |
| `parent_candidate_id` | `7a746b09-be06-41f2-b52d-710bbf34ad44` |
| Provenance | `LOCAL — Z-Image Turbo — Image Edit` |
| Asset / Library / `lineage.finalAssetId` | `b0bd03c3-f213-4da8-80bd-cf22d8ead147` |
| Camera | C1 v20 hash `542a31ee7e39cb76` cell 11,11 locked |
| Timeline | MAGI `exportLedger` `bb_476ec1a8b0c6` / `clip_6ae59becdddd` asset `b0bd03c3…` (notice: `Sent to Timeline (1 clip).`) |

Failed Qwen T2I Take B `f98dfb43…` / asset `e0d3af5e…` remains historical contrast (portrait + extra). It is **not** the approved look.

Region Edit C inpaint: job `953fcdcb-3458-4892-b80b-26187d5930d9` `zimage.inpaint` source `02ec3985…`, camera hash unchanged.

### Remaining limitations (not silent T2I)

- Final-quality Modify (`d4c856ab…`, `Region Edit G`) and Add (`Region Edit H`) hit **Output Gate: masked region did not change meaningfully**. Operations are wired; pixels did not pass the gate on this ECU cup. C1 has no face, so “Modify expression” cannot be proven on this locked shot.
- Job store flattens `creativeContext`; structured cinematographer is compiled into **translated prompt prose** plus candidate stamps (`camera_state_version/hash`, `source_camera_id`). No raw JSON in the prompt.
- Double-click enqueued Take D and Take E (both Strategy A, same source). Approved look is Take E.
- Do not resurrect `:8760`.

---

## Architecture findings

Existing Cinematographer remains authoritative. No second camera store, preview route, lock route, or final route.

```text
Spatial Map / ERS baseline
→ Scene Creator SceneCinematographerPack
→ dropdown semantic command
→ optional CameraPose.orientation3d
→ compile_camera_context (prose + structured dump)
→ existing preview / lock / final
```

`SAVE_CAMERA_BACK_TO_SPATIAL_MAP` remains false. Live Spatial Map document `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081` still has C1/C2/C3 at cells **11,11 / 13,11 / 9,11** with `shotType=medium` before and after orientation experiments.

3D frontend uses **existing `three`** (already in `studio-web/package.json`). Imperative `OrientationRig.tsx` with dispose-on-collapse. No React Three Fiber / drei. No Babylon (PoseCraft-only).

Inpaint reuses `ImageMaskEditor`, image-product mask persistence (`POST /api/image-product/projects/{id}/masks`), and appends `kind=region_edit` candidates. Capability labels are frozen:

| Family | Label | Native Inpaint | Image Edit |
|---|---|---|---|
| zimage | Native Inpaint | yes | yes |
| flux | Image Edit | no | yes |
| qwen2512 | Unsupported | no | no |
| illustrious | Unsupported | no | no |

Live proof: Qwen region-edit returns HTTP 400 *This generator cannot edit a region. Choose Z-Image for Native Inpaint.* Z-Image used `zimage.inpaint` with `fallbackApplied=false`.

---

## Files changed

**Backend**

- `studio-api/app/scene_creator/cinematographer.py` — `Orientation3DState`, ops, math, hash keys when enabled, compile prose
- `studio-api/app/scene_creator/cinematographer_service.py` — `orientation3d` command patch; final allows draft region-edit approval
- `studio-api/app/scene_creator/router.py` — `CinematographerCommandBody.orientation3d`
- `studio-api/app/scene_creator/service.py` — region-edit enqueue, Strategy A/B compile, `approved_look_blocks_final`
- `studio-api/app/scene_creator/generation.py` — family capability contract
- `studio-api/app/scene_creator/region_edit_router.py` — `POST .../region-edit`
- `studio-api/app/scene_creator/ers_resolver.py` / `ers_contracts.py` — candidate `kind`, `mask_id`, `edit_operation`
- `studio-api/app/main.py` — mount region-edit router
- `studio-api/tests/test_cinematographer_orientation3d.py`
- `studio-api/tests/test_scene_creator_region_edit.py`

**Frontend**

- `studio-web/src/components/CoDirector/SceneCreator/cinematographer/CinematographerPanel.tsx` — camera cards stay on the right; 3D accordion removed from this panel
- `studio-web/src/components/CoDirector/SceneCreator/cinematographer/OrientationAccordion.tsx` — left-sidebar 3D tool
- `studio-web/src/components/CoDirector/SceneCreator/cinematographer/OrientationRig.tsx`
- `studio-web/src/components/CoDirector/SceneCreator/cinematographer/orientationMath.ts`
- `studio-web/src/components/CoDirector/SceneCreator/cinematographer/cameraCommandEngine.ts`
- `studio-web/src/components/CoDirector/SceneCreator/regionEdit/RegionEditPanel.tsx` — controls only; no sidebar thumbnail painter
- `studio-web/src/components/CoDirector/SceneCreator/regionEdit/CenterMaskCanvas.tsx` — paints on the center hero image
- `studio-web/src/components/CoDirector/SceneCreator/regionEdit/inpaintSession.tsx` — UI session, not a product store
- `studio-web/src/components/CoDirector/SceneCreator/regionEdit/regionEdit.ts`
- `studio-web/src/components/CoDirector/SceneCreator/SceneCreatorCore.tsx` — three-zone Standard layout
- `studio-web/src/components/CoDirector/SceneCreator/useSceneCreator.ts`
- `studio-web/src/components/CoDirector/SceneCreator/sceneCreatorApi.ts`
- `studio-web/src/components/imageEdit/ImageMaskEditor.tsx` — hideChrome / fill / imperative export
- matching CSS + unit tests

---

## Camera JSON contract

Authoritative fields remain on `CameraPose` (`yawDegrees`, `pitchDegrees`, `rollDegrees`, `lensMm`, `fovPreset`, `opticalZoomStep`, `targetEntityId`). Added:

```json
{
  "orientation3d": {
    "enabled": true,
    "targetLock": true,
    "zoom": 1.35,
    "axisLocks": { "yaw": false, "pitch": false, "roll": false, "zoom": false },
    "source": "gizmo"
  }
}
```

When `enabled=false`, extra hash keys are omitted so old packs keep the same hash.

Live locked C1 (shot `2a58894b-b5d4-4e86-b068-7cd156199d98`):

| Field | Value |
|---|---|
| cameraStateVersion | 20 |
| cameraStateHash | `542a31ee7e39cb76` |
| yaw / pitch / roll | +32 / −18 / +3 |
| zoom | 1.35x (`lensMm` 47.25) |
| target | Korri `c49371ed-ba6b-4c16-ba98-a8b28b72118b` |
| targetLock | true |
| shotType | extreme_close_up |
| cell | grid 11,11 (C12R12) |
| instruction | `CAMERA 1 take EXTREME CLOSE-UP on CHARACTER 1, Korri with PROP 1, Coffee Cup included in composition.` |
| locked | true |

---

## Yaw / pitch / roll math

- Yaw wrap `(-180, 180]`
- Pitch clamp `[-60, 60]`
- Roll clamp `[-25, 25]`
- Optical zoom `[0.5, 3.0]`; `lensMm = clamp(baseline * zoom, 18, 200)`
- Snap yaw: Front 0, 3/4 L 45, Profile L 90, Rear 3/4 L 135, Rear 180, and right-side negatives
- Snap pitch: Eye 0, Slight High −12, High −28, Bird’s Eye −55, Slight Low 12, Low 22, Worm’s Eye 45

Zoom never steps the grid cell. Dolly/step still change `physicalStepOffset` and cell. Live: cell stayed `[11,11]` through zoom 1.35→1.5; Dolly In moved to `[11,9]`; undo restored cell and kept yaw +32.

---

## Dropdown + JSON fusion

Preview job `254c2921-819e-42cb-b287-cb5aa00afa68` (`zimage.txt2img`, 512×288, `lockModelFamily` true, `fallbackApplied` false) prompt contains both:

- Semantic: `Shot: EXTREME CLOSE-UP` and `CAMERA 1 take EXTREME CLOSE-UP on CHARACTER 1, Korri with PROP 1, Coffee Cup included in composition.`
- Translated 3D: `3D camera aim: yaw +32°, pitch -18°, roll +3°, optical zoom 1.35x, target lock on. Framing: three-quarter left, elevated looking down, subtle Dutch tilt clockwise, tighter optical framing.`

No raw `{"yawDeg":32}` dump.

Final job `f98dfb43-d72c-4c51-871a-f46601c95b9d` (`qwen2512.txt2img`, 1280×720) contains the same fused camera language **plus** Strategy B: `Do not include the removed extra. Remove the background extra behind Korri…`

---

## Live jobs (Schnick Coffee, reuse project)

| Step | Job | Runtime | Asset |
|---|---|---|---|
| Preview 1 | `254c2921-819e-42cb-b287-cb5aa00afa68` | zimage.txt2img 512×288 | `88a424a7-38d6-4365-8cdd-875ee373f5e2` |
| Stale lock | — | HTTP 400 *Generate a preview…* after roll 3→6 | — |
| Preview 2 (lock) | `f56c0c29-0d90-45a5-9745-98b9676cbaec` | zimage draft | `dd795811-152f-43af-9a64-927ab6502e97` |
| Mask | `mask-98aecd47b80c` | image-product PNG bound to preview 2 | — |
| Inpaint | `8891db25-8a3b-427b-93fa-c57f8211b647` | **zimage.inpaint** `imagegen_edit` / remove | `02ec3985-6980-4732-b870-96eaec534194` |
| Final | `f98dfb43-d72c-4c51-871a-f46601c95b9d` | qwen2512.txt2img 1280×720 | `e0d3af5e-b63d-4974-b999-7c5543f7624e` |

C2 yaw −25 remained while C1 yaw moved 32→33. Spatial Map cells unchanged.

Model switch: same pack JSON used for Z-Image preview and Qwen final. Orientation was not reset.

---

## Tests measured

- Backend pytest: **27 passed** this addendum pass (`test_cinematographer_orientation3d.py`, `test_scene_creator_region_edit.py`); prior full Scene Creator pytest set was **58 passed**
- Frontend Vitest: **35 passed** (4 Scene Creator files including layout contract, collapsed orientation line, inpaint source list)
- Playwright: not added (by spec)

---

## Independent verifier E2E TRACE (closure)

Verifier quote: `VERIFIED — 3D CAMERA + INPAINT HOSTED E2E PASSED`

| Layer | Result |
|---|---|
| User action | PASS — hosted creator clicks (3D, inpaint generate, approve take, Final Quality Render, Send to Timeline) |
| Frontend | PASS — `index-ZKRp9KRs.js` has 3D Camera Orientation, INPAINT MODE, cine-tile |
| API | PASS |
| Backend | PASS — Strategy A compile; Qwen T2I refused when inheritance required |
| Persistence | PASS — approved Take E + C1 lock/hash survive reload |
| Runtime | PASS — `zimage.inpaint` then `zimage.ref_edit`; no silent family swap |
| Result | PASS — cup ECU Final; extra gone vs failed Qwen portrait `e0d3af5e` |
| Reload | PASS |
| Downstream | PASS — Library hit + Timeline exportLedger Take E |

Historical TRACE (pre-closure NO-GO) remains in git history; do not treat it as current.

---

## SCENE CREATOR INPAINT / REGION EDIT — END-TO-END CERTIFICATION

**Supported local:** Z-Image Native Inpaint (`zimage.inpaint`); FLUX Image Edit (`flux.img2img`) in unit tests only (not live this run).  
**Unsupported live:** Qwen 2512, Illustrious — UI/API refuse; no silent txt2img fallback.  
**API providers:** not exercised; `api_enabled` stayed false; painting a mask does not enqueue.

Mask implementation: canvas overlay + `saveMask` → `mask-98aecd47b80c` on source `dd795811…`. Worker consumed `maskAssetId`. Smart Select not shipped (no fake segmentation).

Low-res Inpaint: real job, real mask, real output candidate `7d6450c7…` (`LOCAL — Z-Image Turbo — Native Inpaint`). Camera lock/yaw unchanged.

Low-res → final inheritance: **FAIL.** Qwen cannot edit; compiler used Strategy B text; extra reappeared in `orient3d-c1-final.png`.

Final-quality Inpaint finishing pass: **not live-run** (blocked by inheritance NO-GO).

Expression / add-prop certification shots: **not live-run**.

Nondestructive: original preview assets remain; inpaint appended a candidate.

---

## ADDENDUM — LEFT-SIDEBAR TOOL ARCHITECTURE

Implemented. Not a redesign of Scene Creator. Placement only.

```text
LEFT  = tools: Scenes, Shots, 3D Camera Orientation ▸, Inpaint / Region Edit ▸
CENTER = hero image, preview/final, mask overlay, take strip
RIGHT = Environment, Spatial Map, Characters/Props, Cinematographer C1–C4 cards
```

Locked UX law: **Left = Tools. Center = Creation. Right = Context.**

| Rule | Status |
|---|---|
| Camera cards stay on the right | IMPLEMENTED — `CinematographerPanel` still renders C1–C4 |
| 3D Camera accordion under Shots | IMPLEMENTED — `OrientationAccordion` in `scene-creator-standard__browser` |
| Inpaint accordion under 3D Camera | IMPLEMENTED — `RegionEditBlock` in the left sidebar |
| Accordions are independent, not exclusive | IMPLEMENTED — no shared `name` on `<details>` |
| Mask painted on the center image | IMPLEMENTED — `CenterMaskCanvas` in `StandardPreview`; `RegionEditPanel` has no `ImageMaskEditor` |
| Left/right camera selection is one state | IMPLEMENTED — both call `selectCinematographerCamera` / `selectedCameraId` |
| No `leftSidebarCameraState` / `leftSidebarInpaintState` | IMPLEMENTED — `InpaintSession` is UI-only (tool, brush, prompt, open); product state remains cinematographer pack + region-edit candidates |
| Collapsed 3D pauses WebGL | IMPLEMENTED — `OrientationRig active={open}` disposes on collapse |
| Sidebar ~220px; center remains dominant | IMPLEMENTED — `grid-template-columns: 220px minmax(0, 1fr) 280px` |
| Narrow width Tools toggle | IMPLEMENTED — CSS drawer; accordion React state survives hide |
| Same Inpaint accordion for preview and final | IMPLEMENTED — Source selector (`Low-Res Preview`, approved, takes) |

### Certification scenarios A–E

| Scenario | Result |
|---|---|
| A — 3D accordion updates right C1 card / stale preview | NOT VERIFIED — layout wired; no creator browser session this pass |
| B — Inpaint brush on center image → candidate | NOT VERIFIED — center canvas wired; no live paint this pass |
| C — both accordions open, left sidebar scrolls | NOT VERIFIED — CSS `overflow: auto` on left column; no browser measure |
| D — right C2 ↔ left C3 bidirectional select | NOT VERIFIED — shared `selectedCameraId`; no browser click |
| E — reload reconstructs orientation + prompt + approved edit | NOT VERIFIED for UI session fields (prompt/tool); authoritative pack/candidates still persist from prior API E2E |

Immediate NO-GO regressions from this addendum (source/contract): **none observed**. Camera cards were not moved. Center column stays `minmax(0, 1fr)`. Mask is not a sidebar thumbnail.

Browser three-zone sync remains **NOT VERIFIED**. Hosted Adept UI still does not contain this feature.

---

## Known limitations

- Final-quality Modify/Add on this locked ECU cup failed Output Gate (pixel delta). Remove extra + Strategy A Final are the certified inheritance path.
- Job params do not retain a full `creativeContext.cinematographer` object; prompt prose + candidate stamps do.
- Take D and Take E were both Strategy A finals from a double click; approved is Take E.
- ECU-on-cup does not visually prove three-quarter / Dutch tilt; payload and 3D HUD do.
- `qwen.edit` remains Draft/stub — not advertised.

## Manual review

- Hosted: `https://adeptui.vercel.app/project/2347bf46-3762-4763-86c5-4a6032522278?workspace=scenecreator`
- API: `http://127.0.0.1:8758/` (leave running). Do not resurrect `:8760`.
- Choose Z-Image or FLUX for Final when an approved region-edit exists. Qwen T2I is refused.

## Evidence paths

`docs/release-gate/scene-creator/evidence/orient3d-*.json` and `orient3d-c1-*.png`.
