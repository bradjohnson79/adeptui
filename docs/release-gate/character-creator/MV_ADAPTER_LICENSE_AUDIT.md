# MV-Adapter I2MV License Audit — Character Creator V3 Gate 0

**Date:** 2026-08-24  
**Gate:** License audit only. **No weights downloaded. No environment created.**  
**Governing for this gate:** this document  
**Related ledger:** [`MULTIVIEW_ENGINE_LICENSE_AUDIT.md`](./MULTIVIEW_ENGINE_LICENSE_AUDIT.md)

Repo license is never treated as the runtime stack license. Ambiguous = REJECT.  
Apache adapter + RAIL++ base is **not** “Apache all the way down.”

Owner policy for this trial (2026-08-24):

- Required **CreativeML Open RAIL++-M** bases are allowed.
- AGPL, CC-BY-NC, research-only, unclear, and missing provenance remain STOP.
- Wonder3D stays blocked. Do not download `flamehaze1115/wonder3d-v1.0`.
- Qwen Image Edit 2509 is **not** the official Character Angles engine. No silent Qwen fallback.
- Scope is **2D I2MV only**. No texture, mesh, or 3D reconstruction stage.

---

## Verdict

```text
ACCEPT — MV-Adapter I2MV-SDXL 2D-only required inference chain
under RAIL++-allowed owner policy
```

This ACCEPT unlocks a later isolated official download of the **2D I2MV required set only**.  
It does **not** certify quality, GPU, identity, Back, sheet, JSON, Playwright, or production GO.

```text
NOT CERTIFIED — runtime / quality / Gates 6–8 still closed
```

---

## Conditions (hard)

These are part of the ACCEPT. Violating any one reopens Gate 0 as REJECT.

1. **Do not** `pip install -r requirements.txt` from the official repo. That file pulls `nvdiffrast`, which is **non-commercial**.
2. **Do not** install, import, or vendor `nvdiffrast`, CV-CUDA, Open3D, PyMeshLab, or any texture/3D path.
3. Official I2MV script imports `get_orthogonal_camera` via `mvadapter.utils.mesh_utils`, whose `__init__.py` also imports `render.py` (`import nvdiffrast.torch`). Adept must import cameras from [`mvadapter/utils/mesh_utils/camera.py`](https://github.com/huanngzh/MV-Adapter/blob/main/mvadapter/utils/mesh_utils/camera.py) only. That file does not use nvdiffrast.
4. Download official sources only. No Google Drive mirrors, community SDXL, DreamShaper, Animagine, LCM-SDXL, or unofficial adapter conversions.
5. Canonical storage later is the **internal** Adept models tree (same drive as AIVideoStudio), not `D:\01_Models`:
   `C:\AdeptFilmWorks\AIVideoStudio\data\models\MV-Adapter\`
   Isolated venv: `C:\AdeptFilmWorks\AIVideoStudio\data\venvs\mvadapter`.
   Never Comfy / Studio API / Adept Bots / MCP venvs. Never the external `D:` model root.
6. Optional rembg, if used, is official `ZhengPeng7/BiRefNet` (MIT) only. Prefer Adept clean Front and leave rembg **off** for first cert unless needed.
7. Do not download `3D`, geometry-to-multiview, or image-to-texture adapters for this milestone.

---

## Official sources audited

| Role | Source | Version pinned here | License label |
| --- | --- | --- | --- |
| Code | https://github.com/huanngzh/MV-Adapter | `4277e0018232bac82bb2c103caf0893cedb711be` (main, 2025-06-26) | Apache-2.0 (`LICENSE`) |
| Adapter weights | https://huggingface.co/huanngzh/mv-adapter | HF SHA `6de4033df6b53366f3c009d22f5ec434bb55e59f` | `license: apache-2.0` |
| I2MV-SDXL adapter file | `mvadapter_i2mv_sdxl.safetensors` | same HF repo | Apache-2.0 (repo card) |
| Required base | https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0 | HF SHA `462165984030d82259a11f4367a4eed129e94a7b` | CreativeML Open RAIL++-M (`openrail++`) |
| Official default VAE | https://huggingface.co/madebyollin/sdxl-vae-fp16-fix | HF SHA `207b116dae70ace3637169f1ddd2434b91b3a8cd` | MIT |
| Paper | https://arxiv.org/abs/2412.03632 | ICCV 2025 | n/a |

HF model-card row for I2MV-SDXL once incorrectly linked `mvadapter_t2mv_sdxl.safetensors`. **GitHub README is authoritative:** `mvadapter_i2mv_sdxl.safetensors`.

---

## Required 2D I2MV inference artifacts

Official script: [`scripts/inference_i2mv_sdxl.py`](https://github.com/huanngzh/MV-Adapter/blob/main/scripts/inference_i2mv_sdxl.py)  
Defaults: `--base_model stabilityai/stable-diffusion-xl-base-1.0`, `--vae_model madebyollin/sdxl-vae-fp16-fix`, `--adapter_path huanngzh/mv-adapter`, 768×768, 6 views, azimuth `{0, 45, 90, 180, 270, 315}`.

| Artifact | Source | Version | License | Commercial use | Redistribution | Required? | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MV-Adapter inference code (pipeline, I2MV script, camera math) | `huanngzh/MV-Adapter` | `4277e001` | Apache-2.0 | Yes | Apache notice | **Required** | ACCEPT |
| I2MV-SDXL adapter tensors | `huanngzh/mv-adapter` `mvadapter_i2mv_sdxl.safetensors` | HF `6de4033` | Apache-2.0 | Yes | Apache notice | **Required** | ACCEPT |
| SDXL UNet + default VAE + tokenizers + scheduler config | `stabilityai/stable-diffusion-xl-base-1.0` | HF `4621659` | **CreativeML Open RAIL++-M** (2023-07-26) | Yes, with Attachment A use restrictions | Must pass RAIL++ copy + use restrictions to downstream users of the **weights** | **Required** | ACCEPT under owner policy |
| CLIP-ViT/L text encoder | Bundled in SDXL `text_encoder/` | same SDXL repo | Distributed under SDXL RAIL++; upstream OpenAI CLIP code MIT | Yes (RAIL++ restrictions apply to the bundled SDXL copy) | Same as SDXL if redistributed from that repo | **Required** (loaded by SDXL pipeline) | ACCEPT |
| OpenCLIP-ViT/G text encoder | Bundled in SDXL `text_encoder_2/` | same SDXL repo | Distributed under SDXL RAIL++; OpenCLIP project MIT-class | Yes (RAIL++ on bundled copy) | Same as SDXL | **Required** | ACCEPT |
| Official fp16 VAE fix | `madebyollin/sdxl-vae-fp16-fix` safetensors | HF `207b116` | MIT | Yes | MIT notice | **Required for official I2MV-SDXL path** (script default) | ACCEPT — prefer `diffusion_pytorch_model.safetensors` / `sdxl_vae.safetensors`, not `.bin` |
| In-repo ShiftSNR scheduler wrapper | `mvadapter/schedulers/scheduling_shift_snr.py` | code SHA above | Apache-2.0 | Yes | Apache | **Required** | ACCEPT |
| Diffusers / Transformers / Accelerate / PEFT / safetensors / Pillow | PyPI, isolated venv | pin at install time | Apache/BSD-class library licenses | Yes | standard | **Required libraries** | ACCEPT (pin later; do not contaminate Comfy) |

RAIL++ is **not** non-commercial. It allows commercial use and hosted use. It forbids Attachment A misuses (minors, illegal harm, PII-for-harm, discrimination, medical advice, justice/immigration profiling, etc.). If Adept later redistributes SDXL weights, those restrictions must remain enforceable for recipients. Generated Character Angles images are Output; licensor claims no rights in Output, and Adept remains accountable for use.

---

## Optional / not required for first I2MV cert

| Artifact | Source | License | Required? | Decision |
| --- | --- | --- | --- | --- |
| BiRefNet rembg | `ZhengPeng7/BiRefNet` + GitHub `ZhengPeng7/BiRefNet` | MIT (HF card `license: mit`, GitHub MIT) | Optional. CLI `--remove_bg`; Gradio defaults **on** | ACCEPT optional. Prefer off if Adept Front is already a clean single character. `trust_remote_code=True` is an execution risk; vendor/review before enabling. |
| I2MV-SD21 + `stabilityai/stable-diffusion-2-1` | official alt path | Apache adapter + RAIL++ SD 2.1 | Not chosen | DEFER. Do not download. |
| LCM-SDXL | `latent-consistency/lcm-sdxl` | separate | Optional speed path | REJECT for cert (not official I2MV quality path) |
| DreamShaper XL / Animagine XL / community SDXL | various | mixed / unclear | Demo-only | REJECT for cert |
| Geometry adapters `mvadapter_ig2mv_*` / `tg2mv_*` | same HF repo | Apache adapters + RD geometry | 3D/texture | DO NOT DOWNLOAD |
| Texture stack: CV-CUDA, Open3D, PyMeshLab, Spandrel | official requirements “texturing” block | mixed | 3D only | DO NOT INSTALL |
| Training extras: pytorch-lightning, Objaverse datasets | official | n/a | Training | DO NOT DOWNLOAD |
| ComfyUI custom node | community | n/a | Not required | Do not force a fake Comfy wrapper |

---

## Forbidden if pulled into the I2MV runtime

| Artifact | Source | License | Why it is here | Decision |
| --- | --- | --- | --- | --- |
| **nvdiffrast** | `git+https://github.com/NVlabs/nvdiffrast.git` in official `requirements.txt`; `mvadapter/utils/mesh_utils/render.py` imports it | NVIDIA Source Code License (1-Way Commercial): **non-commercial / research-eval only** for users | Texture/mesh render. Official I2MV **script import** pulls it via `mesh_utils/__init__.py` | **REJECT as a dependency.** Do not install. Bypass package `__init__`. Same class of failure that blocked TRELLIS as a shipped pipeline. |
| Wonder3D weights | `flamehaze1115/wonder3d-v1.0` | AGPL-3.0 | Historical candidate | **REJECT.** Never download. |
| Zero123++ weights | `sudo-ai/zero123plus-*` | CC-BY-NC 4.0 | InstantMesh / Unique3D lineage | **REJECT.** Not part of I2MV. |

`camera.py` computes orthogonal cameras with torch only. I2MV uses those cameras plus `get_plucker_embeds_from_cameras_ortho` in `geometry.py` (also no nvdiffrast). The non-commercial package is **not required to generate 2D views** if Adept does not import `mesh_utils/__init__.py` or `render.py`.

---

## Safetensors

| File | Serialization | Call |
| --- | --- | --- |
| `mvadapter_i2mv_sdxl.safetensors` | safetensors | Required. Official. |
| SDXL UNet / text encoders | official `.safetensors` (+ fp16 variants) | Prefer safetensors. |
| `madebyollin/sdxl-vae-fp16-fix` | safetensors and a `.bin` sibling | Prefer safetensors. Do not load the pickle `.bin` when the official safe file exists. |

---

## Intended Adept mapping (license-neutral; quality later)

Official I2MV cameras (elevation 0°):

| Azimuth | Role | Adept slot |
| --- | --- | --- |
| 0° | Generated front | Discard. Keep approved Front. |
| 45° | Front-right three-quarter | **3/4** |
| 90° | Right profile | **Side** |
| 180° | Rear | **Back** |
| 270° | Left profile | Extra; do not overwrite Side unless remaking |
| 315° | Front-left three-quarter | Extra |

Mapping is from published azimuths, not an LLM guess.

---

## Allowed later download set (only after this paper ACCEPT)

Official, 2D I2MV only. **Internal Adept models root only** (AIVideoStudio `data\models`, Setup-visible). Do not write `D:\01_Models` or Downloads.

| Artifact | Internal destination |
| --- | --- |
| Adapter | `C:\AdeptFilmWorks\AIVideoStudio\data\models\MV-Adapter\mvadapter_i2mv_sdxl.safetensors` |
| SDXL base pipeline | `C:\AdeptFilmWorks\AIVideoStudio\data\models\MV-Adapter\stable-diffusion-xl-base-1.0\` |
| fp16 VAE | `C:\AdeptFilmWorks\AIVideoStudio\data\models\MV-Adapter\sdxl-vae-fp16-fix\` |
| Code checkout (optional, no weights) | `C:\AdeptFilmWorks\AIVideoStudio\data\runtimes\mv-adapter\` |
| Isolated venv | `C:\AdeptFilmWorks\AIVideoStudio\data\venvs\mvadapter` |

1. Git clone or sparse checkout of `huanngzh/MV-Adapter` at `4277e001` (code) into `data\runtimes\mv-adapter\`.
2. `huggingface-cli download huanngzh/mv-adapter --include mvadapter_i2mv_sdxl.safetensors --local-dir data\models\MV-Adapter`
3. `huggingface-cli download stabilityai/stable-diffusion-xl-base-1.0 --local-dir data\models\MV-Adapter\stable-diffusion-xl-base-1.0`
4. `huggingface-cli download madebyollin/sdxl-vae-fp16-fix --include *.safetensors --local-dir data\models\MV-Adapter\sdxl-vae-fp16-fix`

**Do not download in this Gate 0 turn.** Isolated venv and internal `data\models\MV-Adapter\` happen in the next gate.

Optional later: `ZhengPeng7/BiRefNet` only if rembg is enabled after a written need.

---

## What this gate does not decide

- Photoreal identity, wardrobe, or Back quality
- Whether Objaverse-trained I2MV is CRS-usable on people
- RTX 5090 runtime, VRAM, cancel, reject/approve, sheet, JSON, Playwright
- Production engine flip in code (`PRODUCTION_ENGINE` may still say Qwen until integration)

If later install accidentally adds nvdiffrast, or if any required extra is NC/AGPL/unclear, **stop and reopen this audit as REJECT**.
