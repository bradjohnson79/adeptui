# Local Spatial Map: Guide → FLUX.1-dev Structural Control

**Historical / deferred.** Not current production truth. Current governing document: `SPATIAL_MAP_API_ONLY_PRODUCTION_CERTIFICATION.md`.

R&D weights `flux1-dev.safetensors` and `instantx_flux1_dev_union.safetensors` were uninstalled after the API-only production cleanup. Compilers remain isolated Deferred R&D.

Historical Local production-quality reports (not current truth for a certified Local Atlas designer):

- Qwen layout compiler pass: `LOCAL_SPATIAL_LAYOUT_COMPILER_QWEN_CERTIFICATION.md` (deferred; compiler/guide PASS, paint FAIL)
- Plain FLUX `txt2img` pass: `LOCAL_ATLAS_DESIGNER_CERTIFICATION.md` (owner-rejected corridor)
- Prior Phase 0 inventory-only stop (no weights): superseded by this authorized R&D install + raw Comfy gate

API / GPT Image 2 remains the certified Spatial Map creation path. That path is frozen.

**Verdict:** `NO-GO — LOCAL SPATIAL MAP ATLAS DESIGNER DEFERRED; GPT IMAGE 2 API REMAINS THE CERTIFIED SPATIAL MAP CREATION PATH`

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| Named project | Adept Stability Cert `2bc632b8-b329-4d3b-bc40-b68dc41b6bb1` |
| Production map (never write Atlas) | Supplementary View Assist Cert `e6f64c3b-2533-4549-a476-bf0dcb90d298` / Atlas `9f7d4571-9444-41fa-b4c2-29c27919736a` |
| Cert-only map | Local Atlas Designer Cert `a6176a4c-c25c-48c2-9077-ee8932ec4ced` (not written this pass) |
| Raw stack | `flux1-dev.safetensors` + `instantx_flux1_dev_union.safetensors` |
| Adept key | `flux.atlas_layout_control` — **not implemented** (raw owner FAIL) |

Review URLs left running:

- Creator UI `http://127.0.0.1:5173/`
- Studio API `http://127.0.0.1:8758/`
- Comfy `http://127.0.0.1:8188/` (Desktop Comfy reused; supervisor `--force` was not used)

Evidence: `docs/release-gate/spatial-map/evidence/flux_control_atlas/`.

---

## Phase 0 — Live inventory before install

MCP + `:8188` reconfirm (`phase0/phase0_reconfirm.json`, `phase0/comfy_mcp_reconfirm.json`):

| Check | Observed |
| --- | --- |
| Nodes | `ControlNetLoader`, `ControlNetApplyAdvanced`, `Canny`, `SetUnionControlNetType`, `SetShakkerLabsUnionControlNetType` |
| `ControlNetLoader` before install | 0 models |
| FLUX UNets before install | `flux1-kontext-dev.safetensors` only |
| CLIP / T5 / VAE | Reused `clip_l.safetensors`, `t5xxl_fp16.safetensors`, `ae.safetensors` |
| GPU | RTX 5090, CUDA, ~2.1 GB free before unload |

Kontext was not used for InstantX and was not replaced.

---

## Licenses (R&D / local qualification)

Written before download. Not Apache-2.0. Not Adept redistribution. Not hosted commercial production. Adept may later support user-supplied gated weights.

| Component | Source | License | Status |
| --- | --- | --- | --- |
| `flux1_dev_local` | `black-forest-labs/FLUX.1-dev` / `flux1-dev.safetensors` | FLUX.1-dev Non-Commercial License | `TERMS_RESTRICTED` |
| `instantx_flux_controlnet_union` | `InstantX/FLUX.1-dev-Controlnet-Union` | `flux-1-dev-non-commercial-license` | `TERMS_RESTRICTED` |

Rows: [studio-api/app/setup/license_metadata.py](studio-api/app/setup/license_metadata.py). Evidence: `phase0/licenses.json`.

Install landed in Desktop Shared models:

- `models/diffusion_models/flux1-dev.safetensors` (23.80 GB)
- `models/controlnet/instantx_flux1_dev_union.safetensors` (6.60 GB)

After install, live loaders listed both files. Hugging Face was not gated on this machine.

---

## Raw Comfy corridor

Guide exported from existing Interior compiler (exact owner sentence). Visual inspect **PASS** on the guide: long corridor, walls, far-end elevator (top), right-mid Combat Chamber, yellow strip, north-up. `raw_comfy/corridor_guide.png`.

Isolated graph (not Adept routing):

```text
LoadImage guide → Canny → ControlNetLoader (InstantX Union)
→ SetShakkerLabsUnionControlNetType type=canny
→ ControlNetApplyAdvanced
→ UNETLoader flux1-dev + DualCLIP + text
→ EmptySD3LatentImage 576×1024 → KSampler euler/simple 24 / cfg 3.5
→ VAE ae → Save
```

No Kontext. No img2img-as-control. No appearance reference (topology never passed).

MCP `validate_workflow` on `graph_s065.json`: **valid**. Executed graph MCP: `raw_comfy/mcp_executed.json` — UNet `flux1-dev.safetensors`, control `instantx_flux1_dev_union.safetensors`, strength 0.65, GPU RTX 5090.

| Strength | Prompt id | Elapsed | Plate |
| --- | --- | --- | --- |
| 0.45 | `289d26a2-…` | 44.04 s cold | `corridor_s045.png` |
| 0.65 | `cff01443-…` | 18.02 s | `corridor_s065.png` |
| 0.80 | `fad8f93e-…` | 20.02 s | `corridor_s08.png` |

VRAM: ~32.3 GB free after unload; ~1.7–1.9 GB free after resident FLUX+ControlNet. Warm sample ~18–20 s. Performance is not the blocker.

---

## Owner decision

**FAIL.**

All three plates are photoreal **eye-level / one-point-perspective** silver halls with **ceilings**. They are not roofless top-down Atlases. Far door reads as a vanishing-point elevator, not a plan-view north anchor. Combat Chamber is not a right-mid plan room. Camera law failed at every strength.

The guide was correct. FLUX painted a walkable corridor instead of a site-plan Atlas. Bounded strength repair is exhausted. Appearance reference was not run. Adept was not wired.

---

## Product wiring

Not entered. `LOCAL_ATLAS_CANDIDATES` still experimental `qwen2512.atlas_layout` (`certified: False`). No `flux.atlas_layout_control`. Forest E2E, Playwright generate, and workspace cert were not opened.

---

## Isolation

| Check | Result |
| --- | --- |
| Production Atlas | unchanged `9f7d4571-…` |
| GPT Image 2 API | frozen; not edited |
| Kontext UNet | left installed; not used in the raw graph |
| Extra ControlNet families | not installed |

---

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | N/A — raw Comfy R&D only |
| Frontend | Unchanged |
| API | Unchanged |
| Backend | Compilers reused for guide export only |
| Persistence | Evidence plates on disk; no Atlas write |
| Runtime | FLUX.1-dev + InstantX Union on GPU |
| Result | Perspective corridors — owner FAIL |
| Reload | Production map remains default |
| Downstream | GPT Image 2 remains certified |

---

## Why this is the intended stop

The stack loaded and ran. InstantX enforced a corridor-shaped scene, but the **camera class** stayed first-person. That is not a Spatial Map Atlas. The mission forbids another family, another model, Qwen, or wiring a failed graph.

Local Atlas design stays **experimental / uncertified**. No further Local model experiment in this milestone.

---

## Limitations

- Owner visual FAIL on raw plates; no Adept Local designer.
- Weights remain on disk as R&D assets under restricted licenses.
- Playwright generate against a missing Adept key was not invented.

---

## Manual review

1. Open `http://127.0.0.1:5173/` on Adept Stability Cert — production map / Atlas `9f7d4571-…`.
2. Compare `raw_comfy/corridor_guide.png` (correct topology) with `corridor_s045.png`, `corridor_s065.png`, `corridor_s08.png` (wrong camera).
3. Do not treat Local Generate as production-ready.
4. Use API / GPT Image 2 to create Spatial Maps.

---

## Auditors and peers

| Review | Model | Result | BLOCK tickets |
| --- | --- | --- | --- |
| Auditor 1 — structural-control / MCP / topology | Kimi 2.7 | READY FOR PRIMARY REVIEW | none |
| Peer — sole peer | Composer 2.5 | **PASS** (stop package, not Local Atlas GO) | none |

Product-integration auditor not invoked (no Adept wiring).

Auditor 1: license recorded, flux1-dev not Kontext, genuine ControlNet path, MCP executed graph, topology FAIL honest, Adept unwired.

Composer 2.5: corridor FAIL is correct; control enforced a hall, not Atlas camera law; stop-condition complete.

---

## Final language

`NO-GO — LOCAL SPATIAL MAP ATLAS DESIGNER DEFERRED; GPT IMAGE 2 API REMAINS THE CERTIFIED SPATIAL MAP CREATION PATH`
