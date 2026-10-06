# FLUX Kontext Candidate Graphs — Comfy MCP Inspection

**Date:** 2026-08-24 04:01 UTC  
**Status:** Candidate graphs MCP-validated and smoke-executed. **Not wired** into Character Creator. **Not certified.**

Owner sources:

- `C:\Users\bradj\Downloads\character_flux_front_kontext_ref.json`
- `C:\Users\bradj\Downloads\character_flux_back_from_front_kontext_ref.json`

Review copies:

- `docs/release-gate/character-creator/workflows/candidates/`

---

## Verdict

| Gate | Result |
|---|---|
| Live `:8188` node signatures | PASS — `FluxKontextImageScale`, `ReferenceLatent`, `FluxGuidance`, `ConditioningZeroOut`, loaders, VAE, KSampler all exist in core |
| MCP `validate_workflow` Front | PASS — `valid: true`, 0 errors, 0 warnings |
| MCP `validate_workflow` Back | PASS — `valid: true`, 0 errors, 0 warnings |
| MCP `workflow_deps` | PASS — no unknown nodes, no missing custom packs |
| Official Kontext topology match | PASS — same reference-conditioning pattern as `flux_kontext_dev_basic` |
| Direct MCP smoke Front | PASS — completed, PNG written |
| Direct MCP smoke Back | PASS — completed, PNG written |
| Source-level JSON corrections | None required |
| Character Creator wiring | **Not done** |
| Certification | **Not done** |

---

## What MCP checked on live `:8188`

Comfy MCP `nodes action=get` against the running catalog (`object_info` via MCP, not a raw HTTP substitute):

| Node | Required inputs on this install | Candidate JSON |
|---|---|---|
| `FluxKontextImageScale` | `image` (IMAGE) | matches |
| `VAEEncode` | `pixels`, `vae` | matches |
| `ReferenceLatent` | `conditioning` required; `latent` optional | both wired |
| `FluxGuidance` | `conditioning`, `guidance` (default 3.5, range 0–100) | `guidance: 2.5` — same as official template |
| `ConditioningZeroOut` | `conditioning` | matches |
| `UNETLoader` | `unet_name`, `weight_dtype` | `flux1-kontext-dev.safetensors` / `default` — present in live combo |
| `DualCLIPLoader` | `clip_name1`, `clip_name2`, `type`, `device` | `clip_l.safetensors` + `t5xxl_fp16.safetensors`, `type=flux` — present |
| `VAELoader` | `vae_name` | `ae.safetensors` — present |

`KSampler`: 20 steps, CFG 1.0, euler / simple, denoise 1.0 — same widgets as the official basic template.

---

## Official template comparison

MCP fetched `flux_kontext_dev_basic` (“Flux Kontext Dev Image Edit”).

Default official subgraph wires:

`LoadImage → FluxKontextImageScale → VAEEncode`  
then the encoded latent goes to **both** `ReferenceLatent.latent` and `KSampler.latent_image`, with `denoise=1.0`, `FluxGuidance=2.5`, and `ConditioningZeroOut` as negative.

The owner candidates use that same pattern. They are **not** conventional latent img2img (no denoise 0.35 path).

The gallery template is **not runnable as-shipped** on this install because it names `flux1-dev-kontext_fp8_scaled.safetensors` and `t5xxl_fp8_e4m3fn_scaled.safetensors`. The candidate files correctly use the live Adept stack: `flux1-kontext-dev.safetensors`, `ae.safetensors`, `clip_l.safetensors`, `t5xxl_fp16.safetensors`.

Official note: `EmptySD3LatentImage` is optional if you want a custom canvas size. It is not required for the basic recipe.

---

## Direct smoke (not Character Creator)

Disposable geometric stand-ins were uploaded via MCP `upload_file` as:

- `character_creator_reference.png`
- `character_creator_approved_front.png`

These are **not** Schnick, Korri, or Mira. They exist only to prove LoadImage + reference-conditioning execute.

| Graph | Prompt id | MCP status | Output |
|---|---|---|---|
| Front | `066fa35b-57b1-44bc-a026-fdd6666ac739` | completed, `error: null` | `studio/character_creator/flux_kontext_front_ref_00001_.png` |
| Back | `f52cc805-ea1a-42b2-95f0-de59edb68249` | completed, `error: null` | `studio/character_creator/flux_kontext_back_from_front_00001_.png` |

Local copies:

- `artifacts/character-creator/workflows/kontext-smoke/outputs/flux_kontext_front_ref_00001_.png`
- `artifacts/character-creator/workflows/kontext-smoke/outputs/flux_kontext_back_from_front_00001_.png`

Observed: Front kept the blue torso / tan head / navy legs and stayed front-facing. Back kept the red torso / black hair block and produced a rear view. That is wiring-and-conditioning evidence only, not Character Creator quality certification.

Runtime: CUDA RTX 5090. After the two runs, free VRAM was about 2.3 GB of 34 GB.

---

## Not done

- No Character Creator route change
- No `flux.img2img` builder rewrite
- No certified-registry change
- No prompt-compiler change
- No Adept job enqueue
