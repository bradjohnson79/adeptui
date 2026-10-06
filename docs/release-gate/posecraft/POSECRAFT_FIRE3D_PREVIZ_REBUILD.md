# PoseCraft / Fire3D 3D Previsualization Rebuild

**Status:** HISTORICAL / SHELVED — V1.2 CLOUD · 2026-09-13  

This document is **no longer governing**. Current authority:

`docs/release-gate/scenecraft/ADEPT_UI_V1_1_SPATIAL_3D_SHELF.md`

Do not resume WSL2 / local Fire3D / PoseCraft certification for Adept UI v1.1. Incomplete gates stay **DEFERRED — V1.2 CLOUD**. The attempted local verdict `NO-GO — LOCAL_FIRE3D BLOCKED` remains historically correct and is not a v1.1 blocker.

**Product name:** PoseCraft  
**Internal subsystem:** PoseCraft / Fire3D System  
**Backup:** `.runtime/backups/posecraft-full-20260913-154707` (1,337 files, readback VERIFIED)

Prior PoseCraft audits and GO reports are **historical inputs**. Do not cite them as current truth.

## Backup

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| Commit | `99665cf76693e359cedc60c50c4405daf1b4e3a1` |
| Path | `.runtime/backups/posecraft-full-20260913-154707` |
| File count | 1337 |
| Readback | VERIFIED (types, engine, workspace, schemas, service, router, handler, V4 GLB, handoff, migration, e2e) |
| Live projects with PoseCraft JSON | Schnick Coffee, WC-APP-1787326164799, Korri Anadriya (metadata only) |

## Inventory (pre-rebuild)

### KEEP

- Project-scoped `projects.posecraft_document_json`
- Frozen snapshot PNG key `imageAssetId`
- 17-joint map and V4 archetype set (adult-male/female, child-boy/girl)
- V4 GLBs under `studio-web/public/posecraft/figures/`
- Pose catalog joint data (50+ poses)
- Co-Director `creatorModified` approval gate
- Storyboard `addImage` backend path
- Pose Intelligence concept (not Inspector flicker coupling)
- `cameraPlausibility` signals (not the 2.7–15 clamp)

### REBUILD

- `PoseCraftWorkspace.tsx` session authority / mount race
- `engine.ts` camera defaults + sync/fov unguarded writes
- Image Generator sessionStorage handoff as SoT
- Custom GLB `/file` loader
- Camera face-zoom (minZ, radius, target)
- Object system (imported + reconstructed)
- Co-Director persist that rebuilt a document without snapshots
- Hydrate-failure empty PUT

### MIGRATE

- `BlockingPrimitive` → `PoseCraftObject` (`source: procedural`)
- Schema 2 → 3 (`environment`, `objects`, `cameras`, `shots`)
- Pose catalog presentation categories (standing/sitting/walking/…)
- Snapshots remain previz captures; add first-class `shots`

### SHARED

- Project Library asset API
- ERS visual identity / CRS character identity
- Co-Director tool execution + approval
- Image Generator authority-ref consume
- Storyboard Studio addImage

### DELETE / DEAD

- localStorage scene SoT (`storage.ts` production path)
- sessionStorage as IG/Storyboard authority
- Spatial Map origin surprise-import
- Scene Creator as a PoseCraft dependency
- `__posecraftController` as authority
- Duplicate camera constant authorities
- Silent `_empty_document()` overwrite of a stored scene

## Hard laws

- One scene SoT: server document. Renderer reflects it.
- One camera authority.
- Fire3D is reconstruction only. ERS is visual identity only.
- Objects are not figures.
- Reconstructed people are not characters by default.
- Co-Director mutates only canonical PoseCraft actions.
- `--skip-render` for PoseCraft mesh path.
- Do not install Fire3D into the Windows/Comfy CUDA environment.
- Do not restart Comfy `:8188`.

## Frozen contracts (Wave 1)

### PoseCraftScene schemaVersion 3

Server document is the only SoT. Fields:

- `environment` — reconstructed/imported room mesh + optional `#EnvironmentName` ERS link
- `figures` — rigged PoseCraft figures only
- `objects` — furniture, props, reconstructed meshes (`source: procedural | imported | reconstructed`)
- `cameras` / live `camera`
- `shots` — named framing + optional frozen transforms
- `snapshots[].imageAssetId` — frozen PNG key (never `snapshotAssetId`)
- `igHandoffSnapshotId` — Image Generator backend handoff
- `loadState`: `ok` | `empty` | `corrupt`
- `creatorModified`

### Fire3DReconstructionPackage

Normalized from official outputs (`oriented_bboxes.json`, `obj_dict` / `annotation_*.json`, meshes, composed GLB). Detected humans never auto-promote to figures.

### Runtime

- Providers: `LOCAL_FIRE3D` | `CLOUD_FIRE3D`
- Adept 32 GB profile: `studio-api/app/posecraft/reconstruction/profile_32gb.json`
- Official layout adapter: `data/<scene_id>/rgb.jpeg` + `aligned_pcd.ply` (Pi3). No invented point maps.
- GPU admission waits; never kills Comfy `:8188`

### Co-Director tools

Keep existing reads/mutations. Added: `add_object`, `move_object`, `place_figure`, `sit_on_object`, `look_at`, `focus_figure`, `save_shot`, `capture_previz`, `propose_previz_plan`, `execute_previz_plan`.

Auto Previz execute requires a stored plan + `approved: true`.

## License

See `FIRE3D_LICENSE_LEDGER.md`. Production licensing is **NOT ACCEPT** until live `--skip-render` infer is proven.

## Local Fire3D host (this machine, 2026-09-13)

`wsl.exe` reports **Windows Subsystem for Linux is not installed**. Enabling WSL2 requires elevation and a reboot. Fire3D was not installed into the Windows/Comfy CUDA environment.

## Certification (2026-09-13)

**Tests:** `studio-api` `tests/test_posecraft_previz_rebuild.py` + `tests/test_posecraft_contracts.py` → **33 passed**. Vitest `contactActions` / `cameraPlausibility` / `sceneState` → **22 passed**.

**Live UI:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=posecraft` (Korri Anadriya). Build/Reconstruct, stage tree, sit/look/focus, Reconstruct panel, and Auto Previz draft-plan are wired. Draft plan returned four honest default shots. Approve was not executed on the live project.

**Independent review:** GLM 5.2 Max unavailable (usage limit). Primary review: server document is SoT; camera limits unified at 0.35–24 / minZ 0.05; IG handoff is backend-first; Spatial Map hydrate removed; Fire3D types stop at the import adapter; humans are not auto-promoted; corrupt hydrate cannot PUT empty (409); Auto Previz execute requires a stored approved plan. Residual: workspace god-file still hosts the old chrome; sessionStorage remains a leftover IG fallback; Reconstruct still asks for a Library picture id rather than a creator picker; object gizmos are transform-sync only.

| Gate | Verdict |
| --- | --- |
| BACKUP VERIFIED | VERIFIED |
| OLD POSECRAFT INVENTORY | VERIFIED |
| POSECRAFT FULL REBUILD | NOT VERIFIED (contracts + surfaces landed; god-file not fully replaced) |
| FIRE3D NATIVE ENGINE ADAPTER | NOT VERIFIED (layout/normalize/runtime exist; no live infer) |
| LOCAL/CLOUD RUNTIME ABSTRACTION | VERIFIED (honest unavailable) |
| FIRE3D IMAGE RECONSTRUCTION | E2E BLOCKED — WSL2 not installed |
| FIRE3D VIDEO RECONSTRUCTION | NOT VERIFIED |
| FIRE3D → POSECRAFT IMPORT | VERIFIED (unit / fixture) |
| ENVIRONMENT LAYER | NOT VERIFIED (live mesh) |
| OBJECT SYSTEM | VERIFIED (schema + sync + import) |
| OBJECT TRANSFORMS | VERIFIED (full XYZ in sync) |
| BUILT-IN FIGURES | NOT VERIFIED (browser viewport showed empty stage while cast listed figures) |
| CUSTOM GLB FIGURES | VERIFIED (`pluginExtension`) |
| RIG INSPECTION | VERIFIED (unit: unrigged ≠ poseable) |
| RIG RETARGETING | NOT VERIFIED |
| POSE LIBRARY | VERIFIED (creator groups) |
| SITTING / WALKING / LYING | VERIFIED (unit + presentation) |
| MANUAL JOINT POSING | VERIFIED (existing path kept) |
| CONTACT-AWARE POSING | VERIFIED (sit/look ops; honest initial placement) |
| CAMERA AUTHORITY | VERIFIED |
| FACE-LEVEL ZOOM | VERIFIED (limits + focus action) |
| SAVED SHOTS | VERIFIED (API) |
| PREVIZ CAPTURE | NOT VERIFIED (live PNG) |
| CO-DIRECTOR STAGE CONTROL | VERIFIED (sit writes canonical scene) |
| AUTO PREVIZ | VERIFIED (draft live; execute gated) |
| POSECRAFT → IMAGE GENERATOR | VERIFIED (backend SoT; live consume not run) |
| POSECRAFT → STORYBOARD | VERIFIED (existing addImage kept) |
| 3D OBJECT LIBRARY | VERIFIED (classify + delete-guard) |
| SAVE / RELOAD | VERIFIED (API) |
| LICENSING GATE | NOT VERIFIED — see FIRE3D_LICENSE_LEDGER.md |
| GREEN PLATFORM REGRESSION | NOT VERIFIED (scoped PoseCraft tests only) |

### E2E TRACE

| Step | Result |
| --- | --- |
| User action | PASS (PoseCraft opened on Korri Anadriya; Reconstruct + Draft plan clicked) |
| Frontend | PASS (mode bar, reconstruct panel, Auto Previz plan list) |
| API | PASS (healthz 200 after recycle; Auto Previz plan 200) |
| Backend | PASS (schema 3, scene_ops, auto_previz store) |
| Persistence | PASS (project document; hydrate-failure 409) |
| Runtime | FAIL — LOCAL_FIRE3D unavailable (WSL2 missing) |
| Result | FAIL — no Mess Hall reconstruction |
| Reload | N/A (no reconstructed stage) |
| Downstream | N/A (no previz PNG → IG / Storyboard this run) |

`COMFY BEFORE: PID 45624 / healthy`  
`COMFY AFTER: PID 45624 / healthy`  
`COMFY RESTARTED?: NO`  
`WHY?: Ordinary PoseCraft API/UI work. Supervisor recycle of Studio API only.`

**Final:** `NO-GO — LOCAL_FIRE3D BLOCKED: WSL2 is not installed; live Fire3D --skip-render infer and Mess Hall reconstruction were not run. Licensing remains NOT ACCEPT until that infer is proven.`
