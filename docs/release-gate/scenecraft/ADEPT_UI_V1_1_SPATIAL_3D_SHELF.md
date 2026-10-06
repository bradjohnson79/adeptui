# Adept UI v1.1 Spatial/3D Shelf — SceneCraft v1.2 Cloud

**Status:** GOVERNING CANON (Law 30) · 2026-09-13

LAW — As of 2026-09-13, Spatial Map, PoseCraft, Fire3D and SceneCraft are outside Adept UI v1.1 scope. Preserve them without active production exposure. Development resumes under SceneCraft for Adept UI v1.2 Cloud; their incomplete certification must never block v1.1 GO.

## Release boundary

| Surface | v1.1 | v1.2 Cloud |
| --- | --- | --- |
| Spatial Map | SHELVED — preserved, inactive, not creator-facing | SceneCraft subsystem |
| PoseCraft | SHELVED — preserved, inactive, not creator-facing | SceneCraft figures / poses / blocking / staging |
| Fire3D | SHELVED — not a runtime/setup requirement | Reconstruction backend (cloud GPU primary) |
| SceneCraft | RESERVED — do not build now | Creator-facing spatial/3D production system |

Historical PoseCraft/Fire3D rebuild status: **SHELVED — V1.2 CLOUD**. The earlier `NO-GO — LOCAL_FIRE3D BLOCKED` remains true for that local certification attempt. It is **not** a v1.1 release blocker. Unfinished gates are **DEFERRED — V1.2 CLOUD**, not fake PASS.

Prior PoseCraft GO/NO-GO reports are historical evidence only.

## v1.1 creator authorities

| Need | Authority |
| --- | --- |
| Environment / ERS | Environment Creator |
| Production still | Image Generator |
| Shot sequencing | Storyboard Studio |
| Video production | Timeline |
| Video finishing | MAGI |

Stale URLs (silent, no coming-soon copy):

- Spatial Map / aliases → Environment Creator
- PoseCraft / aliases → Image Generator

## SceneCraft direction (do not build in v1.1)

```
SCENECRAFT
  ├── Spatial Map
  ├── Fire3D Reconstruction
  ├── PoseCraft
  │     ├── figures
  │     ├── poses
  │     ├── blocking
  │     └── character staging
  ├── Objects / Furniture
  ├── Cameras
  ├── Saved Shots
  └── Co-Director Auto Previz
```

v1.2 Fire3D direction: Adept UI → SceneCraft → reconstruction job → Cloud GPU → Fire3D → `Fire3DReconstructionPackage` → SceneCraft canonical scene.

`LOCAL_FIRE3D` and `CLOUD_FIRE3D` stay in code. Do not require or certify LOCAL_FIRE3D for v1.1. The reconstruction package stays provider-neutral.

## Preservation

Do not delete:

- PoseCraftScene schemaVersion 3, server-document SoT, `imageAssetId`, 17-joint map, V4 archetypes/GLBs, pose catalog, objects, cameras, shots, snapshots
- Fire3D contracts, `Fire3DReconstructionPackage`, 32 GB profile, normalize, Co-Director tool implementations, Auto Previz, IG/Storyboard handoff, tests, migrations
- Spatial Map implementation and saved documents
- Backup `.runtime/backups/posecraft-full-20260913-154707`
- [`docs/release-gate/posecraft/FIRE3D_LICENSE_LEDGER.md`](../posecraft/FIRE3D_LICENSE_LEDGER.md) — **NOT ACCEPT** (v1.2 Cloud commercial gate; cloud does not erase licensing)

Do not rewrite PoseCraft back to the pre-rebuild architecture.

## What v1.1 must not do

- Install WSL2 / Ubuntu / local Fire3D / Fire3D CUDA extensions / weights
- Certify PoseCraft viewport, figures, Auto Previz, or Fire3D reconstruction
- Treat Fire3D/PoseCraft as ESSENTIAL / MISSING ESSENTIAL / REQUIRED RUNTIME / PLATFORM BLOCKER
- Expose the four names as active creator destinations
- Demand these systems in Setup Wizard
- Block v1.1 GO on their incomplete certification

## Tests

- v1.1 active: shelf routing, hide/redirect, Environment Creator / Image Generator / Storyboard / Timeline / MAGI
- v1.2 dormant: PoseCraft/Fire3D unit and contract tests remain on disk; do not fail v1.1 because WSL/Fire3D/cloud GPU is absent
