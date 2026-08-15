# SCENE CREATOR 3D CAMERA ORIENTATION — FINAL END-TO-END CERTIFICATION

**Date:** 2026-08-14  
**Branch:** `beta`  
**HEAD SHA:** `9bc9f982c3adb8c20adcc769bc2bf80ab180a92c`  
**Working tree:** uncommitted Scene Creator 3D + Inpaint + left-sidebar tool architecture (not pushed)  
**Deployed SHA:** not applicable — Vercel Production still serves a cinematographer-only bundle until this work is pushed  
**Local web build:** `studio-web/dist/assets/index-a-qLfgTT.js` (built this session; contains `3D Camera Orientation` and `INPAINT MODE`)  
**Studio API:** `http://127.0.0.1:8758/` via `https://api-beta.adeptui.org`  
**Studio API runtime:** owned uvicorn (pid file **42912**, listener **42068**), started **2026-08-15T00:43:17Z** after `Restart-AdeptBetaBackend.ps1 -Service studio_api`. OpenAPI includes `orientation3d` on the cinematographer command body and `POST /api/scene-creator/projects/{project_id}/shots/{shot_id}/region-edit`. ComfyUI `0.32.0` ready, CUDA RTX 5090.

This document is the governing certification for this milestone. It does **not** supersede `SCENE_CREATOR_CINEMATOGRAPHER_SYSTEM_CERTIFICATION.md` for the prior Cinematographer GO.

Independent verifier: [Independent 3D/inpaint verifier](53a50a08-1acc-43a0-a338-c244cfb7dc49).

## Verdict

```text
NO-GO — SCENE CREATOR 3D CAMERA ORIENTATION NOT CERTIFIED END TO END
```

```text
NO-GO — SCENE CREATOR INPAINT / REGION EDIT NOT CERTIFIED END TO END
```

Local API contract, compiler, preview, lock, final payload, persistence, and Spatial Map non-writeback **did** run live. That is not full-stack certification.

### Blockers

1. **Hosted Adept UI does not contain this feature.** Creators on `https://adeptui.vercel.app/` still load `index-Cgmdwg6q.js`. There is no 3D Camera Orientation accordion and no Inpaint panel on hosted. Work was not pushed (not requested).
2. **Live E2E was API-scripted**, not a creator browser session. `OrientationRig` mouse orbit was not exercised against the running product. No Playwright (by spec).
3. **Inpaint → Final inheritance failed visually.** Approved Z-Image Native Inpaint did not become the Qwen final source. Final job `f98dfb43-d72c-4c51-871a-f46601c95b9d` is `qwen2512.txt2img` with Strategy B prose only. `orient3d-c1-final.png` still shows a blurred background extra on the left.

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

## Independent verifier E2E TRACE

| Layer | Result |
|---|---|
| User action | FAIL — API script, not creator click / 3D drag |
| Frontend | FAIL — hosted bundle stale; local dist not browser-certified |
| API | PASS |
| Backend | PASS |
| Persistence | PASS (API reload) |
| Runtime | PASS — Comfy completed preview, native inpaint, Qwen final; no silent family swap |
| Result | FAIL — final extra still present; preview/inpaint are cup ECU |
| Reload | PASS — API GET lock + orientation persist |
| Downstream | FAIL — approved inpaint was not the final source (`sourceAssetId` null on Qwen txt2img) |

Verifier overall: **REJECTED — inpaint correction did not survive into final; hosted/frontend 3D path not proven.**  
3D Camera (local API contract laws): PASS. Inpaint: FAIL.

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

- Hosted UI not updated; no push this session.
- Left-sidebar placement is in local dist `index-a-qLfgTT.js` only.
- 3D viewport not live-browser certified.
- Addendum scenarios A–E not yet manually verified in a creator browser session.
- ECU-on-cup previews do not visually prove three-quarter / Dutch tilt; payload did.
- Qwen 1280×720 was used for production final because Z-Image 1280×720 previously failed `WORKFLOW_GRAPH_DRIFT` against the certified 1024×1024 graph.
- `creativeContext.cinematographer` is overwritten to a slim dict in `_enqueue_shot_candidates`; fused **prompt** still carries orientation (live-proven).
- `lineage.finalAssetId` on C1 may not equal this shot’s final candidate id (verifier note).
- Work uncommitted.

## Manual review

- API: `http://127.0.0.1:8758/` (leave running).
- Hosted UI will **not** show left-sidebar 3D Camera / Inpaint until this branch is pushed and Vercel rebuilds.
- Local dist `index-a-qLfgTT.js` contains left-sidebar accordions, center INPAINT MODE, and right camera cards.
- Do not expect Qwen Final Quality Render to keep a Z-Image inpaint; choose an edit-capable generator or treat Strategy B as prompt-only.
- Do not resurrect `:8760`. Standard Scene Creator is the Project Editor three-zone workspace.

## Evidence paths

`docs/release-gate/scene-creator/evidence/orient3d-*.json` and `orient3d-c1-*.png`.
