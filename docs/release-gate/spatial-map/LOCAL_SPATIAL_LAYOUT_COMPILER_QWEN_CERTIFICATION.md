# Local Interior/Exterior Spatial Layout Compiler → Qwen Atlas

**Historical for Local production quality.** The later Guide → FLUX Structural Control attempt is governed by `LOCAL_SPATIAL_FLUX_CONTROL_ATLAS_CERTIFICATION.md` and also deferred. This document remains the Qwen-pass record only.

Historical FLUX Local Atlas Designer certification is superseded for Local production quality: `LOCAL_ATLAS_DESIGNER_CERTIFICATION.md`.

API / GPT Image 2 remains the certified Spatial Map creation path.

**Verdict:** `NO-GO — LOCAL SPATIAL MAP ATLAS DESIGNER DEFERRED; GPT IMAGE 2 API REMAINS THE CERTIFIED SPATIAL MAP CREATION PATH`

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| Starting SHA | `b6156455e643d5fa430784b3130756f2d8038651` |
| Named project | Adept Stability Cert `2bc632b8-b329-4d3b-bc40-b68dc41b6bb1` |
| Production map (never write Atlas) | Supplementary View Assist Cert `e6f64c3b-2533-4549-a476-bf0dcb90d298` / Atlas `9f7d4571-9444-41fa-b4c2-29c27919736a` |
| Cert-only map | Local Atlas Designer Cert `a6176a4c-c25c-48c2-9077-ee8932ec4ced` |
| Local renderer | `qwen2512.atlas_layout` (experimental / Deferred). Retired camera I2I keys stay retired. No FLUX fallback. |
| Guide renderer | Internal PIL (`layout_compiler.py`). **Maker.js rejected:** JS CAD, not in-repo, Python backend already has a deterministic raster. Apache-2.0 compatible via existing stack. |

Review URLs left running:

- Creator UI `http://127.0.0.1:5173/`
- Studio API `http://127.0.0.1:8758/`
- Comfy `http://127.0.0.1:8188/` (Desktop Comfy reused; supervisor `--force` was not used)

---

## Architecture implemented

```
Environment Description + optional appearance reference + Local-only Environment Type
  → Environment Design Packet (environmentClass + existing free-form environmentType)
  → Interior or Exterior Spatial Layout Compiler
  → shared deterministic structural guide (SVG/PNG authority)
  → Qwen Atlas Renderer (qwen2512.atlas_layout)
  → topology / semantic / appearance gate
  → Spatial Map (cert map only)
```

Authority split:

- Guide = topology
- Description / packet = semantics
- Reference / appearance prior = materials only
- `geometrySource=designed` on both Local branches. Express Local does not go through MoGe/VGGT.

API / GPT Image 2 provider, prompts, gate, retry, resolver, and Express API chrome were not changed.

---

## Isolation

| Check | Result |
| --- | --- |
| Production Atlas after Interior live | unchanged `9f7d4571-…` |
| Production Atlas after Exterior live | unchanged `9f7d4571-…` |
| Production Atlas after recency restore | unchanged `9f7d4571-…` |
| `getMostRecentMap` default after cert | production `e6f64c3b-…` |
| GPT leak on Local jobs | none observed |
| FLUX fallback | none (`flux.txt2img` not used) |

Evidence: `docs/release-gate/spatial-map/evidence/local_layout_compiler_qwen/live/`.

---

## Live E2E

### Interior corridor (owner case, parser-derived)

Owner text: long silver metallic corridor, far-end elevator, right-mid Combat Chamber, yellow strip.

| Step | Result |
| --- | --- |
| Packet / compiler | PASS — `environmentClass=interior`, corridor, elevator, Combat Chamber, yellow strip |
| Guide | PASS — deterministic top-down footprint |
| Qwen `atlas_layout` | RAN — 576×1024, 28 steps |
| Harvest | PASS after `/view` + Install-output candidate dirs (first run failed harvest; repaired) |
| Visual gate | FAIL — `FAIL_TOP_DOWN` |
| Owner quality | **FAIL** — plate is a noisy schematic / color-block guide, not a recognizable silver metallic corridor |

Bounded repair applied once: stronger paint prompt + packet-derived PIL appearance prior on dual-image Plus (`image1=guide`, `image2=spatial_appearance_prior`). Qwen still returned a diagram, not a painted environment.

First harvest miss: Comfy wrote `2bc632b8_atlas_ce6b8dee_00001_.png` to Desktop **Install** output. Shared output did not have it. `/view` served it. Repair: candidate dirs + `/view` fallback.

### Exterior forest (owner case, parser-derived)

| Step | Result |
| --- | --- |
| Packet / compiler | PASS — forest, clearing, west river, SE trail, NE fallen tree, northern hill. Not forced into rooms. |
| Guide | PASS |
| Qwen `atlas_layout` | RAN — dual-image Plus, 70.5s |
| Visual gate | reported PASS (false accept of a color-block site plan) |
| Owner quality | **FAIL** — schematic site-plan graphic, not a recognizable painted forest Atlas |
| Applied to cert map | yes (cert-only). Production untouched. |

Reference-conditioned Interior/Exterior live modes were **not** run after owner-quality failure. The plan forbids another model experiment once corridor/forest fail after bounded repair.

### Comfy graph (exterior live)

Evidence: `live/exterior_comfy_mcp_summary.json`

| Slot | Value |
| --- | --- |
| UNET | `qwen_image_2512_fp8_e4m3fn.safetensors` |
| CLIP | `qwen_2.5_vl_7b_fp8_scaled.safetensors` (`type=qwen_image`) |
| VAE | `qwen_image_vae.safetensors` |
| image1 | `studio/spatial_design_guide.png` |
| image2 | `studio/spatial_appearance_prior.png` |
| Encoder | `TextEncodeQwenImageEditPlus` |
| Sampler | euler / simple / 28 / cfg 4.0 / denoise 1.0 |
| Output | `studio/2bc632b8_atlas_4baf9d5d` |

Retired keys `qwen2512.atlas` and `qwen2512.atlas_direct` were not used.

---

## Tests

| Suite | Result |
| --- | --- |
| `test_spatial_layout_compiler.py` + harvest + local designer + Qwen atlas workflow + atlas i2i + Prop Express | **42 passed** |
| Spatial Map frontend vitest | **152 passed** (19 files) |
| Playwright `spatial-map-environment-type.spec.ts` against Vite `:5173` | **1 passed** |
| Prop Express + Local Atlas / Qwen layout / harvest | included in the 42 passed above |
| Character candidate routing (`test_character_candidate_routing.py`) | 12 failed — pre-existing candidate-count / zimage vs flux assertions, not touched by this milestone |

API isolation unit: Local sends `environmentType` / Interior or Exterior compiler; API ignores stale Local class and stays on GPT Image 2.

---

## E2E TRACE

| Stage | Interior | Exterior |
| --- | --- | --- |
| User action | Local + Interior + owner corridor text | Local + Exterior + owner forest text |
| Frontend | Express Local payload includes `environmentType` | same |
| API | `atlas.generate` local branch | same |
| Backend | packet + layout compiler + guide | same |
| Persistence | guide + job asset persisted | same; cert map background updated |
| Runtime | Qwen 2512 layout graph on GPU Comfy | same |
| Result | schematic, not painted corridor | schematic site plan |
| Reload | N/A (not assigned) | cert map only |
| Downstream | not certified | not certified |

---

## Why Local is deferred

The compiler and guide did their job. Qwen Image Edit / Edit Plus treated the guide as the image to keep, not as a floorplan to paint. Owner quality requires a recognizable long silver corridor (elevator, right-mid Combat Chamber, yellow safety strip) and a recognizable forest site-plan environment. Color-block diagrams fail that bar.

The plan is explicit: after one clean implement + bounded repair, stop. Do not start another model bake-off.

Local Atlas design is **experimental**. GPT Image 2 API remains the certified creation path.

---

## Limitations

- Owner-quality Local corridor and forest failed.
- Exterior visual gate false-accepted a schematic.
- Reference-conditioned live modes not run after the quality stop.
- Playwright Environment Type spec can no-op if an existing map hides the empty Express form; form isolation is covered by unit/vitest.
- Live forest evidence still shows the pre-repair `environmentSubtype=interior` snapshot. The merge path now drops a stale subtype when Local class changes; `test_spatial_layout_compiler.py` covers re-inference (`13 passed` after the repair).
- Studio API recycle reuses a healthy process unless the PID is explicitly recycled; code changes required an API-only recycle (Comfy left running).

---

## Manual review

1. Open `http://127.0.0.1:5173/` on Adept Stability Cert.
2. Spatial Map should open the production Supplementary View Assist Cert map (Atlas `9f7d4571-…`).
3. Express Local shows Environment Type; API hides it.
4. Do not treat Local Generate as production-ready.
5. Evidence plates: `docs/release-gate/spatial-map/evidence/local_layout_compiler_qwen/live/interior_corridor.png`, `exterior_forest.png`.

---

## Auditors and peers

| Review | Result | BLOCK tickets |
| --- | --- | --- |
| Auditor 2 — Qwen rendering / Comfy / API isolation | READY FOR PRIMARY REVIEW | none |
| Auditor 1 — Spatial Layout | BLOCK then repaired | `SPATIAL-LAYOUT-SUBTYPE-MERGE` closed |
| Peer — layout isolation | READY FOR PRIMARY REVIEW | none |
| Peer — quality stop | READY FOR PRIMARY REVIEW | none |

Auditor 2 confirmed: guide required, retired I2I keys stay blocked, no FLUX fallback, live exterior slot order `image1=guide` / `image2=appearance prior`, harvest `/view` + Install output, GPT path frozen, owner-quality failure honestly documented. Retired builder functions may remain in source as long as the resolver is the selector.

Auditor 1 BLOCK `SPATIAL-LAYOUT-SUBTYPE-MERGE`: Local merge kept a prior `environmentSubtype=interior` on an exterior packet. Repair pops stale subtype on Local class change and ignores class-incompatible leftover subtypes in `compile_environment_design`. Both peers returned READY with no BLOCKs.

---

## Final language

`NO-GO — LOCAL SPATIAL MAP ATLAS DESIGNER DEFERRED; GPT IMAGE 2 API REMAINS THE CERTIFIED SPATIAL MAP CREATION PATH`
