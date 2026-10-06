# Fresh Brand Ad Movement Segment Smoke

Project: `Movement Segment Brand Ad Smoke`  
projectId: `47668934-6993-42f8-9bd4-1c8ae3db2bd4`  
mapId: `186c6d74-f610-4872-a36f-633c2a22919a`  
branch: `feat/movement-segments`  
HEAD: `aa6b72bb0970e651bb25bd323c55ff3e40bb1b88`  
UI: `http://127.0.0.1:8760/project/47668934-6993-42f8-9bd4-1c8ae3db2bd4?workspace=spatial`  
API: `http://127.0.0.1:8758/`

This is a new Commercial / Brand Ad project. Schnick Coffee was not reused.

## Preflight

| Item | Observed |
| --- | --- |
| Branch | `feat/movement-segments` |
| HEAD | `aa6b72bb0970e651bb25bd323c55ff3e40bb1b88` (same SHA as `feat/timeline-final-certification`; Movement work is in the dirty tree) |
| Qwen family | `/api/image-product/families` → `qwen2512` **Certified + executable=true** |
| Image-studio catalog | `qwen-image-2512-local` readiness **draft** — Spatial Map ERS dropdown disables Qwen and falls back to GPT Image 2 |
| Live Qwen path used | API `ers.generate` + Mini `generator=qwen2512` with `qwen2512.ref` |

## Inheritance (hard gate) — PASS

Evidence: `evidence/brand_ad_setup.json`

- M2 copied M1 character/prop/camera state before any move
- After M2 move, M1 coords unchanged
- M1 ≠ M2 ≠ M3 blocking
- Delete M1 → 409 `MOVEMENT_CANNOT_DELETE`
- Sixth movement → 409 `MOVEMENT_LIMIT_REACHED`
- Activate missing → 404 `MOVEMENT_SEGMENT_NOT_FOUND` (recovery: will not substitute M1)

| Movement | Beat | Spokesperson |
| --- | --- | --- |
| M1 | Opening Pitch | nX -0.5, nY -0.5, grid 2,2 |
| M2 | Hallway Walk | nX 0.3, nY 0.1, grid 5,6 |
| M3 | Closing Product Beat | nX 0.7, nY 0.7, grid 8,8 |

Arrows API: `evidence/movement_arrows.json` — M1→M2 and M2→M3 at those coordinates.

## Spatial Map UI — PASS (chrome) / NOTE (slots)

Observed live:

- Accordion: M1 Opening Pitch / M2 Hallway Walk (Active) / M3 Closing Product Beat
- Trash only on M2 and M3
- Active indicator M2
- Save = Saved (version 17)
- Grid shows C1 and a dashed purple movement path
- Screenshots: `spatial-map-movements-accordion.png`, `spatial-map-grid-arrows.png`

Setup placed the spokesperson with `slotIndex: -1`, so Character 1–4 chrome stays empty. Movement JSON and arrows still hold the spokesperson. This is smoke-setup binding, not a second Movement store.

## ERS — PASS (assembled product sheet)

Qwen Local I2I `qwen2512.ref` 2560×1440 core, then code-assembled taller sheet **2560×2220**.

- Asset `7d15373f-3db8-4f0a-9f26-a2631da7426e`
- Sheet `e5beb006-e95f-4d20-9d2a-f4022a768363`
- Layout errors: none (`evidence/ers_assembled_strip.json`)
- Camera band: C1 · C2 (compact)
- Movement strip: M1 Opening Pitch / M2 Hallway Walk / M3 Closing Product Beat with distinct spokesperson dots
- No full dialogue/action dump in the strip
- Hero crop remains core panel 0
- Evidence: `ers_official_assembled.png`, `ers_comfy_recovered.png`, `ers_assembled_strip.png`

Honesty: the Qwen core is still a top-down floor plan (atlas I2I bias), not a classic labeled 3×3 view set. The Movement strip and camera band are the Movement-specific assembly and they are correct.

First ERS job `f4813901-...` was interrupted by an API death; Comfy finished the plate; a second Studio ERS persisted the assembled composite.

## Mini packets — PASS

`evidence/mini_packet_isolation.json`

- All six jobs `generator=qwen2512`
- Unique movement IDs
- Distinct blocking in both take.movement and cameraPackets
- Provenance present: `movementSegmentId`, `segmentNumber`, `revision`, `cameraId`, `variation`, `generatedAgainstMovementRevision`

## Qwen six-image visual smoke — FAIL

Required: M1+C1 A/B, M2+C1 A/B, M3+C1 A/B.

| Take | Result |
| --- | --- |
| M1 A | complete — `mini_M1_A.png` |
| M1 B | complete — `mini_M1_B.png` |
| M2 A | failed — API restart interrupted |
| M2 B | failed — Comfy `ConnectError` |
| M3 A | failed — Comfy `ConnectError` |
| M3 B | failed — Comfy `ConnectError` |

M1 A/B are real Qwen images, but they are top-down interior plates (ERS hero-crop I2I), not camera-true hallway shots of a spokesperson at M1. They cannot prove `M1 ≠ M2 ≠ M3` blocking.

Comfy on `:8188` later stopped accepting HTTP (wedged / refused). Retry of M2/M3 was blocked.

## Playwright

`tests/e2e/movement-segments/movement-segment-brand-ad-smoke.spec.ts`

- First run: Chromium missing in this environment
- After `npx playwright install chromium`: **1 passed (7.6s)** against live Beta `:8760` / `:8758`
- Spec covers M1–M3 hold, no silent M1 fallback, delete-M1 409, arrows, accordion, Qwen executable
- Spec does **not** generate the six Qwen images

## Timeline compile — PASS (architecture)

`evidence/compile_layers_m1_m2.txt` — distinct UNCHANGED / START / END / ACTION / DIALOGUE / TIMED PROMPT.  
`evidence/timeline_structured_refs.json` — `~M1` `~M2` `~M3` are structured refs.

Live LTX/MiniMax video was not executed (GPU reserved for Qwen; MiniMax availability not fabricated).

## Co-Director live chat — NOT VERIFIED

`evidence/cd_ask_movements.py` failed while API was down. Not re-run while Qwen occupied the GPU, then Comfy died. Tools exist: `spatial.plan_movements` is `recommendOnly`; `scene_creator_mini.create_take` refuses missing movement (no M1 substitute).

## Request stability — FAIL (incident)

Studio API died at least twice during this smoke (Atlas mid-sample, ERS mid-sample, Mini M2 mid-sample). Schnick Coffee UI continued polling `/jobs` and advancing an LTX execution onto the same Comfy queue. A pending Schnick LTX prompt was removed so it would not run after Brand Ad ERS.

This is not a Movement schema defect. It is a live-cert blocker.

## Fresh-smoke verdict

Cannot pass: six real Qwen images and `M1 ≠ M2 ≠ M3` were not observed.
