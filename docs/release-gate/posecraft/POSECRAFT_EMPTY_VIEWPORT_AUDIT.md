# PoseCraft Empty Viewport — Live Rendering Audit (AUDIT ONLY)

**Status:** GOVERNING DOCUMENT — audit findings for the empty PoseCraft viewport.
**Date:** 2026-09-11 · Branch: `feat/posecraft-v4-human-replacement`
**Mission:** AUDIT ONLY. Determine why PoseCraft loads its UI but the 3D viewport
shows no figure. No repair in this mission.

**Verdict: AUDIT COMPLETE — ROOT CAUSE PROVEN — READY FOR REPAIR JOURNEY**

> Backup: `.runtime/backups/posecraft-20260911-212659/` (87 files). No production
> code modified. Evidence: `.runtime/_posecraft_canvas.png`, `.runtime/_posecraft_full.png`.

---

## LIVE SYMPTOM

Reproduced against the live UI (`:5173`, project `beffd3d8-…`, `?workspace=posecraft`).
The viewport renders the floor, gray grid, RGB axes — and a **faint humanoid
silhouette (Adult Male 1) at the extreme upper-left edge** plus a large dark slab
(a body mesh the camera nearly sits on). "WebGPU active" pill and Pose
Intelligence panel are populated. The figure reads as **effectively empty**
because it is rendered tiny and off-center at maximum zoom.

## FIRST BROKEN TRANSITION

**Camera state hydration → viewport frame.**
`studio-web/src/posecraft/engine.ts` — `PoseCraftViewportController.sync()`
camera-write block (~line 1500) + `create()` camera defaults (~line 750).
- Expected: camera framed on the figure at `(-1.4, 0, 0)`.
- Actual (live): `globalPosition (10.22, 8.18, -14.13)`, `target (4.262, 1.2, -3.627)`,
  `radius 13.948` (== `upperRadiusLimit`). Figure is 19.4–20.1 units away, off-axis.

## ROOT CAUSE — PROVEN

A **stale, corrupt persisted camera** is stored in the project's PoseCraft scene
(API: scene `revision 13`, `camera.target=(4.262,1.2,-3.627)`, `radius=13.948`).
On every load, `sync()` re-applies this persisted camera through its
`lastSyncedCamera` guard. That camera points away from the figure at maximum
zoom, so the figure renders as a near-invisible speck at the frame edge.

**This is NOT a mesh/rig/asset/renderer failure.** Measured:
- All **17 body meshes present**, `isVisible=true`, real vertex counts, `visualState="READY"`, 3546 tris.
- Mesh world bounds form a correct standing figure at `x∈[-1.67,-1.13], y∈[0,1.85], z≈0` (feet at y=0).
- **GLB served HTTP 200** (`model/gltf-binary`), valid structure.
- **Real WebGPUEngine**, live device, render loop `frameId=450`, **no console/page/network errors**.

## CONTRIBUTING DEFECTS

1. **No load-time camera sanitization** — a persisted camera that frames nothing
   is applied verbatim; no "does this camera actually see the figures?" guard.
2. **Persisted `radius` at the upper limit** for a 1.84 m figure — an extreme
   zoom-out became the sticky `lastSyncedCamera`.
3. **Off-target persistence** — `target` drifted away from the only figure; the
   orbit-protection guard treats it as intentional and re-applies it.

## WORKING SYSTEMS (do NOT rebuild)

Babylon WebGPU renderer + WebGL fallback; render loop; resize. v4 GLB pipeline
(`v4FigureLoader.loadContainer` → `attachV4Figure`, region bind, pick colliders,
tint, highlight). 17-joint TransformNode rig + V4 rest binding; archetype specs.
Scene state, persistence/migration (`state.ts`, schema v2). **Pose Intelligence
backend** (`codirector/pose_intelligence/service.py` — canonical joint/pose
state, not the mesh — which is why intelligence is healthy while visualization is
mis-framed). Floor/grid/axes, gizmos, picking, snapshot path.

## REPAIR SURFACE

- `studio-web/src/posecraft/engine.ts` — `PoseCraftViewportController.create()`
  (initial camera) and `sync()` camera-write guard (`lastSyncedCamera`, ~line 1500).
- Contract: persisted `PoseCraftScene.camera` in `types.ts` / `state.ts`
  (`migrateSceneToCurrent`) — add camera plausibility validation.

## RISK

The `lastSyncedCamera` guard protects the creator's live orbit from being stomped
on every scene edit. A naive "always reset camera on load" would regress
legitimate saved framings and snapshot-restore. The fix must distinguish a
*plausible* saved camera from a *corrupt/out-of-frame* one — not blanket-reset.

## RECOMMENDED REPAIR (describe only — NOT implemented)

Add a **load-time camera plausibility clamp** in `sync()` (or in
`migrateSceneToCurrent`): after reading the persisted camera, check whether at
least one figure (or the stage origin) falls within the camera's useful frustum
(target distance within `[lowerRadiusLimit, ~2× figure height]`, target within
stage bounds). If the persisted camera frames nothing / is at an extreme radius,
**replace just the camera fields** with the default framed-on-stage camera
(`target (0,1.2,0)`, `radius 7.5`, `alpha -π/2`, `beta 1.12`) and let that persist.
Keep the `lastSyncedCamera` guard intact for in-session edits.

## ASSET TABLE

| Model | Path | On disk | Loader | HTTP |
| --- | --- | --- | --- | --- |
| adult-male-lowpoly-v4 | `/posecraft/figures/adult-male-lowpoly-v4.glb` | ✅ 289,384 B | Babylon glTF | ✅ 200 |
| adult-female-lowpoly-v4 | `/posecraft/figures/adult-female-lowpoly-v4.glb` | ✅ 289,548 B | same | ✅ 200 |
| child-boy-lowpoly-v4 | `/posecraft/figures/child-boy-lowpoly-v4.glb` | ✅ 289,516 B | same | ✅ shared |
| child-girl-lowpoly-v4 | `/posecraft/figures/child-girl-lowpoly-v4.glb` | ✅ 289,524 B | same | ✅ shared |
| Custom figures | Library asset via `api.assetUrl(...)` | Library | `SceneLoader.ImportMesh` (glTF/OBJ) | shared viewport/camera |

Loader path is shared across all four archetypes → not a one-model asset break.
The Custom-figure route uses a different loader but the **same viewport/camera**,
so the camera-framing defect affects it identically.
