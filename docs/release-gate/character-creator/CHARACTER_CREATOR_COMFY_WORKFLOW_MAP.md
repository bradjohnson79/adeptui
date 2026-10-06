# Character Creator — Comfy MCP Workflow Map

**Date:** 2026-08-24  
**Branch:** `feat/character-creator-final-closure`  
**Live Comfy:** `http://127.0.0.1:8188` (Comfy MCP `server_info` + `validate_workflow`)  
**Comfy MCP:** `data/venvs/mcp/Scripts/comfy-mcp.exe` with `COMFY_BIN=data/venvs/mcp/Scripts/comfy.exe`  
**Comfy core:** v0.32.0 · GPU `cuda:0 NVIDIA GeForce RTX 5090`  
**Review URLs:** local creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/`  
**Retired:** do not use `:8760`

This is the governing workflow-acceptance map for Character Creator V2 Comfy graphs.  
It does **not** redesign Character Creator, Scene Creator, Timeline, ERS, MAGI, or JobQueue.

**No operation is CERTIFIED in this pass.**  
CERTIFIED requires MCP node inspection, MCP validation, model proof, reference-binding proof, direct `prompt_id` + history/output, Character Creator route proof, **and** visual acceptance of the product path. Direct smoke alone is not Character Creator certification.

Status classes used here:

| Class | Meaning |
| --- | --- |
| CERTIFIED | Full evidence chain for that operation. None this pass. |
| TESTING | Graph exists, MCP-valid, and/or smoked, but product-path visual acceptance or wiring is incomplete. |
| UNSUPPORTED | No legitimate graph for that operation. No placeholder invented. |
| UNAVAILABLE | Family exists but this operation cannot be offered (same as UNSUPPORTED for Illustrious I2I/Back). |

Creator-facing UI still uses **Available / Requires Setup / Unavailable**. These map classes are for owner review, not dropdown chrome.

---

## 1. Comfy MCP restore / confirm

| Check | Result |
| --- | --- |
| Cursor IDE `comfy` MCP namespace | Not present. Cursor cannot invoke Comfy MCP as a native IDE tool. |
| Standalone Comfy MCP stdio | Present and used. |
| Target URL | `http://127.0.0.1:8188` (`server_info.server.url`) |
| Tools used | `server_info`, `nodes`, `validate_workflow`, `workflow_deps`, `upload_file`, `run_workflow`, `job`, `free_memory` |
| `/object_info` used as substitute? | No. HTTP `/queue` and `/history` were used only to watch smoke progress. |

If the IDE namespace is later restored, re-run the same `validate_workflow` / `nodes` calls through it. The stdio path already targeted the live production Comfy.

---

## 2. Capability table

Final review JSONs live in `docs/release-gate/character-creator/workflows/final/`.

| Generator | Operation | Workflow JSON | Workflow Key | Reference Source | MCP Valid | Live Smoke | Character Creator Status |
| --------- | --------- | ------------- | ------------ | ---------------- | --------: | ---------: | ------------------------ |
| Qwen Image 2512 | Front no-ref (`FRONT_T2I`) | `character_qwen_front_t2i.json` | `qwen2512.txt2img` | none | YES | YES | TESTING |
| Qwen Image 2512 | Front ref (`FRONT_REFERENCE_I2I`) | `character_qwen_front_ref.json` | `qwen2512.ref` | uploaded ref | YES | YES (graph). Visual FAIL on geometric dummy | TESTING |
| Qwen Image 2512 | Back (`BACK_FROM_FRONT`) | `character_qwen_back_from_front.json` | `qwen2512.ref` | approved Front | YES | same topology; prior Mira Back | TESTING |
| Qwen Image 2512 | Close-up (`CLOSEUP_FROM_FRONT`) | same as Back JSON | `qwen2512.ref` | approved Front | YES | no dedicated graph; no live Close-up GPU | TESTING |
| FLUX | Front no-ref (`FRONT_T2I`) | `character_flux_front_t2i.json` (prompt-cleaned export) | `flux.txt2img` | none | YES | YES (graph). Visual FAIL — two people | TESTING |
| FLUX | Front ref — **accepted Kontext graph** | `character_flux_front_ref.json` | **not wired** (candidate) | uploaded ref | YES | YES — `066fa35b-…` | TESTING |
| FLUX | Front ref — **production wired** | `final/production-wired/character_flux_front_ref.production_img2img.json` | `flux.img2img` | uploaded ref | YES | not re-smoked this pass | TESTING — conventional img2img, not Kontext |
| FLUX | Back — **accepted Kontext graph** | `character_flux_back_from_front.json` | **not wired** (candidate) | approved Front | YES | YES — `f52cc805-…` | TESTING |
| FLUX | Back — **production wired** | `final/production-wired/character_flux_back_from_front.production_img2img.json` | `flux.img2img` | approved Front | YES | not re-smoked this pass | TESTING — conventional img2img, not Kontext |
| FLUX | Close-up | same as Back (production `flux.img2img`) | `flux.img2img` | approved Front | YES | no dedicated graph | TESTING |
| Illustrious XL (SDXL) | Front no-ref (`FRONT_T2I`) | `character_sdxl_front_t2i.json` | `illustrious.txt2img` | none | YES | YES (graph). Visual FAIL — unusable silhouette | TESTING |
| Illustrious XL (SDXL) | Front ref | — | none | — | n/a | n/a | UNSUPPORTED |
| Illustrious XL (SDXL) | Back | — | none | — | n/a | n/a | UNSUPPORTED |
| Illustrious XL (SDXL) | Close-up | — | none | — | n/a | n/a | UNSUPPORTED |
| Z-Image | Front no-ref (`FRONT_T2I`) | `character_zimage_front_t2i.json` | `zimage.txt2img` | none | YES | YES | TESTING |
| Z-Image | Front ref (`FRONT_REFERENCE_I2I`) | `character_zimage_front_ref.json` | `zimage.ref_edit` | uploaded ref | YES | pending after Omni image1+vae repair | TESTING — Omni `reference_latents` + matching VAEEncode |
| Z-Image | Back (`BACK_FROM_FRONT`) | `character_zimage_back_from_front.json` | `zimage.ref_edit` | approved Front | YES | same topology as Front ref | TESTING |
| Z-Image | Close-up | same as Back JSON | `zimage.ref_edit` | approved Front | YES | no dedicated graph | TESTING |
| GPT Image | Front / Back | hosted API, not Comfy | none | hosted I2I if configured | n/a | n/a | not in this Comfy audit |

Close-up never has a separate topology. It reuses the family’s Back / I2I graph and changes only the compiled prompt/role.

---

## 3. Capability proof by family

### Qwen Image 2512

```text
FRONT_T2I: YES
FRONT_REFERENCE_I2I: YES
BACK_FROM_FRONT: YES
CLOSEUP_FROM_FRONT: YES (same graph as Back; prompt/role only)
```

| Item | Front T2I | Front ref / Back |
| --- | --- | --- |
| UNET | `qwen_image_2512_fp8_e4m3fn.safetensors` | same |
| CLIP | `qwen_2.5_vl_7b_fp8_scaled.safetensors` (`type=qwen_image`) | same |
| VAE | `qwen_image_vae.safetensors` | same |
| Loader | `UNETLoader` + `CLIPLoader` + `VAELoader` + `ModelSamplingAuraFlow` shift 1.73 | same |
| Latent | `EmptyLatentImage` 2048² denoise 1.0 | `EmptyLatentImage` 2048² denoise 1.0 |
| Reference | none | `LoadImage` → **both** `TextEncodeQwenImageEdit` (pos + neg) `image` + `vae` |
| Sampling | 20 / 3.5 / euler / simple / denoise 1.0 | 50 / 4.0 / euler / simple / denoise 1.0 |
| Output | `VAEDecode` → `SaveImage` `studio/character_creator/qwen2512_*` | same |

Reference semantics: **dedicated Qwen image-edit conditioning**, not starting-latent I2I. Job denoise `0.35` is **not** applied to this graph (hardcoded 1.0). That is execute-path truth, not a silent T2I fallback.

Direct Front T2I smoke (this pass): one adult, front-facing, full body, head-to-feet, neutral standing pose, clean studio background, no collage / insets / extra figures / text. Visual acceptance of the **graph** = PASS. Not a named Character Creator profile.

Direct Front ref smoke (this pass, geometric dummy): **visual FAIL** — collage / multiple figurines around an inset of the reference. The graph executed and bound `character_creator_reference.png` through `TextEncodeQwenImageEdit`. Topology is not the defect. Do not retune the Qwen compiler in this pass. Prior Mira Front I2I with a real photo reference remains the Character Creator route proof.

Prior Character Creator route (cert project, not this-pass enqueue):

| Character | View | Key | Asset |
| --- | --- | --- | --- |
| Mira Vale `cf4437c7-…` | Front I2I | `qwen2512.ref` | `/api/assets/7867b14e-…/file` |
| same | Back I2I | `qwen2512.ref` from Front `7867b14e-…` | `/api/assets/86719bb2-…/file` |
| Mira Vale Open `9cc4c839-…` | Front T2I | `qwen2512.txt2img` | `/api/assets/b2263863-…/file` |

### FLUX

```text
FRONT_T2I: YES
FRONT_REFERENCE_I2I: YES on accepted Kontext graph; production still conventional img2img
BACK_FROM_FRONT: YES on accepted Kontext graph; production still conventional img2img
CLOSEUP_FROM_FRONT: YES only as reuse of the I2I graph
```

Accepted Kontext stack (matches official `flux_kontext_dev_basic` on this install):

| Item | Value |
| --- | --- |
| UNET | `flux1-kontext-dev.safetensors` / `UNETLoader` / `weight_dtype=default` |
| CLIP | `DualCLIPLoader` `clip_l.safetensors` + `t5xxl_fp16.safetensors` `type=flux` |
| VAE | `ae.safetensors` |
| Reference path | `LoadImage` → `FluxKontextImageScale` → `VAEEncode` → **both** `ReferenceLatent.latent` and `KSampler.latent_image` |
| Guidance | `FluxGuidance` 2.5 on `ReferenceLatent` output |
| Negative | `ConditioningZeroOut` of the **positive** CLIP encode. No negative-token dump into the positive string. |
| Sampling | 20 / cfg 1.0 / euler / simple / denoise **1.0** |
| Front LoadImage | `character_creator_reference.png` |
| Back LoadImage | `character_creator_approved_front.png` |

Production wired path (`flux.img2img` / `build_flux_img2img_workflow`):

| Item | Value |
| --- | --- |
| Reference | `LoadImage` → `VAEEncode` → `KSampler.latent_image` only |
| Missing | `FluxKontextImageScale`, `ReferenceLatent`, `FluxGuidance` |
| Denoise | 0.35 |
| CFG | live remap to 3.5 unless cfg is already 1.0 |
| Prompt | `_flux_positive_negative_nodes` **appends the negative string onto the positive CLIP text**, then ZeroOuts that same encode |

The live MCP contract wins: official Kontext identity on this install is ReferenceLatent + FluxGuidance, not low-denoise starting latent. Production Character Creator still submits the conventional graph. **Not wired this pass** because `flux.img2img` is a certified shared key (Scene Creator / Image Generator / Prop). Swapping Kontext onto that key would break the fingerprint. Required source repair is a **new CC-only key** (recommended `flux.cc_v2_kontext_ref`) plus `build_flux_kontext_ref_workflow`. Do not rewrite `build_flux_img2img_workflow`. Do not reuse Draft `flux.kontext_edit`.

Prompt-cleaned Front T2I export uses empty negative and cfg 1.0. Live Character Creator still concatenates the FLUX compiler negative into the positive caption.

Kontext direct smoke (disposable geometry, not Schnick/Korri/Mira): Front kept blue torso / front view; Back kept red torso / rear view. Wiring proof only.

### Illustrious XL (this product’s SDXL)

```text
FRONT_T2I: YES
FRONT_REFERENCE_I2I: NO
BACK_FROM_FRONT: NO
CLOSEUP_FROM_FRONT: NO
```

| Item | Value |
| --- | --- |
| Checkpoint | `Illustrious-XL-v1.0.safetensors` via `CheckpointLoaderSimple` |
| Conditioning | separate positive / negative `CLIPTextEncode` |
| Latent | `EmptyLatentImage` 2048² |
| Sampling | 28 / 5.0 / euler / normal / denoise 1.0 |
| Output | `VAEDecode` → `SaveImage` |

Installed EasyUse IPAdapter and SD1.5 ControlNet exist in the Comfy pack list. Character Creator does **not** use them. No legitimate Illustrious identity/reference graph is routed. No fake I2I JSON was created.

### Z-Image

```text
FRONT_T2I: YES
FRONT_REFERENCE_I2I: YES (Omni image1+vae reference_latents + matching VAEEncode)
BACK_FROM_FRONT: YES (same)
CLOSEUP_FROM_FRONT: YES (same graph)
```

| Item | T2I | Ref / Back |
| --- | --- | --- |
| UNET | `z_image_turbo_bf16.safetensors` | same |
| CLIP | `qwen_3_4b.safetensors` `type=lumina2` | same |
| VAE | `ae.safetensors` | same |
| Text | `TextEncodeZImageOmni` text-only | `TextEncodeZImageOmni` **image1 + vae** (`auto_resize_images=false`) |
| Reference | none | Scaled pixels enter Omni `image1` (official `reference_latents` on CONDITIONING) **and** `VAEEncode` → `KSampler.latent_image` |
| Sampling | 8 / 1.0 / euler / simple / denoise 1.0 | 8 / 1.0 / euler / simple / denoise 0.72 |

MCP contract (`nodes action=get` on `:8188`, confirmed in `comfy_extras/nodes_zimage.py`): optional `image1`/`image2`/`image3` (IMAGE), optional `vae` (VAE), optional `image_encoder` (CLIP_VISION). When `image1` + `vae` are bound, Omni writes `reference_latents` into conditioning. The previous text-only graph was **not** the installed ref-edit architecture. EmptyLatent + Omni(image) previously crashed on shape mismatch; the repair keeps a matching VAEEncode starting latent and turns Omni auto-resize off so both latents stay at the 2048² canvas.

Execute `zimage.ref_edit` still does not pass Character Creator job denoise 0.35; builder default 0.72 wins. CLIP vision `image_encoder` is not bound (optional; no certified encoder wired).

---

## 4. Prompt construction (after graph correctness)

Shared intent (all families): one person, one view, full body, correct orientation, neutral pose, clean background, identity preserved, wardrobe preserved, no collage, no extra figures, no inset portraits, no text.

Provider compilers already differ. Do not force one generic template.

| Family | Compiler | Positive | Negative |
| --- | --- | --- | --- |
| Qwen | `compile_character_image_prompt` (13-block package) | Numbered blocks; identity facts stay here | Composition/quality rejects only for non-Korri. Korri may still reject Anadriya sibling traits. Bound to the negative `TextEncodeQwenImageEdit`. |
| FLUX | `compile_flux_crs_single_view` (T5 caption) | Single-view caption, anti-collage, no sheet/turnaround tokens | `FLUX_CRS_NEGATIVE` is already composition-only. Live shared builder still concatenates that string onto the positive CLIP text. |
| Illustrious / SDXL / Z-Image | Qwen 13-block package via `_compile_visual_prompt` fallback | Same Qwen package | Same composition-only default / compiler list. Exported graphs rebuilt 2026-08-24. |

**Repaired source defect:** `DEFAULT_NEGATIVE_PROMPT` and the export fixture were a Korri-vs-Anadriya appearance list (`blonde hair`, `aqua eyes`, `metallic clothing`, …) applied to every character. `build_negative_constraints` also always added “missing wooden accessories / missing light-circuitry markings”. Those are now composition-only unless the character is Korri, and any negative that restates a locked profile trait is stripped.

Qwen graph slots stay split. The 13-block package still includes a `negative_constraints` block inside the positive string; that block now uses the same repaired list.

---

## 5. Direct smoke

Disposable assets only. Geometric stand-ins for reference binds. Not Schnick / Korri / Mira.

| Workflow | prompt_id | History | Output | Visual (graph only) |
| --- | --- | --- | --- | --- |
| `character_flux_front_ref.json` (Kontext) | `066fa35b-57b1-44bc-a026-fdd6666ac739` | completed, `error: null` | `artifacts/.../kontext-smoke/outputs/flux_kontext_front_ref_00001_.png` | wiring PASS (geometry kept, one figure) |
| `character_flux_back_from_front.json` (Kontext) | `f52cc805-ea1a-42b2-95f0-de59edb68249` | completed, `error: null` | `.../flux_kontext_back_from_front_00001_.png` | wiring PASS; rear-vs-front of a faceless block is inconclusive |
| `character_qwen_front_t2i.json` | `6190fba4-f546-4514-ae7b-eb04466f095c` | completed, `error: null` | `artifacts/.../final/smoke-outputs/qwen2512_front_t2i_00001_.png` | Front criteria PASS |
| `character_qwen_front_ref.json` | `407e46a4-bde6-43b9-9931-ed51471d7502` | completed, `error: null` | `.../qwen2512_front_i2i_00001_.png` | **FAIL** — collage / extra figurines / inset |
| `character_flux_front_t2i.json` | `6d1f1070-6c76-4ae2-8a9a-9b47cb80d99b` | completed, `error: null` | `.../flux_front_t2i_00001_.png` | **FAIL** — two people + extra limb |
| `character_sdxl_front_t2i.json` | `9125ac67-4f7f-4de2-8119-f30985096ceb` | completed, `error: null` | `.../illustrious_xl_front_t2i_00001_.png` | **FAIL** — tiny unusable silhouette |
| `character_zimage_front_t2i.json` | `aef8fce5-3ac1-4e89-9f79-bf350a97ac12` | completed, `error: null` | `.../zimage_front_t2i_00001_.png` | Front criteria PASS |
| `character_zimage_front_ref.json` | `bf683630-b32b-4927-953c-16b687969cb0` | completed, `error: null` | `.../zimage_front_i2i_00001_.png` | one figure, no collage; starting-latent preserve of the dummy |

All ten exported JSONs: MCP `validate_workflow` `valid: true`, 0 errors, 0 warnings, `unknown_nodes: []`, `object_info_source` `127.0.0.1:8188`.

Evidence file: `docs/release-gate/character-creator/workflows/final/mcp_final_validate_and_smoke.json`  
Smoke PNGs: `artifacts/character-creator/workflows/final/smoke-outputs/`  
Total sequential smoke wall time: **677701 ms** (~11.3 min).

---

## 6. Character Creator route proof

Trace:

```text
Character Creator
→ selected generator / AUTO
→ cc_v2.generate_view
→ resolve_v2_generation (T2I vs I2I lists)
→ force_workflow_key
→ _enqueue_txt2img(sheet_layout=cc_v2, 2048²)
→ build_leaf_graph(execute key)
→ Comfy /prompt
```

Live inventory 2026-08-24 against cert project `2bc632b8-b329-4d3b-bc40-b68dc41b6bb1`:

| Character | hasReference | AUTO Front chooses | Illustrious Front | FLUX Front key |
| --- | --- | --- | --- | --- |
| Mira Vale `cf4437c7-…` | true | `flux` | Unavailable — no reference generation | `flux.img2img` |
| Mira Vale Open `9cc4c839-…` | false | `flux` | Available `illustrious.txt2img` | `flux.txt2img` |

No silent family swap. Back / Close-up refuse T2I at inventory + resolve + HTTP 409. AUTO uses `AUTO_T2I_PRIORITY` when no reference and `AUTO_I2I_PRIORITY` when a reference or Back/Close-up is required.

**Hidden-workflow gap:** Character Creator FLUX I2I still submits `build_flux_img2img_workflow`, not the accepted Kontext JSON in `final/character_flux_front_ref.json`. Qwen / Z-Image / Illustrious T2I submit the same builder topology as the exported JSONs.

Frontend this pass: Create Front / Back / Close-up is disabled when the selected generator’s operation for that view is unavailable (Illustrious + reference no longer stays clickable). Dropdown already disabled unavailable families. Creator copy stays Available / Unavailable.

---

## 7. Rebuilt / repaired workflows

| Change | Why |
| --- | --- |
| Exported `character_flux_front_t2i.json` with empty negative + cfg 1.0 | Prompt-clean the T2I graph for owner review. Live builder still concatenates. |
| Copied owner Kontext candidates to `character_flux_front_ref.json` / `character_flux_back_from_front.json` | Accepted graphs after MCP + GPU smoke. **Not wired.** |
| Kept production conventional FLUX I2I under `final/production-wired/` | Honest record of what Character Creator still submits. |
| No Illustrious I2I / Back / Close-up files | Unsupported. Inventing them would be a workaround. |
| No Close-up-only JSON | Close-up is the Back graph + prompt. |

No frontend workaround, no backend alias, no silent model swap, no fake readiness.

---

## 8. Root-cause log (no workarounds)

| Defect | Source | Repair taken | Not done (correctly deferred) |
| --- | --- | --- | --- |
| Production FLUX I2I is conventional VAEEncode + denoise 0.35 | `build_flux_img2img_workflow` used by shared `flux.img2img` | Accepted Kontext graphs exported and MCP-smoked | New CC-only key + builder. Shared `flux.img2img` left intact. |
| FLUX negatives dumped into positive CLIP | `_flux_positive_negative_nodes` | Cleaned T2I export only | Shared builder change would hit Scene Creator / Image Generator |
| Qwen negatives also appear inside the positive 13-block package | `compile_character_image_prompt` block `negative_constraints` | Documented | Prompt retune deferred until graphs are owner-reviewed |
| Qwen / Z-Image job denoise 0.35 ignored | Family builders hardcode 1.0 / 0.72 | Documented execute truth | Not remapped at `queue_prompt` |
| Profile-positive traits in every negative | `DEFAULT_NEGATIVE_PROMPT` + always-on Korri rejects in `build_negative_constraints` | Composition-only default; Korri sibling rejects only when `is_korri`; strip locked-trait conflicts | 13-block still embeds negatives in the positive package |
| Z-Image Omni `image1` existed but was unbound | `build_zimage_ref_workflow` omitted image1 after an EmptyLatent shape crash | Bind scaled pixels to Omni `image1` + `vae`, `auto_resize_images=false`, keep matching VAEEncode | CLIP vision encoder still unbound; live smoke of the repaired graph pending |
| Illustrious has no identity I2I | No CC workflow + `refKey=None` | Inventory already Unavailable | Do not invent IPAdapter/ControlNet for CC |
| Create button stayed clickable on an unavailable generator | `CharacterV2Studio` only gated Back on Front lock | Button now also requires `viewOpAvailable` | No family auto-swap |

---

## 9. AUTO vs validated map

AUTO already consults per-operation availability, not generic model presence:

| Situation | AUTO list | Live choose (this machine) |
| --- | --- | --- |
| No reference Front | Certified `FRONT_T2I` in `AUTO_T2I_PRIORITY` | `flux` → `flux.txt2img` |
| Reference Front | Certified `FRONT_REFERENCE_I2I` in `AUTO_I2I_PRIORITY` | `flux` → `flux.img2img` (production conventional) |
| Back / Close-up | Certified `BACK_FROM_FRONT` | `flux` → `flux.img2img` |

AUTO will keep choosing production FLUX I2I until the isolated Kontext key is wired and advertised. That is truthful to the current registry, not to the accepted Kontext graph.

---

## 10. Binary gates

| Gate | Verdict |
| --- | --- |
| 1 — Comfy MCP cross-check complete | **GO.** MCP stdio targeted `:8188`. All 10 final JSONs `valid: true`. Six remaining selectable graphs smoked; two Kontext graphs already smoked. |
| 2 — Qwen workflows verified | **GO as verification.** Operations remain **TESTING**. T2I visual PASS. Ref graph is real Qwen-edit bind. This-pass geometric-dummy ref visual FAIL (collage). Prior Mira CC route exists. Not CERTIFIED. |
| 3 — FLUX workflows verified | **GO as verification.** Accepted Kontext Front/Back MCP+smoke PASS. Prompt-cleaned T2I smoked but visual FAIL (two people). Production I2I remains conventional **TESTING**. Not wired. Not CERTIFIED. |
| 4 — SDXL / Illustrious capabilities verified | **GO as verification.** Front T2I graph MCP-valid and smoked; visual FAIL (unusable silhouette). Front ref / Back / Close-up **UNSUPPORTED**. |
| 5 — Z-Image workflows verified | **GO as verification.** T2I visual PASS. Ref is starting-latent I2I and smoked. Operations **TESTING**. |
| 6 — Capability routing certified | **TESTING / not CERTIFIED.** Dual-mode routing and AUTO lists match the map. AUTO still selects production `flux.img2img` instead of the accepted Kontext graph. Generate button now refuses an unavailable operation. |

Overall product language:

```text
NO-GO — FULL-STACK E2E NOT VERIFIED
```

No Character Creator operation is CERTIFIED in this pass.

---

## 11. Owner review files

- Map: `docs/release-gate/character-creator/CHARACTER_CREATOR_COMFY_WORKFLOW_MAP.md`
- Final JSONs: `docs/release-gate/character-creator/workflows/final/`
- Production-wired FLUX (currently submitted): `docs/release-gate/character-creator/workflows/final/production-wired/`
- Kontext candidate inspection: `docs/release-gate/character-creator/workflows/candidates/FLUX_KONTEXT_CANDIDATE_MCP_INSPECTION.md`
- Earlier builder export (pre-rename): `docs/release-gate/character-creator/CHARACTER_CREATOR_WORKFLOW_MAPPING.md`

Do not continue broad prompt tuning until these artifacts have been reviewed.
