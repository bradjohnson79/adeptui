# Environment Creator Express Dual Save — Certification

**Date:** 2026-09-16  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf76693e359cedc60c50c4405daf1b4e3a1` (implementation uncommitted)  
**Surface:** Co-Director → Environment Creator Express (`contentTab=scene_creator`)  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Entity:** Anadriya's Quarters `84ef72cb-663d-4d8d-89b7-61874fc8db01`

This is the governing report for the dual Save Environment action.

## What shipped

One canonical `saveEnvironment()` on the shared `EnvironmentCreatorSurface` (Express + Standard). Top and bottom **Save Environment** buttons are two entry points into that command.

Save upserts the Environment Creator entity (`POST /api/environment-reference-sheets/projects/{project_id}/save`):

- NEW → `create_sheet` + persist plan + Global
- EXISTING (bound id or same project name) → update the same `sheetId`
- Does not generate, regenerate, or detach `ers_composite_asset_id`

Character Creator Express and Prop Creator Express already have a single Save. They were audited only; not redesigned.

## Tests

- `studio-api` `tests/test_environment_creator_save.py`: **4 passed**
- `studio-web` `environmentCreatorContracts.test.ts`: **11 passed**

## Owner live tests A–G

| Test | Result |
| --- | --- |
| A Top Save visible | PASS |
| B Bottom Save visible | PASS |
| C Description change + bottom Save + reload | PASS (`[DUAL-SAVE-C]` on sheet `84ef72cb…`) |
| D Aspect 21:9 + top Save + reload | PASS |
| E Global ON top Save / reload / visible on Global Scope Project B; Global OFF bottom Save / other project no longer lists it | PASS |
| F Repeated save same ID, one name | PASS |
| G Generated ERS composite remains `e4c10cdb-fc70-453f-84d1-d639dbcec09c` | PASS |

URL stayed on Co-Director Environment Creator. Generate was not invoked.

## Runtime

- Local creator UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/` (recycled 27048 → 24104)
- **COMFY BEFORE:** PID 34484 healthy  
- **COMFY AFTER:** PID 34484 healthy  
- **COMFY RESTARTED?:** NO  

## Verdict

**GO — ENVIRONMENT CREATOR EXPRESS DUAL SAVE CERTIFIED**
