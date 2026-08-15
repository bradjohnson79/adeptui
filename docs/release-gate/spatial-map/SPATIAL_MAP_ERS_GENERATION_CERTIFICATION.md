# Spatial Map ERS Generation + Scene Creator Handoff Certification

**Date:** 2026-08-15  
**Branch:** `beta`  
**HEAD at cert write:** `513fa8c`  
**Commit SHA:** _fill after commit_  
**Deployed SHA:** _fill after Vercel Ready_  
**Hosted:** https://adeptui.vercel.app

## Verdict

**GO — SPATIAL MAP ERS GENERATION + SCENE CREATOR HANDOFF CERTIFIED END TO END**

Independent Maintenance Verifier: **VERIFIED — SPATIAL MAP ERS → SCENE CREATOR E2E PASSED**

This chain only. Not Image Core complete. Not Qwen I2I. Not Avatar / Timeline.

## Root cause

`capture_intelligence._bearing_degrees` subtracted attached-prop world coords that were `None` (Clear Glass Cup held by Korri, `x/y/z=null`). That produced:

`HANDLER_ERROR: unsupported operand type(s) for -: 'NoneType' and 'float'`

before any Image Core job existed.

Repair: `_finite_world_xz` returns `None` for missing coords; skip world bearing; `_attached_holder_note` records held-by. No `or 0` coerce. Not a camera bug.

## Old path vs repaired path

| | Old | Repaired |
|---|---|---|
| Geometry | Crash on attached `x=None` | Skip world bearing; holder note |
| ERS jobs | Four directional `zimage` jobs | One Image Core T2I |
| Purpose | Implicit / hardcoded | `purpose=environment_reference_sheet` |
| Persist | Directionals, often empty | Library composite on the sheet |
| Scene Creator | Discover only | Preview request carries `ers_composite` |

## Live local trace

- Map `6bc36d92` v91, placements intact (Korri + attached cup + C1/C2/C3), `backgroundAssetId=caa72759`
- ERS execution `1c3c8493-ff27-406b-8b22-01ba2a72712c` capability `ers.generate` completed
- Child job `b964d61d` asset `2f2e871b`
- `resolvedWorkflowKey=qwen2512.txt2img` `operationIntent=text_to_image`
- Sheet `db095959` `has_reference=true` `ers_composite_asset_id=2f2e871b`
- Scene Creator workspace `selected_sheet_id=db095959` `resolved_ers.ers_composite=2f2e871b`
- Preview job `aa8eaaf3` candidate `4a11e5fe` asset `2606ac9d`
- `final_strategy=C` `final_workflow_key=qwen2512.txt2img`
- `creativeContext.ers_composite=2f2e871b` `reference_image_ids[0]=2f2e871b`
- Never `zimage.ref_edit` / `flux.img2img` / Strategy A

## Image Core

- Used: yes (`resolve` + local Comfy `qwen2512.txt2img`)
- Local model: `qwen2512`
- API-provider ERS: not tested this run
- Qwen I2I: refused (honest T2I). Qwen Edit remains frozen.

## Playwright

`tests/e2e/spatial-map-ers-scene-handoff.spec.ts` observe-only consume assert PASS on `aa8eaaf3`. Live Generate held.

## Leftovers — NOT GO

- `imagegen_edit` filename
- `ImageGen (edit) complete` label
- flux checkpoint label
- Spatial Map leftover-ERS hydrate without Generate
- isolated `test_duplicate_region_edit_reuses_in_flight`
- Qwen Edit frozen
- no API-provider ERS this run
- `params.refs` / `imageIntent.referenceIds` empty (ERS id is `creativeContext` only — request-shape C, not I2I pixel cert)
- Attached live label is Clear Glass Cup `78c5be96`, not Coffee Cup `a8d48a46`

## Deploy rule

Commit ERS / shared-core refuse / Scene Creator honest-T2I handoff / FE error sanitize / Playwright spec / this cert only. Exclude Timeline W46, Avatar, `.runtime`, logs, screenshots, secrets, unrelated Scene Creator WIP.
