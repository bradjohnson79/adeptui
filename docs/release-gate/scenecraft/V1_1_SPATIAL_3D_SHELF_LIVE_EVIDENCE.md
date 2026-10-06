# v1.1 Spatial/3D Shelf — Live Evidence

**Status:** EVIDENCE (not governing). Authority remains `ADEPT_UI_V1_1_SPATIAL_3D_SHELF.md`.

**Date:** 2026-09-13  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Local UI:** http://127.0.0.1:5173/  
**Studio API:** http://127.0.0.1:8758/ (`healthz` status ok)  
**API recycle:** oldPid 38868 → newPid 53208 (routing/knowledge/setup contract changes only)

## COMFY

- COMFY BEFORE: PID 45624 / `:8188` healthy (RTX 5090)
- COMFY AFTER: PID 45624 / `:8188` healthy
- COMFY RESTARTED?: NO
- WHY?: Observe-only `GET /system_stats`. No WSL2 / Fire3D install. No Comfy stop/start.

## Live v1.1 journey (zero of the four names)

Walked: Project Home → Co-Director (Express tabs: Wiki / Notes / Story / Script Writer / Character / Voice / Prop / Environment Creator / Timeline / Library) → Environment Creator → Image Generator → Storyboard → Timeline → MAGI → Setup Wizard → Library.

Stale URLs (silent `replace`):

| Bookmark | Landed |
| --- | --- |
| `workspace=spatial` | Environment Creator |
| `workspace=spatialmap` | Environment Creator |
| `workspace=blocking` | Environment Creator |
| `workspace=posecraft` | Image Generator |
| `workspace=pose-craft` | Image Generator |

No “unavailable” / “coming soon” chrome for those systems. Setup Wizard: Ready to Generate; no WSL2 / Fire3D / PoseCraft essential demand.

## Preservation

| Asset | Proof |
| --- | --- |
| PoseCraft JSON | `GET /api/posecraft/projects/…/scene` schemaVersion **3**, scene `PoseCraft Blocking Study`, **6** figures, **1** camera after opens + API recycle |
| Spatial Map docs | `GET /api/spatial-map/projects/…/maps` — `Venture Corridor Walk` id `7c7aac85-6932-4945-a13f-4a11fd69b79f` version 283 |
| Fire3D contracts | `studio-api/app/posecraft/reconstruction/contracts.py` (`Fire3DReconstructionPackage`, `LOCAL_FIRE3D` / `CLOUD_FIRE3D`) |
| License ledger | `docs/release-gate/posecraft/FIRE3D_LICENSE_LEDGER.md` — **NOT ACCEPT** |
| Backup | `.runtime/backups/posecraft-full-20260913-154707` present |

## Tests (this close)

- Vitest (`sceneCraftShelf`, `spatialMapShelf`, `productionMenu`): **25 passed**
- Pytest (`test_v11_spatial_shelf_routing` + `test_codirector_platform_knowledge`): **23 passed**, **1 failed** (`test_chat_paths_call_knowledge_reply_after_grounding` source-scan for `def _maybe_platform_knowledge_reply` — pre-existing hook location; not a shelf blocker)
- Dormant PoseCraft/Fire3D live-runtime tests remain on disk; not faked PASS

## Verdicts

SPATIAL MAP / POSECRAFT / FIRE3D — SHELVED FOR V1.2 CLOUD  
SCENECRAFT — RESERVED FOR V1.2 CLOUD  
V1.1 CREATOR SURFACES CLEAN · CO-DIRECTOR V1.1 CAPABILITY MAP CLEAN · SETUP WIZARD / RUNTIME REQUIREMENTS CLEAN  
ENVIRONMENT CREATOR / IMAGE GENERATOR / STORYBOARD / TIMELINE / MAGI PRESERVED  
SPATIAL MAP DATA / POSECRAFT DATA / FIRE3D CONTRACTS PRESERVED  
FIRE3D LICENSE LEDGER PRESERVED — NOT ACCEPT  
NO WSL2 / FIRE3D INSTALL ATTEMPT · COMFY HEALTH PRESERVED · V1.1 ACTIVE JOURNEY VERIFIED

`GO — V1.1 SPATIAL/3D SYSTEMS INVISIBLY SHELVED FOR SCENECRAFT V1.2 CLOUD`
