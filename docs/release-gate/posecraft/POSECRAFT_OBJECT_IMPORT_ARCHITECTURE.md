# PoseCraft 3D Object / Furniture Import — Future Architecture

**Status:** AUDIT DELIVERABLE F · read-only · no implementation · 2026-09-12
**Owner direction:** creators must be able to import general 3D scene objects (tables,
chairs, desks, couches, beds, decor, machinery, props) — distinct from humanoid custom
figures. This lets a creator stage characters around a real imported table/chairs,
snapshot that previz, and hand it to Scene Creator alongside ERS/CRS references.

---

## 1. WHAT EXISTS TODAY

| Capability | Location | Class |
| --- | --- | --- |
| Procedural furniture contract | `types.ts` `BlockingPrimitive`, `PrimitiveKind`, `FurnitureKind` (tables/blocks/chairs/walls) | **EXISTS** |
| Procedural furniture builders | `engine.ts` `createPrimitiveRig` (~501–628) | **EXISTS** |
| Add/update/remove furniture | `state.ts` `createFurniture`, `addFurnitureToScene`, `addPrimitiveToScene`, `updatePrimitive`, `removePrimitiveFromScene` | **EXISTS** |
| Imported arbitrary 3D object | — | **MISSING** (`PoseCraftObject` is a proposal only) |
| Imported object Library integration | `classify.py` parks 3D in `miscellaneous` as `DEFERRED_VERSION_1_2` | **DISCONNECTED / DEFERRED** |
| Humanoid custom figure import | `engine.ts` ~404–455 via `SceneLoader.ImportMesh`; `v4FigureLoader.ts` | **BROKEN (renders nothing) — see §2a** (existence ≠ working) |

So PoseCraft has a **procedural** furniture foundation and a **humanoid** import path whose
**mesh never renders** — and **no general imported-object path**.

## 2. WHY NOT REUSE THE CUSTOM FIGURE PATH AS-IS

The custom figure path treats the asset as a **humanoid**: it binds a 17-joint rig,
looks for head/hand/foot regions, applies arm rest transforms, and registers pose
metadata. Applying that to a table is wrong. What **is** reusable is the **lower layer**:
`SceneLoader.ImportMesh("", "", assetUrl, scene, …)` + project-Library asset URL
(`api.assetUrl`). Reuse the loader; do **not** reuse the figure semantics.

**⚠ Blocker: the reusable lower layer is itself currently broken (see §2a).** Do not build
imported objects on top of it until the loader defect is repaired, or objects inherit the
same failure.

## 2a. CUSTOM FIGURE IMPORT IS BROKEN END-TO-END (reproduced)

**Symptom:** a custom mesh uploads and persists correctly yet **never renders**.

**Trace:** UI (`PoseCraftWorkspace.tsx` ~1438–1444, `accept=".obj,.gltf,.glb,.fbx"`) →
upload `POST /api/projects/{id}/assets` (`api.py` ~1522–1561; `kind="mesh-3d"`) →
asset stored as `{asset_id}{ext}` → row persisted (`kind`, no `assetType`) →
`assetUrl(assetId)` = `/api/projects/{pid}/assets/{assetId}/file` →
`SceneLoader.ImportMesh("", "", assetUrl, scene, …)` (`engine.ts` ~418–437).

**Root cause (independently reproduced):** the asset URL ends in **`/file` with no dot**, so
Babylon's `getFilenameExtension` (`sceneLoader.js` ~79–84) returns the whole path as the
"extension" → **no loader plugin resolves**. Babylon then falls back to a **HEAD** request to
sniff `Content-Type` (`sceneLoader.js` ~199) — but the asset route is **GET-only**, and
**FastAPI's `APIRoute` does not add HEAD for GET** (unlike plain Starlette `Route`), so the
probe returns **405** and the import rejects. Repro against the repo venv
(FastAPI 0.116.1 / Starlette 0.47.3): `HEAD /get → 405 (Allow: GET)`, `GET /get → 200`.
Corroborated by the shipped audit artifact `IMPORT-debug.json` ("Unable to find a plugin to
load …/file files"; `Error code: 405`).

**Secondary:** even fixing HEAD would not rescue **OBJ** — the OBJ loader registers only
`extensions: ".obj"` with **no `mimeType`**, and `getPluginForMimeType` matches on
`plugin.mimeType`. A dot-less `FileResponse` also resolves to `text/plain`. The robust fix
is to pass an explicit `pluginExtension` derived from the **stored filename**, not to rely
on URL extension or MIME sniffing.

**Evidence that this is a rendering-only failure:** the same run's `IMPORT-custom.json` /
`IMPORT-transform.json` show `"kind":"custom"`, `"customAssetId":"04cea7ee…"` persisting
across reload, while `IMPORT-debug.json` records `importStatus: Imported … as a Custom
Figure.` and `hasFigure: true`. **Persistence ≠ rendering.**

**Compounding gaps:**
- `visualState` is set to `"READY"` **synchronously** before the import resolves
  (`engine.ts` ~452), so no LOADING/ERROR state is ever emitted; the failure is console-only.
- Custom rigs fabricate humanoid metadata (`jointCount:17`, `bodyRegions`) on a cube — the
  `kind !== "custom"` fences hold, but the metadata is misleading.
- `api.assetUrl()` returns `""` when no project is bound (`api.ts` ~7770–7771), and
  `engine.ts` calls it with the id only — another silent-failure path.

## 3. SUPPORTED IMPORT FORMATS (code-level, actual)

| Format | UI gate | Loader registered | Real support | Basis |
| --- | --- | --- | --- | --- |
| `.glb` (self-contained) | yes | yes (`engine.ts` ~22) | **Blocked today by the 405 defect**; correct once fixed | glTF metadata `isBinary:true` |
| `.gltf` (embedded/self-contained) | yes | yes | Blocked by 405; external `.bin`/textures unsupported (single-file asset) | glTF loader metadata |
| `.obj` (self-contained) | yes | yes (`engine.ts` ~21) | **Not loadable via this URL shape** — no extension and no declared MIME (see §2a) | `objFileLoader.metadata.js` (`extensions:".obj"`, no `mimeType`) |
| `.fbx` | **yes** | **NO** (FBX package present in `node_modules` but never imported) | **NO — accepted-but-broken** | grep `@babylonjs/loaders` → only OBJ + glTF registered |

**Import-failure surfacing is MISSING on the custom path:** the loader's `onError` only
`console.error`s; no `kind:"visual"` ERROR event is emitted (contrast the v4 path), so a
failed/deleted asset yields an **invisible figure with no creator-facing error**.

## 4. DELETE-GUARD GAP (must close with any asset-backed object)

The CDX-063 delete-guard `_entity_refs_for_asset()` (`scene_references/service.py`
~578–790) scans 10+ downstream stores but has **no PoseCraft scan** and no
`posecraft` match anywhere in `scene_references/`. Consequence today: a custom-figure mesh
asset can be deleted freely; the scene keeps a dangling `customAssetId`; on reload the
asset URL 404s → silent loader failure → invisible figure, no delete-block, no detach.
**Add a PoseCraft block** reading `posecraft_document_json` figures' `customAssetId` and
(future) objects' `assetId`, plus a detach handler on force-delete.

## 5. PROPOSED CONTRACT — `PoseCraftObject`

```ts
export type PoseCraftObjectSource = "imported" | "procedural";

export type PoseCraftObject = {
  id: string;            // permanent identity
  name: string;          // creator-facing label
  source: PoseCraftObjectSource;
  assetId?: string;      // project Library asset (imported only)
  format?: "glb" | "obj";       // reliable formats only
  primitiveKind?: FurnitureKind; // procedural only
  position: { x: number; z: number };  // floor-plan; Y is ground-derived
  rotationY: number;     // yaw only (matches figures + primitives today)
  scale: number;         // uniform
  visible?: boolean;
  locked?: boolean;
};
```

### Relationship to existing contracts

- **Keep `BlockingPrimitive`** as the `source: "procedural"` case (do not break existing
  scenes). A future migration can map each `BlockingPrimitive` → `PoseCraftObject
  { source: "procedural", primitiveKind: kind }`.
- **Do not merge** `FigureInstance` and `PoseCraftObject`. Figures have rig/pose/identity
  semantics; objects have transform/contact semantics. Keep them separate arrays
  (`figures`, `objects`/`primitives`) so picking, gizmos, and Co-Director semantic
  labels stay clean.
- **`visible`/`locked` are currently NOT enforced** anywhere (fields persist but no
  engine/UI/keyboard check; `visible` only gates floating labels). Enforcement is new work
  for **both** furniture and objects.
- **No SQL migration needed.** `PoseCraftScene` persists as a single JSON blob
  (`projects.posecraft_document_json`); the server Pydantic schema tolerates new fields via
  defaults. Add `objects: []` + `selectedObjectId` to both client and server schemas, bump
  `schemaVersion` 2→3 with an `objects: []` default branch in `migrateSceneToCurrent`.
- **Semantic layer is ready:** `PoseCraftSemanticObject` (`id, label, type, transform,
  visible, locked`) already exists and `buildSemanticPackage` emits primitives through it —
  real objects flow in almost unchanged.

## 6. LIBRARY INTEGRATION (recommended path)

The taxonomy **already has** `three_d.props` / `three_d.environments` (and
`props.three_d` / `scenes.three_d`), all labeled **"Coming in Version 1.2"**;
`classify.py` (~59–74) actively defers all 3D uploads to `DEFERRED_VERSION_1_2` and parks
them in `miscellaneous`. Note the current custom-figure upload already sends
`kind:"mesh-3d"`.

1. **Activate** `three_d.props` (or a dedicated `three_d.posecraft_objects`): remove the
   deferral branch for mesh kinds and add a real classify rule for `kind:"mesh-3d"`.
2. Upload flow is **already correct**: `POST /api/projects/{id}/assets` (project-scoped,
   content-hash dedup, Library enrichment). A future "add to stage" picker reads the
   Library list filtered by the new systemKey.
3. **Delete-guard:** add the PoseCraft scan block (see §4).
4. **Library UI:** add a 3D type-nav entry / surface the `three_d` folder
   (`LibraryPanel` TypeNav currently has no 3D filter; mesh assets only appear under
   All/misc).
5. **Migration impact:** none for existing assets — classification is repairable via
   `assign_asset`; no SQL migration (Library meta is JSON on assets).

## 6. TRANSFORM REQUIREMENTS — REUSE ANALYSIS

| Transform | Figures today | Primitives today | Object-readiness |
| --- | --- | --- | --- |
| Move | gizmo XYZ (Y clamped ≥0) + numeric X/Z | numeric X/Z only (no viewport pick/gizmo) | engine drag machinery reusable; needs a **bbox-based anchor** instead of the figure pelvis-Y anchor |
| Rotate | gizmo XYZ, but **X/Z emit spine-pose events** (figure-coupled); Y is true yaw | `rotationY` field, **no UI** | Y-yaw path generic; **exclude** the X/Z→pose path for objects |
| Scale | uniform numeric (0.5–1.8 clamp) | `scale` field, no UI | generic |
| Duplicate / Remove | `duplicateFigure` / `removeFigure` | keyboard Delete + Remove | portable; must respect `locked` (new) |
| Lock | **field exists, never enforced** | same | enforcement is new work |
| Ground snap | Y clamped ≥0; **custom meshes are NOT origin-normalized** (an off-origin GLB floats/sinks) | auto-floor via `size.y/2` — the correct pattern | imported objects need **bbox-min → 0** normalization at import |

**Guardrail:** do not overload `handleManipulation` figure branches; add a parallel
`object` manipulation kind so figure and object semantics never mix. A `PrimitiveRig`-style
rig (root + material + sync loop) is the proven pattern for a non-figure entity.

## 7. RECOMMENDED CLEAN ARCHITECTURE (later journey — NOT built)

**Prerequisite (otherwise objects inherit the failure):** fix the shared loader defect
(§2a) — pass an explicit `pluginExtension` derived from the stored filename, and make the
asset file route answer HEAD (or bypass HEAD). Then:

- `types.ts`: add `PoseCraftObject` (+ `objects` on `PoseCraftScene` + `selectedObjectId`),
  keep `BlockingPrimitive` for procedural. **No SQL migration** — the scene is a JSON blob;
  bump `POSECRAFT_SCHEMA_VERSION` (currently `2`) with an `objects: []` default in
  `migrateSceneToCurrent`.
- `state.ts`: `addImportedObjectToScene`, `updateObject`, `removeObject`, `duplicateObject`
  (mirror the primitive ops).
- `engine.ts`: `createObjectRig()` that imports via the **fixed** `SceneLoader.ImportMesh`
  (GLB/OBJ) at the Library asset URL, **normalizes bbox-min to y=0**, registers pick
  metadata `{ kind: "object", objectId }`, stores in a new `objectRigs` Map driven by
  `sync()`, and emits **visual ERROR events on import failure** (unlike the silent
  custom-figure path).
- Extend `getLabelScreenPositions()` and semantic export to include objects (use the
  primitive label-anchor pattern, **not** the figure `+1.85 m` head anchor).
- Snapshot freeze already clones `primitives`; add `objects`.

## 8. VERDICT

**3D OBJECT / FURNITURE IMPORT FEASIBILITY: PARTIAL FOUNDATION — FEASIBLE, but gated on the
custom-import loader repair.**
Procedural furniture **EXISTS** (contract, state ops, real geometry, UI, persistence,
semantic export). Arbitrary imported objects are **MISSING** — `PoseCraftObject` is a
proposal only. The generic pipeline half (upload, `assetUrl`, `ImportMesh`, root node,
ground-clamped move, Y-rotate, uniform scale, event bus, semantic objects, JSON-blob
persistence) is reusable, and the humanoid half is already fenced behind `kind !== "custom"`
guards that must stay fenced. **However, the reusable loader layer is currently broken
(§2a): custom figure import never renders.** The work is: (1) repair the loader
(extension/HEAD), (2) a parallel `objects` array + imported-object rig, (3) real Library
`three_d` classification (currently deferred to v1.2), (4) a PoseCraft block in the asset
delete-guard — **without** overloading the humanoid figure contract.
