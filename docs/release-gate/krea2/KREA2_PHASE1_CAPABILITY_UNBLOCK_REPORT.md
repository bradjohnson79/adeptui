# Krea 2 Phase 1 — Capability Unblock Report

**Verdict: PASS — KREA 2 CAPABILITY UNBLOCKED AND RUNTIME VERIFIED**

Date: 2026-08-16  
Branch: `beta`  
HEAD: `3980b6051269514b5b3c38eb066c005a1a5fe850`  
Scope: Phase 1 only — model capability readiness + one local Turbo GPU smoke.  
Not in scope: Qwen/ERS Phase 2, Draft→Certified promotion, commit/push/deploy, Vercel.

**Boundary:** `models.image.krea2.ready` is **Ready**. Product workflows `krea2.turbo_txt2img` and `krea2.raw_txt2img` remain **Draft**. Model capability ready ≠ product workflow certified.

---

## 1. Initial state (Phase 1A)

| Item | Value |
| --- | --- |
| Branch / HEAD | `beta` / `3980b6051269514b5b3c38eb066c005a1a5fe850` |
| Concurrent dirty tree | Large (Scene Creator, avatar, fal_catalog, timeline, etc.). Left untouched except the Krea-path `image_product` cfg/steps pass-through below. |
| Probe chain | `_eval_models_image_krea2` → `krea2_models` → `_verify_krea2_files` |
| Root | `settings.krea2_model_root` = `D:\01_Models\krea2` |
| Comfy | 0.32.0 at `http://127.0.0.1:8188` — loaders `comfy/ldm/krea2/model.py`, `comfy/text_encoders/krea2.py`, `CLIPLoader` type `krea2` |
| Detection keys | UNET: `txtfusion.projector.weight`, `first.weight`, `blocks.0.attn.wq.weight`. CLIP: `model.` Qwen3-VL prefix |
| D: free space | ~3.33 TB (catalog budget 40 GB) |
| **Before readiness** | `krea2_models` `present=false` / `optional_models_missing`; `models.image.krea2.ready` **blocked** `MODEL_MISSING` |

Already on disk (kept intact):

- `turbo.safetensors` (26,283,332,608) — Comfy-native Turbo
- Diffusers `transformer/` shards — **not** used as RAW
- `text_encoder\model.safetensors` — **not** used as CLIP (no `model.` contract)
- `vae\diffusion_pytorch_model.safetensors` — Diffusers AutoencoderKL, **not** aliased to Qwen Image VAE

---

## 2. Artifact gate (Phase 1B)

Source: [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2) (`gated: false`, license `krea-2-community-license`, repo SHA observed `952f49d49653cb42e7d6cf7cbfad74738073ec7d`).

Tensor-layout proof was made against the installed loader **before** download. Filenames alone were not treated as proof.

| Role | File | Size | SHA256 | Loader keys proven |
| --- | --- | --- | --- | --- |
| RAW | `diffusion_models/krea2_raw_fp8_scaled.safetensors` | 13,141,730,784 | `48cd5d6c100297968349b41a8e77c6591d1dac18a215807f5f25f59e5c54cd61` | `txtfusion.projector.weight`, `first.weight`, `blocks.0.attn.wq.weight` |
| Encoder | `text_encoders/qwen3vl_4b_fp8_scaled.safetensors` | 5,242,467,968 | `54bd5144df0bbc25dd6ccadfcb826b521445a1b06ae5a42570bdd2974ca87094` | `model.visual.deepstack_merger_list.0.norm.weight`, `model.visual.merger.linear_fc2.weight` |
| VAE | `vae/qwen_image_vae.safetensors` | 253,806,246 | `a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f` | WanVAE/`decoder.head.0.gamma` (VAELoader Qwen Image path) |

Rejected as candidates: Diffusers `transformer/` shards, `text_encoder\model.safetensors`, aliasing the existing Diffusers VAE.

---

## 3. Install (Phase 1C–E)

Destinations under `D:\01_Models\krea2` (Turbo + Diffusers tree unchanged):

- RAW → `diffusion_models\krea2_raw_fp8_scaled.safetensors` (SHA verified after download)
- Encoder → `text_encoders\qwen3vl_4b_fp8_scaled.safetensors` (SHA verified)
- VAE → `vae\qwen_image_vae.safetensors` **alongside** original `diffusion_pytorch_model.safetensors` (SHA verified)

`hf download` hit WinError 10054 on the large files; completed with `curl.exe -L -C -` from the same Hugging Face resolve URLs (no third-party mirror).

**Comfy paths:** backed up `%APPDATA%\Comfy Desktop\shared_model_paths.yaml` → `shared_model_paths.yaml.krea2-phase1.bak`, then added:

```yaml
adept_krea2:
  base_path: D:/01_Models/krea2
  checkpoints: .
  diffusion_models: |-
    .
    diffusion_models
  text_encoders: text_encoders
  vae: vae
```

`diffusion_models` is a two-line block so `UNETLoader` sees root `turbo.safetensors` **and** `diffusion_models\krea2_raw_fp8_scaled.safetensors`. Comfy log after restart:

```
Adding extra search path checkpoints D:\01_Models\krea2
Adding extra search path diffusion_models D:\01_Models\krea2
Adding extra search path diffusion_models D:\01_Models\krea2\diffusion_models
Adding extra search path text_encoders D:\01_Models\krea2\text_encoders
Adding extra search path vae D:\01_Models\krea2\vae
```

**Local env** (`config/beta-local.local.env`, gitignored):

```
STUDIO_KREA2_RAW_CHECKPOINT=krea2_raw_fp8_scaled.safetensors
STUDIO_KREA2_TEXT_ENCODER=qwen3vl_4b_fp8_scaled.safetensors
STUDIO_KREA2_VAE=qwen_image_vae.safetensors
STUDIO_KREA2_TURBO_CFG=1.0
```

CFG 1.0 matches the live Comfy template `image_krea2_turbo_t2i` (`KSampler` widgets: 8 steps, **cfg=1**, euler/simple). Official repo `--cfg 0.0` is **not** used for this smoke (Comfy `KSampler` treats 0.0 as the negative branch).

No Comfy-Org filenames were hardcoded into `config.py`.

---

## 4. Comfy restart (Phase 1F)

```
.\Restart-AdeptBetaBackend.ps1 -Service comfyui
```

`GET http://127.0.0.1:8188/system_stats` → **200**.  
Studio API was then restarted so uvicorn picked up `STUDIO_KREA2_*` (50 env vars loaded).  
Device: `cuda:0 NVIDIA GeForce RTX 5090`, pytorch `2.10.0+cu130`, VRAM 32607 MB.

---

## 5. Loader proof (Phase 1G)

`/object_info` after path registration:

| Node | Visible |
| --- | --- |
| UNETLoader | `turbo.safetensors`, `krea2_raw_fp8_scaled.safetensors` |
| CLIPLoader | `qwen3vl_4b_fp8_scaled.safetensors`, type includes `krea2` |
| VAELoader | `qwen_image_vae.safetensors` |

Instantiate (Draft graph nodes, PreviewAny to force load):

- Turbo UNET + CLIP type `krea2` + VAE — Comfy success. Log: VAE on `cuda:0`, MixedPrecisionOps text encoder, `Requested to load Krea2` (`model_type FLUX` is Krea2’s flow `ModelType`, unet class `SingleStreamDiT`).
- RAW UNET `krea2_raw_fp8_scaled.safetensors` — loader-only success; fp8 mixed-precision metadata detected. No second full generation.

---

## 6. Readiness before / after (Phase 1H)

| Probe | Before | After |
| --- | --- | --- |
| `verify_component("krea2_models")` via `GET /api/comfy/health` | `present=false`, `optional_models_missing` | `present=true`, `issueCode=null`, summary: Turbo/RAW + Qwen3-VL + Qwen Image VAE readable |
| `POST /api/capabilities/refresh` → `models.image.krea2.ready` | blocked `MODEL_MISSING` | `status=locally_verified`, `available=true`, `healthy=true`, `reasonCode=null` |
| `GET /api/health` missing optional | included Krea | `missing_optional_model_component_ids=[]` |

No readiness verifier was patched. Frontend/Vercel not deployed.

---

## 7. Turbo GPU smoke (Phase 1I)

Adept `POST /api/image-product/generate` on existing project **Schnick Coffee** (`2347bf46-3762-4763-86c5-4a6032522278`) — no new project.

| Field | Value |
| --- | --- |
| Job | `85d49654-2fbc-43a2-b258-2713be7221cb` |
| Workflow | `krea2.turbo_txt2img` (Draft harness `allow_draft_cert_harness=true`) |
| Provider | local (no fal/cloud) |
| Prompt | a red ceramic coffee mug on a wooden table, soft studio lighting, photorealistic, 1024px still |
| Size / steps / cfg / seed | 1024×1024 / 8 / **1.0** / **20260816** |
| Comfy prompt | `3ff6f980-5158-49e2-b7ef-385e95dc8b59` |

Live Comfy graph (from `/history`):

- `UNETLoader` `unet_name=turbo.safetensors` `weight_dtype=fp8_e4m3fn`
- `CLIPLoader` `clip_name=qwen3vl_4b_fp8_scaled.safetensors` `type=krea2`
- `VAELoader` `vae_name=qwen_image_vae.safetensors`
- `ModelSamplingAuraFlow` `shift=1.15`
- `KSampler` cfg=1.0, steps=8, euler/simple, seed=20260816

Runtime log (Law 26):

- `Requested to load Krea2TEModel_` — 4999 MB staged, `cuda:0`
- `Requested to load Krea2` — 12224 MB staged, `cuda:0`
- KSampler 8/8 at ~1.79 it/s after first-step init
- `Requested to load WanVAE` — 241 MB staged
- `Prompt executed in 463.13 seconds`
- Peak observed GPU memory during the job ~19 GB / 32607 MB on RTX 5090. GPU util was low during DynamicVRAM init, then sampling completed on CUDA. **No CPU fallback.**

Result:

- Status `done` / stage `Completed`
- Gate: exists, nonzero, **decodable**, 1024×1024 PNG, 1,075,020 bytes
- Checksum `sha256:71eeedaa6c4b92353e70e2495cc48baccb16183cdb89d4455eaca532f98ceec4`
- Asset: `data/projects/2347bf46-3762-4763-86c5-4a6032522278/assets/imagegen_edit_2ce36158.png`  
  (visual: red ceramic mug on dark wood, as prompted)

**Display-only caveat (does not change the Comfy graph):** job `history_json.settings.checkpoint` still records `flux1-kontext-dev.safetensors` from generic `_checkpoint_for_model`. Provenance `runtime=krea2` / `workflow=krea2.turbo_txt2img` and the Comfy `/history` graph above are authoritative. Not patched in this phase.

---

## 8. Tests

From `studio-api`:

```
python -m pytest tests/test_krea2_provider_registration.py tests/test_krea2_workflow_contracts.py tests/test_runtime_diagnostics_refinement.py -q
```

**36 passed, 5 failed, 4 warnings.**

Failures (not used to fake GO; not repaired by promoting Draft→Certified):

1. `test_model_registry_catalog_contains_krea2_entries` — catalog label `Available` vs test expectation `Certified`. Workflows stay Draft.
2. `test_installed_krea2_files_map_to_static_readiness` — provider readiness `draft` vs `ready`. Same Draft boundary.
3. `test_krea2_fingerprints_match_registry` — graphHash drift already present in the concurrent dirty tree (`25ec19…` vs registry `5e7946…`). Live smoke used the registry fingerprint `sha256:5e794607f682813ae37c1ce9ff7176709260919f0910da0f5a4fa2d6cacf3017`.
4. `test_comfy_health_optional_missing_does_not_degrade_runtime` — `krea2_models` is no longer missing because `_verify_krea2_files` sees the real `D:\01_Models\krea2` install.
5. `test_health_endpoint_top_level_missing_lists_exclude_optional` — live optional-missing list is empty now that Krea files are present.

These are Draft-boundary / live-disk effects. They do not reverse the capability or smoke evidence.

---

## 9. Source vs environment integrity

| Change | Location | Git |
| --- | --- | --- |
| Comfy-Org weights | `D:\01_Models\krea2\…` | untracked host models |
| `adept_krea2` extra paths | `%APPDATA%\Comfy Desktop\shared_model_paths.yaml` (backup `.krea2-phase1.bak`) | outside repo |
| `STUDIO_KREA2_*` | `config/beta-local.local.env` | gitignored |
| cfg/steps pass-through so the Draft harness can send cfg=1.0 | `studio-api/app/image_product/service.py` | dirty, **not committed** |

No commit, push, stash, reset, or revert of concurrent work. Registry entries remain Draft.

---

## 10. Draft boundary (Phase 1J)

- `krea2.turbo_txt2img` status **Draft**
- `krea2.raw_txt2img` status **Draft**
- `qwen.multi_reference` / ERS / Qwen Phase 2 **not started**

---

## 11. Rollback (documented, not executed)

This run **passed**. Rollback is unused.

If it were needed:

1. Delete only new files: `diffusion_models\krea2_raw_fp8_scaled.safetensors`, `text_encoders\qwen3vl_4b_fp8_scaled.safetensors`, `vae\qwen_image_vae.safetensors`. Keep Turbo, Diffusers shards, original VAE.
2. Restore `shared_model_paths.yaml` from `shared_model_paths.yaml.krea2-phase1.bak`.
3. Remove `STUDIO_KREA2_*` from `config/beta-local.local.env`.
4. Revert the `cfg`/`steps` pass-through in `service.py` if desired.
5. `.\Restart-AdeptBetaBackend.ps1 -Service comfyui` (and `studio_api` if env changed).

---

## 12. Verdict

**PASS — KREA 2 CAPABILITY UNBLOCKED AND RUNTIME VERIFIED**

Capability `models.image.krea2.ready` is Ready. Comfy loaders instantiate Turbo, RAW, Krea CLIP, and Qwen Image VAE. One local Turbo GPU job produced a decodable 1024×1024 image through the Draft Adept graph on RTX 5090 with no CPU fallback. Product workflows stay Draft.
