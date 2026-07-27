# M2.13 Phase 0 Audit

**Branch:** `phase2/codirector-m2-9-production-suite`  
**Baseline tip:** `8fa5f81` (pre-M2.13)  
**Flag:** `virtual_environment_studio_v1` (default OFF)  
**Provider Manifest sha256 (locked):** `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc`

## Reuse map

| Area | Verdict | Paths |
| --- | --- | --- |
| Asset upload/graph | REUSE + extend kinds | `studio-api/app/db.py`, `asset_graph.py`, `routers/api.py` |
| Location spin | REUSE scaffold; BUILD stitch | `codirector/m28/location_spin/` |
| Camera metadata | REUSE + respect locks | `codirector/m210b/camera.py`, `director_timeline.py` |
| Lighting language | REUSE specialist; BUILD state | `prompts/specialists/lighting-supervisor.md`, `spatial_scene.py` |
| Specialists / DAG | REUSE pattern; BUILD VPC | `intelligence/specialist_registry.py`, `m211/dag.py` |
| M2.12 feedback | REUSE hooks (no auto lessons) | `codirector/m212/` |
| Three.js / GLB | BUILD | `studio-web` (+ `three`) |
| Blender convert | BUILD optional worker | detect-only / CLI if present |
| COLMAP/Nerfstudio | BUILD adapters only if present | no silent download |

## Dependency inventory

- **Required for UI viewport:** `three` (npm)
- **Optional convert:** Blender CLI (`STUDIO_BLENDER_BIN` / `blender` on PATH)
- **Optional reconstruction:** COLMAP / Nerfstudio / gsplat binaries if detected
- **CI:** fixture adapters only — never claim real generation from mocks

## Non-goals (confirmed)

- Not a Blender/Maya replacement (no sculpt/rig/UV)
- No silent COLMAP/Nerfstudio install
- No Provider Manifest mutation
- No silent approval advance
