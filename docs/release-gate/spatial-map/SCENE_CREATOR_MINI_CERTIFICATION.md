# Scene Creator Mini (SUPERSEDED)

> **SUPERSEDED 2026-08-18** by
> `docs/release-gate/spatial-map/SCENE_CREATOR_MINI_PRODUCTION_FIDELITY_CERTIFICATION.md`
> (production fidelity + Qwen closure milestone). This Option 1 record is retained
> for history only; do not cite it as current truth (Build Law #30).

**Status (historical):** NO-GO — SCENE CREATOR MINI CAMERA FIDELITY NOT CERTIFIED

**Date:** 2026-08-18  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`  
**Map:** `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081` version 138  
**Blocker:** GPT Image 2 **C2-only A/B gate FAIL** after Option 1 (relational viewpoint prompt + inset ERS hero plate). Independent review: **A PASS 7/7**, **B FAIL** (lounge/entrance plant) on both the first C2 take and the C2 regenerate. Plan required both stills PASS — **STOP**, no 8-image burn, no Qwen C2 smoke for GO.

Law 27 requested GPT 5.4; specialized review ran as inherit.

Thin accordion under ERS in Spatial Map Express and Standard (`SpatialMapPanel`). Two stills per saved active camera (max 4 → 8). Qwen or GPT Image 2. Frame size is global per take.

## Rules

- Saved Spatial Map only (`savedVersion === version`).
- Draft results use `commitToLibrary: false` / `libraryVisible: false` until Send Selected to Library.
- Regeneration replaces temporary pairs; never deletes Library assets.
- Cameras are Spatial Map coordinates; Mini does not relocate them.
- Pixel plate is the ERS **hero panel inset** (`scene_creator_mini_hero_inset`) — top-left 1/3 with titles/legends cropped out. Same plate for every camera at Option 1. Not the full 3×3 sheet, not the top-down atlas.
- Mini prompt uses Spatial Map cells (`N12`) plus Mini-only `compile_camera_viewpoint_facts`. That compiler is **not** appended to ERS.

## Endpoints

- `GET /api/spatial-map/projects/{pid}/maps/{mid}/mini-take/preview`
- `POST .../mini-take`
- `GET .../mini-take/{takeId}`
- `POST .../mini-take/{takeId}/regenerate`
- `POST .../mini-take/{takeId}/send-to-library`

## Live evidence

| Item | Result |
|------|--------|
| GPT Image 2 full take | `9e07e5cd-e6e6-4d35-8039-face3a8d2ab2` — 4 cameras / 8 jobs at 16:9, all complete |
| Qwen smoke | `f796a0ea-c8fc-4fc8-b0d2-f4cc7df161e3` — C1 only, 2 images, 1280×720, GPU 100% / ~31 GB VRAM |
| Library before gen | 161 visible |
| Library after gen | 161 (no Mini leak) |
| Send Selected C3-A/B | 163 (`4dc91806-ae8e-4b0b-b1a8-6a25656a86cd`, `78ec56d4-8619-435d-900c-398590a00e6e`) |
| After Qwen drafts | still **163** visible; Qwen asset ids not in Library listing |
| C4 drafts | not in Library |
| Duplicate send | no-op (`lastLibrarySendCount=0`) |
| Frame sizes | unit/API: 1:1, 16:9, 21:9 (and 4:5, 9:16) via `mini_pixels` |

## Independent visual

| Review | Result |
|--------|--------|
| GPT full take (`.runtime/camera_mini_cert/INDEPENDENT_MINI_PAIR_CERT.md`) | C3 PASS, C4 PASS, C1 incomplete then repaired, **C2 FAIL** |
| Prior C2 regenerate (`.runtime/camera_mini_cert/INDEPENDENT_MINI_C2_REGEN_CERT.md`) | **C2 FAIL** (A table close-up; B south-looking-north) |
| Qwen C1 smoke (`.runtime/camera_mini_cert/INDEPENDENT_QWEN_MINI_CERT.md`) | **C1 pair PASS** (near-duplicate I2I of hero; ERS title chrome burned in) |
| Option 1 GPT C2 gate take `b31a4af4-…` (`.runtime/camera_mini_cert/INDEPENDENT_GPT_C2_GATE_CERT.md`) | **A PASS 7/7**, **B FAIL** Q1/Q4/Q5/Q6 → pair FAIL |
| Option 1 C2 regen (`.runtime/camera_mini_cert/INDEPENDENT_GPT_C2_REGEN_CERT.md`) | **A PASS 7/7**, **B FAIL** Q1/Q4/Q5/Q6 → pair FAIL |

## Tests

- `studio-api/tests/test_scene_creator_mini.py`
- `studio-api/tests/test_qwen_i2i_ers.py::test_qwen2512_ref_frame_size_is_runtime_not_topology`
- `studio-web/.../sceneCreatorMiniApi.test.ts`
- Playwright accordion + top/bottom Save in `savegate-cert.spec.ts`

Qwen `qwen2512.ref` fingerprints treat width/height as runtime params (`40ca923a…`) so Mini 16:9 does not trip `WORKFLOW_GRAPH_DRIFT`. Topology changes still fail the gate.

## E2E TRACE

| Stage | Result |
|-------|--------|
| User action | PASS — Generate Mini Take / Regenerate Pair / Send Selected |
| Frontend | PASS — accordion under ERS, shared save hook |
| API | PASS — mini-take routes |
| Backend | PASS — `scene_creator_mini` controller |
| Persistence | PASS — take JSON + hidden Asset rows |
| Runtime | PASS — GPT Kie I2I full 8; Qwen `qwen2512.ref` local GPU smoke |
| Result | **FAIL** — C2-A can read east/NW; C2-B repeatedly plants lounge/entrance (windows-left). Pair rule fails |
| Reload | PASS — drafts persist; Library send survives |
| Downstream | PASS — selected-only Library; Scene Creator handoff still dirty-gated |

## Option 1 closure (this pass)

Shipped in working tree (not committed — commit only after Mini GO):

- Mini-only `compile_camera_viewpoint_facts` (N12, east/NW, anti-hero, Spatial Map bearing so named occupants can read ahead)
- Inset hero I2I plate `hero-inset-*.png` / tag `scene_creator_mini_hero_inset`
- Header **Enable Mini** switch (`spatial-map__slot-toggle`); Playwright accordion test passed on live Beta
- Live C2 prompt checks: `N12` present, `C14R12` absent, Korri ahead after bearing fix

GPT C2-only take `b31a4af4-3300-4e71-84a2-27d47da46993` (take 8) then regenerate of C2. Independent cert: A geography PASS both times; B FAIL both times (lounge chair / entrance plate). Per the camera-conditioning plan, a second I2I signal (floor-plan guide / dual plate) is **not** in this pass.

## Verdict

`NO-GO — SCENE CREATOR MINI CAMERA FIDELITY NOT CERTIFIED`

Exact blocker: GPT Image 2 C2-B does not hold the east guest-floor plant. Overlay/compile remain certified under the ERS camera document. Mini C2 is not camera-true as a pair.
