# Multiview Engine License Audit — Character Creator V3

**Date:** 2026-08-24 (updated same day for MV-Adapter I2MV Gate 0)  
**Gate:** License ledger. Hard stop before any new weight download unless a later ACCEPT names the exact set.  
**Wonder3D weights downloaded:** No (`flamehaze1115/wonder3d-v1.0` remains excluded)  
**MV-Adapter / SDXL / I2MV weights downloaded:** No

Repo license is never treated as weights license. Ambiguous = REJECT.

**Current Character Angles license candidate:** MV-Adapter I2MV-SDXL.  
Governing Gate 0 paper: [`MV_ADAPTER_LICENSE_AUDIT.md`](./MV_ADAPTER_LICENSE_AUDIT.md).

Qwen Image Edit 2509 remains license-clear as a **general image/edit** model. It is **not** the official Character Angles engine.

---

## Verdict

```text
ACCEPT — MV-Adapter I2MV-SDXL 2D-only required chain
under RAIL++-allowed owner policy
see MV_ADAPTER_LICENSE_AUDIT.md
```

Wonder3D remains `Rejected for production use due to weight licensing`.

Historical same-day row (superseded as the *official angles* selection, not as a Qwen license revoke):

```text
HISTORICAL — Qwen/Qwen-Image-Edit-2509 Apache-2.0 ACCEPT as a named adapter
PRODUCT — demoted; must not be the official Character Angles engine
```

---

## Candidates

| Engine | Code | Weights | Base / adapters | Commercial | Decision |
| --- | --- | --- | --- | --- | --- |
| Wonder3D `xxlong0/Wonder3D` + `flamehaze1115/wonder3d-v1.0` | MIT | **AGPL-3.0** | same checkpoint | No | **REJECT** |
| Era3D `pengHTYX/Era3D` | AGPL-adjacent | treat as AGPL unless proven otherwise | same family | No | **REJECT** |
| Hunyuan3D-2.x | Tencent Hunyuan 3D Community License | same + MAU clause | Tencent community | Conditional / not Apache-MIT-BSD | **REJECT** |
| TRELLIS / TRELLIS.2 | MIT (core) | MIT (HF `microsoft/TRELLIS.2-4B`) | nvdiffrast / FlexiCubes / Inria renderer **non-commercial** | Not a turnkey commercial pipeline | **REJECT** as shipped pipeline |
| **MV-Adapter I2MV-SDXL** | Apache-2.0 (`huanngzh/MV-Adapter` `4277e001`) | Apache `mvadapter_i2mv_sdxl.safetensors` | **SDXL CreativeML Open RAIL++-M** + MIT fp16 VAE | RAIL++ commercial with use-restriction redistribution | **ACCEPT** for 2D I2MV only — see Gate 0 conditions (no nvdiffrast) |
| InstantMesh `TencentARC/InstantMesh` | Apache-2.0 | HF card Apache-2.0 | customized Zero123++ / FlexiCubes lineage not independently cleared here | Ambiguous derivative stack | **REJECT** (ambiguous) |
| Qwen Image Edit 2509 `Qwen/Qwen-Image-Edit-2509` | Apache-2.0 (`QwenLM/Qwen-Image`) | Apache-2.0 | Official Alibaba edit weights | Yes | **ACCEPT** as general edit model — **not** official Character Angles |
| Lightning LoRA `lightx2v/Qwen-Image-Lightning` | Apache-2.0 | Apache-2.0 | Optional 8-step LoRA; not loaded by the current official 2509 graph | Yes (optional) | **ACCEPT optional** |
| `dx8152/Qwen-Edit-2509-Multiple-angles` | card Apache-2.0 | community ModelScope LoRA | Official Qwen base | Provenance not official | **DEFER** |
| CharacterGen 2D | Apache-2.0 repo/card | Apache 2D bins | Required `stabilityai/stable-diffusion-2-1` RAIL++ | Not selected | **DEFER** — not the I2MV trial |
| MetaView | No SPDX on GitHub | Kolors ckpt + Qwen-Image-Edit | Required DA3 Giant/Nested **CC BY-NC 4.0** | No | **REJECT** |

### Evidence URLs

- Wonder3D weights: https://huggingface.co/flamehaze1115/wonder3d-v1.0 (AGPL-3.0)
- Qwen Image code: https://github.com/QwenLM/Qwen-Image (Apache-2.0)
- Qwen Image Edit 2509: https://huggingface.co/Qwen/Qwen-Image-Edit-2509 (Apache-2.0)
- Adept in-repo declaration: `studio-api/app/workflows/qwen_image_edit_2509.py` `QWEN_EDIT_2509_LICENSE = "Apache-2.0"`
- Lightning: https://huggingface.co/lightx2v/Qwen-Image-Lightning and https://github.com/ModelTC/Qwen-Image-Lightning (Apache-2.0)

---

## Production selection (license candidate only)

**Engine id (intended):** `mv_adapter` / I2MV-SDXL  
**Role:** Character Angles only (Side / 3/4 / Back) from approved Front pixels.  
**Not:** Front generator dropdown. **Not:** `generate_view("back")`. **Not:** Krea. **Not:** Qwen as official angles.  
**Not yet:** wired in code. `PRODUCTION_ENGINE` may still say `qwen_image_edit_2509` until integration. License ACCEPT is not a runtime flip.

This remains an explicit named adapter, not a silent Front-family fallback.

---

## Hard rules preserved

- Do not download Wonder3D weights.
- Do not enable Wonder3D Setup as Ready.
- Do not download MV-Adapter / SDXL until the isolated-install gate, and then only the 2D I2MV set named in [`MV_ADAPTER_LICENSE_AUDIT.md`](./MV_ADAPTER_LICENSE_AUDIT.md). Store on the **internal** Adept tree `C:\AdeptFilmWorks\AIVideoStudio\data\models\`, not `D:\01_Models`.
- Do not install `nvdiffrast` or the official wholesale `requirements.txt`.
- If this engine later fails identity/GPU gates: disable Character Angles and report `NO-GO — CHARACTER CREATOR V3 MULTIVIEW ENGINE NOT CERTIFIED`. Do not fall back to Qwen as the official engine.
