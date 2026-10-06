# Local Atlas Designer — Certification Report

**SUPERSEDED for Local production quality.** This FLUX `txt2img` pass is historical. Owner review rejected the corridor Atlas as unrecognizable. The rejected FLUX plate remains a permanent negative fixture.

Current governing document: `docs/release-gate/spatial-map/LOCAL_SPATIAL_FLUX_CONTROL_ATLAS_CERTIFICATION.md` (also deferred). The Qwen compiler pass is historical: `LOCAL_SPATIAL_LAYOUT_COMPILER_QWEN_CERTIFICATION.md`.

API / GPT Image 2 Spatial Map creation remains the certified production path unless the new governing document certifies Local.

---

Governing document for Express Local Atlas **design** (historical FLUX pass). Historical reconstruction reports remain historical.

**Historical verdict (superseded for Local quality):** `GO — LOCAL SPATIAL MAP ATLAS DESIGNER + EXISTING GPT IMAGE 2 API PATH LIVE E2E CERTIFIED`

Review URLs left running: creator UI `http://127.0.0.1:5173/`, Studio API `http://127.0.0.1:8758/`, Comfy `http://127.0.0.1:8188/`.

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` @ `b6156455e643d5fa430784b3130756f2d8038651` |
| Named project | Adept Stability Cert `2bc632b8-b329-4d3b-bc40-b68dc41b6bb1` |
| Production map (do not write) | Supplementary View Assist Cert `e6f64c3b-2533-4549-a476-bf0dcb90d298` / Atlas `9f7d4571-9444-41fa-b4c2-29c27919736a` |
| Cert map | Local Atlas Designer Cert `a6176a4c-c25c-48c2-9077-ee8932ec4ced` |
| Winner | `flux.txt2img` |

## Product distinction

| Surface | Method | Finished Atlas |
| --- | --- | --- |
| Co-Director Express Local | Local Atlas Designer (`flux.txt2img`) | Designed roofless top-down image |
| Co-Director Express API | GPT Image 2 (`gpt-image-2-kie`) | Unchanged designed Atlas |
| Home / Production Standard Reconstruct | MoGe-2 / VGGT | Reconstructed (kept). Not the Express Local default |

MoGe / VGGT were not deleted or rewritten. They are not the creator-facing Express Local Atlas.

## Isolation

All generates targeted the empty cert map. Production `backgroundAssetId` remained `9f7d4571-…` after every Local, retry, replace, GPT, save, and API recycle. Evidence: `docs/release-gate/spatial-map/evidence/local_atlas_designer/live/isolation.json`.

## Candidate bake-off

Installed and healthy: FLUX Dev / Schnell / Kontext, Qwen Image 2512, Illustrious, SDXL, SD 1.5 + ControlNet, Z-Image.

| Candidate | Prompt-only Atlas | Ref Appearance | Top-down | Layout | Source Identity | Runtime | VRAM | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FLUX `flux.txt2img` (square) | CAD / schematic | n/a | mixed | weak | not metallic | 50.7s cold / 21s warm | RTX 5090, ~2.2–3.3 GB free after | Reject square CAD default |
| FLUX `flux.txt2img` (9:16 + anti-CAD) | painted overhead corridor | prompt-baked | **yes** | long corridor + yellow + far-end feature | silver metallic | 6s warm (576×1024) | RTX 5090 | **Winner** |
| FLUX `flux.img2img` + design guide | schematic leftover | n/a | yes | footprint held | not painted | 41s / 19s | RTX 5090 | Reject — guide over-preserved |
| Qwen `qwen2512.txt2img` | eye-level corridor | n/a | **no** | doors + yellow present | metallic | 31.7s (20 steps) | RTX 5090 | Reject — camera inheritance |
| Retired `qwen2512.atlas` / `atlas_direct` | not retested | — | — | — | — | — | — | Permanently out of this path |
| Illustrious / SDXL | not needed after FLUX winner | — | — | — | — | — | — | Not promoted |

Evidence: `docs/release-gate/spatial-map/evidence/local_atlas_designer/bakeoff.json`.

## Winning Local workflow

- **Workflow:** `flux.txt2img`
- **Family:** `flux` (Kontext Dev: `flux1-kontext-dev.safetensors`)
- **Mode:** prompt-only T2I. Appearance reference is compiled into the prompt. Eye-level photos are **not** I2I camera sources.
- **Aspect:** `9:16` when the design packet is a corridor / hallway; otherwise `1:1`.
- **Steps / CFG:** `20` / `1.0` (`imagegen_flux_steps` / `imagegen_flux_cfg`).
- **Prefix:** unique `studio/{project8}_atlas_{job8}` so harvest cannot pick a stale Shared filename.
- **Residency:** existing Comfy / acceleration registry.

## Live Express Local (cert map)

Corridor text is unchanged.

| Run | Execution | Job | Comfy prompt | Asset | Gate | Route |
| --- | --- | --- | --- | --- | --- | --- |
| Description-only | `6c924520-…` | `c7a687c9-…` | `993985d1-…` | `5df282b9-…` | PASS (`pixelKind=atlas`, VLM q1/q2/q3 YES, source=vlm) | Local `designed`, `engineNote=local_atlas_design`, `flux.txt2img` 576×1024 cfg 1.0 / 20 |
| Reference corridor | `b05d2766-…` | `d14065e2-…` | `4827b833-…` | `934e930d-…` | First API validate FAIL_TOP_DOWN (VLM judged SOURCE photo). After candidate-first VLM order: **PASS**. Applied. | Local `designed_with_reference`, appearance prompt, no I2I |
| Second env (lab) | `cf15e2b4-…` | — | — | `b5b71b08-…` | PASS | Local designed; not corridor-overfit (medical room) |
| Classify-assign | n/a | n/a | n/a | `5df282b9-…` | `kind=atlas`, `action=assign`, confidence 0.82 | No FLUX |
| Replace / Generate New | `f823de9f-…` | — | — | `e4008df4-…` | PASS | Local designed |
| Retry after FAIL_TOP_DOWN | `ca6df527-…` | — | `a215d55a-…` | — | stayed Local | `generationMethod=local`, `engineNote=local_atlas_design`, `flux.txt2img`, zero GPT |

One-click trace (description-only): click/API → ExecutionPlan `6c924520` → GenerationJob `c7a687c9` → Comfy `993985d1` → asset `5df282b9` → gate PASS → cert map `a6176a4c`. Zero GPT Image 2 / Kie. Zero `enqueue_spatial_reconstruct_job`. Workspace opened only after PASS.

Images: `live/description_only.png`, `live/reference_corridor.png`, `live/second_env_lab.png`, `live/replace_generate.png`, `live/source_corridor.png`, `live/api_gpt_image2.png`.

### Quality bar (functional Atlas class)

Description-only and reference plates are roofless top-down, long metallic corridor, far-end elevator box, mid yellow/orange guidance, readable floor/walls, 1 m grid usable. Not eye-level, splat, or photo overlay. Local is not pixel-identical to GPT.

### Gate fields (do not invent score names)

Reported from `evaluate_atlas_candidate_sync` / validate API: `ok`, `failCode` (`PASS` / `FAIL_TOP_DOWN`), `pixelKind=atlas`, `reason`, `source` (`pixel` / `vlm`), VLM `q1` `q2` `q3` when present.

Product repairs that unblocked live PASS (not threshold weakening):

1. Harvest newest-mtime when Shared and install-root share a filename.
2. FLUX cfg 1.0 / steps 20 (not generic 3.5 / 28); unique Atlas prefix.
3. Pixel classifier accepts tall 9:16 corridor plates with the same axis-balance bar as square Atlases.
4. VLM image order is CANDIDATE first so Q1 is not answered on the eye-level SOURCE photo. Q1 is camera-only.

## Persistence / workspace / downstream

On the cert map only:

- Save (`savedVersion=10`). Reload + Studio API recycle: Atlas `e4008df4-…`, `geometrySource=designed`, corridor description, 1 character (Stability Cert Character — not Korri), 1 prop, 1 camera persist.
- Document fields vs production map: same schema (id, Atlas, geometrySource, sceneIntent/packet, characters/props/cameras, grid/scale, provenance). ERS generate was not re-charged; existing ERS/Scene handoff spec remains observe-only on its wired project.

## API + UI + Standard protection

Live Express **API** after Local evidence on disk: execution `126fe857-…`, job `dbefb698-…`, asset `752309ce-…`, `hostedModelId=gpt-image-2-kie`, `engineNote=gpt_image_2_atlas_design`, `generationMethod=api`, `forceWorkflowKey=null`, no `local_atlas_design`. Cert map restored to Local Atlas afterward. Production Atlas unchanged.

UI audit: no new model dropdown, no FLUX label, no Designer/Reconstruct switch. `reviewed / not applicable / owner-approved UI unchanged`.

Standard Home Reconstruct still MoGe (`test_explicit_reconstruct_still_uses_moge`). Empty-route + location image on Standard now stays reconstruct (not style-reference design).

## Comfy MCP (winner graph)

Against `:8188` and live prompt `993985d1-…` via `data/venvs/mcp/Scripts/comfy-mcp.exe`:

- `system_stats`: `cuda:0 NVIDIA GeForce RTX 5090`, VRAM total 34.19 GB, free 1.33 GB after resident FLUX
- `job`: completed; output `studio/2bc632b8_atlas_c7a687c9_00001_.png`
- `validate_workflow` on executed graph JSON: **valid=true**, 0 errors
- Graph: UNETLoader `flux1-kontext-dev.safetensors`, DualCLIPLoader (`clip_l` + `t5xxl_fp16`), CLIPTextEncode (appearance/layout, camera forbidden), EmptySD3LatentImage **576×1024**, KSampler euler/simple cfg **1.0** steps **20**, VAELoader `ae.safetensors`, VAEDecode, SaveImage. No LoadImage / camera I2I.

## Performance

| Workflow | Cold | Warm / product | Peak / free VRAM | Gate |
| --- | ---: | ---: | --- | --- |
| Bake-off winner sample | 50.67s first FLUX load | 6.03s | RTX 5090 | visual |
| Description-only product (UI+job+gate+save) | — | 6.38s wall (graph cached) / job 20.5s | free 1.33 GB after | PASS |
| Reference / lab / replace | — | 14–16s product | RTX 5090 | PASS |
| GPT Image 2 live | — | ~83s | N/A local VRAM | API path |

No silent CPU fallback. Device is CUDA 5090.

## Tests

| Suite | Result |
| --- | --- |
| Playwright live spec (`ADEPT_BETA_TARGET=1`, `:5173` / `:8758`, cert map) | **4 passed** (12.6s) |
| Frontend Spatial Map vitest | **152 passed** (19 files) |
| Protected backend rerun (local designer + dual-route + i2i + CC v2 + prop express/parity) | **106 passed** (`live/pytest_protected.txt`) |

## Auditors / peers

| Reviewer | Verdict | Disposition |
| --- | --- | --- |
| Kimi 2.7 auditor 1 (FLUX / residency / retry / MCP) | PASS | [FLUX/MCP auditor](b0181f2e-4f70-4c68-9752-f65ce2e0bd63) |
| Kimi 2.7 auditor 2 (map / placements / persist / ERS) | PASS after image-manifest repair | First BLOCK: PNGs hidden from glob. Re-audit PASS via `image_manifest.json` + on-disk PNGs. [persist auditor](30ce7fa9-1b6f-41ac-99b9-83d46b1f1380) |
| Peer A (Local/API/UI/tests) | PASS after Playwright log on disk | First BLOCK: no Playwright artifact. Re-audit PASS on `playwright_live.txt` (4 expected). [peer A](93dcb415-6f3a-4337-bb3d-83932d04a9c9) |
| Peer B (retry / persist / MCP / perf) | PASS | [peer B](835179b7-62b5-4d53-a407-101ae5f80adf) |

## Manual review

1. Open `http://127.0.0.1:5173/` → Adept Stability Cert → Co-Director → Spatial Map.
2. Select **Local Atlas Designer Cert** (not Supplementary View Assist Cert).
3. Confirm designed Local Atlas, placements, and that production Korri/Stability Atlas is untouched.

Default most-recent map is restored to the production Supplementary View Assist Cert after this pass.
