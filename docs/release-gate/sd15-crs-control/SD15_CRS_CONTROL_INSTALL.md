# SD 1.5 CRS Control Route — Install Report

Governing document for this installation. Historical reports stay historical.

Do not resume Korri CRS generation from this task.

## Verdict

```text
GO — SD 1.5 INSTALLED + COMFY CRS CONTROL ROUTE AVAILABLE
```

READY FOR PRIMARY REVIEW.

Certification bot live verification only. Independent primary still owns the final product GO.

## Scope / environment

| Item | Measured |
|---|---|
| Requested branch | `feat/codirector-sanitation-phase1` |
| Working tree / API revision | `feat/crs-flux-auto-one-figure` @ `1c86560` (Chief SD15 wiring in the working tree; checkout of sanitation-phase1 was not performed so that wiring stayed loaded) |
| Studio API | `http://127.0.0.1:8758/api/health` **200** (`apiRevision=1c86560`) |
| Beta web | `http://127.0.0.1:8760/` **200** |
| Comfy | `http://127.0.0.1:8188` **200**, nodes **1997**, ComfyUI **0.32.0**, torch **2.10.0+cu130** |
| GPU | `cuda:0 NVIDIA GeForce RTX 5090` — no CPU fallback |
| Project | Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` (reused; no `POST /api/projects`) |
| Subject | Disposable synthetic only. **Korri was not generated.** |

API refresh used Adept-owned `Restart-AdeptBetaBackend.ps1 -Service studio_api` (Comfy was not killed by name). Comfy discovery was restored with Adept-owned `Restart-AdeptBetaBackend.ps1 -Service comfyui` after writing the identity-verified PID. Beta left running.

## Checkpoint installed

| Item | Value |
|---|---|
| Checkpoint | `v1-5-pruned-emaonly.safetensors` |
| Central path | `D:\01_Models\StableDiffusion15\v1-5-pruned-emaonly.safetensors` |
| Source | Hugging Face `stable-diffusion-v1-5/stable-diffusion-v1-5` |
| Bytes | **4,265,146,304** |
| Listed by `CheckpointLoaderSimple` | **yes** |
| Comfy-Shared copy | Absent (central `D:\01_Models` only, via extra paths) |

## ControlNet models installed

| Role | Path | Bytes | Listed by `ControlNetLoader` |
|---|---|---|---|
| OpenPose | `D:\01_Models\ControlNet\SD15\control_v11p_sd15_openpose.safetensors` | 722,601,100 | yes |
| Depth | `D:\01_Models\ControlNet\SD15\control_v11f1p_sd15_depth.safetensors` | 722,601,100 | yes |
| Lineart | `D:\01_Models\ControlNet\SD15\control_v11p_sd15_lineart.safetensors` | 722,601,100 | yes |

No extra ControlNets. Canny not installed.

## Preprocessors / nodes

| Node | Observed |
|---|---|
| `CheckpointLoaderSimple` | Present; lists `v1-5-pruned-emaonly.safetensors` |
| `ControlNetLoader` / `ControlNetApplyAdvanced` | Present; lists the three SD15 ControlNets |
| `OpenposePreprocessor` | **true** (used for the live pose smoke; `.to(cuda)`) |
| `DWPreprocessor` | **true** |
| `LineArtPreprocessor` | Present |

Custom node path:

`C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\custom_nodes\comfyui_controlnet_aux`

OpenPose annotators downloaded once via Comfy venv `huggingface_hub` after the first `/prompt` failed mid-download (`Cannot send a request, as the client has been closed`):

| File | Bytes |
|---|---|
| `ckpts/lllyasviel/Annotators/body_pose_model.pth` | 209,267,595 |
| `ckpts/lllyasviel/Annotators/hand_pose_model.pth` | 147,341,049 |
| `ckpts/lllyasviel/Annotators/facenet.pth` | 153,718,792 |

Limitation: DWPose onnxruntime is missing, so **DWPose** would use OpenCV CPU. This smoke used **OpenposePreprocessor**, which ran on CUDA.

## Extra model paths

Backup: `%APPDATA%\Comfy Desktop\shared_model_paths.yaml.sd15-crs.bak`

Present (Krea pattern; `adept_krea2` untouched):

```yaml
adept_sd15:
  base_path: D:/01_Models/StableDiffusion15
  checkpoints: .

adept_sd15_controlnet:
  base_path: D:/01_Models/ControlNet/SD15
  controlnet: .
```

`STUDIO_COMFY_MODELS_DIR` was not set to `D:\01_Models`.

## Workflow file / registry

| Key | Status | Builder |
|---|---|---|
| `sd15.txt2img` | Draft | `app.imagegen_workflows:build_txt2img_workflow` |
| `crs.sd15.control` | Draft | `app.imagegen_workflows:build_sd15_control_workflow` |
| `control.pose` / `control.depth` / `control.lineart` | Deferred (unchanged) | none |

Workflow JSON: [`config/image-workflows/graphs/crs.sd15.control.json`](../../../config/image-workflows/graphs/crs.sd15.control.json) (2,035 bytes).

Semantics for Adept invoke: `task=CRS_SINGLE_VIEW`, `view=FRONT`, `character_count=1`, `extras=false`, `layout=single_subject`. One image. Not a four-panel sheet.

`GET /api/image-runtime/registry` contains both Draft keys. `productionReadyKeys` still includes `qwen2512.txt2img`, `qwen2512.ref`, `flux.txt2img`, `flux.img2img`, `illustrious.txt2img`. SD15 is **not** production-ready / Certified.

## Co-Director capability

Live `GET /api/image-runtime/capabilities` → `sd15Crs`:

```json
{
  "provider": "sd15",
  "available": true,
  "preferred": false,
  "autoPreferred": false,
  "roles": [
    "pose_control",
    "depth_control",
    "lineart_control",
    "regional_repair",
    "crs_single_view"
  ],
  "workflowKeys": ["sd15.txt2img", "crs.sd15.control"]
}
```

Not AUTO-preferred. Not in the Certified Character Creator beauty dropdown (`GET /api/imagegen/models`: qwen2512 / zimage / illustrious / flux = Certified; krea2 = Draft; **no sd15 Certified beauty**).

## Unit tests

`studio-api/tests/test_sd15_crs_control.py`: **14 passed**.

## Live smokes (measured)

| Test | Result |
|---|---|
| Path verification | **PASS** — checkpoint 4,265,146,304 bytes; three ControlNets 722,601,100 each |
| Comfy checkpoint load | **PASS** — `CheckpointLoaderSimple` lists `v1-5-pruned-emaonly.safetensors` after Adept-owned Comfy restart (nodes 1933 → **1997**) |
| txt2img smoke 512×768 | **PASS** — prompt `1116a585-5a7b-4a90-8680-3321f31b8b5c`; `adept_sd15_txt2img_smoke_00001_.png`; **512×768**; 566,980 bytes; Comfy execution **56.825 s**; one isolated mannequin, not a sheet |
| OpenPose/ControlNet smoke | **PASS** — human disposable source; prompt `f7deb86c-4410-44c5-be2a-071c22a6d44c`; `people=1` (body + face + hands); pose map saved; output `adept_sd15_openpose_smoke_00002_.png` **512×768** 490,968 bytes; **4.169 s** warm; nvidia-smi peak **5532 MiB / 59% util** on RTX 5090; pose transferred (source left hand in pocket → result left hand in pocket, different clothes) |
| Workflow JSON load | **PASS** — `crs.sd15.control.json` present; Adept resolved `crs.sd15.control` |
| Adept `:8758` invoke `sd15.txt2img` | **PASS** — job `d5ea4aad-305c-48a3-b2b6-fae083357f6b` **done**; `history_json.workflowKey=sd15.txt2img`; checkpoint `v1-5-pruned-emaonly.safetensors`; **512×768** 504,757 bytes; **exactly one image**; Schnick Coffee Library; `lockModelFamily=true`; `allowDraft=true`; no silent fallback |
| Adept invoke `crs.sd15.control` | **PASS** — job `822d8e61-1760-42fe-9ea2-610ff7c09ba3` **done**; `history_json.workflowKey=crs.sd15.control`; **512×768** 504,757 bytes; **exactly one image**. No `control_image` was supplied, so the builder omitted ControlNet (txt2img-equivalent graph). Pose-control proof is the Comfy OpenPose smoke, not this Adept invoke |
| Qwen 2512 regression | **PASS** (catalog) — `qwen2512.txt2img` + `qwen2512.ref` **Certified**; `UNETLoader` still lists `qwen_image_2512_fp8_e4m3fn.safetensors`; beauty dropdown still Certified. Full Qwen generate not re-run (expensive); object_info + registry + `/api/imagegen/models` used |
| FLUX regression | **PASS** (catalog) — `flux.txt2img` + `flux.img2img` **Certified**; `UNETLoader` still lists `flux1-kontext-dev.safetensors`; beauty dropdown still Certified. Full FLUX generate not re-run |
| Illustrious path unchanged | **PASS** — still `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models\checkpoints\Illustrious-XL-v1.0.safetensors` **6,938,040,736** bytes; **not** under `D:\01_Models`; still in `CheckpointLoaderSimple` |
| Restart/recovery | **PASS** — Adept-owned Studio API restart + Adept-owned Comfy restart; discovery healthy; queue empty after smokes |
| VRAM / time / GPU device | **PASS** — device `cuda:0 NVIDIA GeForce RTX 5090`; torch `2.10.0+cu130`; OpenPose smoke peak 5532 MiB / 59% GPU; no silent CPU fallback |

Disposable subject only. **Korri was not generated.**

### OpenPose notes

1. First Comfy OpenPose `/prompt` (`f24cba8c-…`) **errored** while Hugging Face was downloading `hand_pose_model.pth` (`RuntimeError: Cannot send a request, as the client has been closed`).
2. Annotators were pre-downloaded with the Comfy `.venv` `huggingface_hub` client.
3. Retry on the **mannequin** pose source succeeded as a graph but `openpose_json.people = []` (featureless armless torso). Output saved as `evidence/adept_sd15_openpose_smoke_mannequin_empty_pose.png`.
4. A disposable generic adult (not Korri) was generated as pose source (`adept_sd15_pose_human.png`). Retry detected **one person** and applied ControlNet. That is the pose-control evidence.

## Evidence

Under `docs/release-gate/sd15-crs-control/evidence/` (no secrets):

- `live_measurements.json`
- `adept_sd15_txt2img_smoke_00001_.png`
- `adept_sd15_openpose_smoke_00002_.png` + `adept_sd15_openpose_map_00001_.png`
- `adept_sd15_pose_human.png`
- `adept_sd15_txt2img_output.png` / `adept_crs_sd15_control_output.png`
- Adept job JSON, Comfy prompt/history JSON, nvidia-smi CSV
- `registry_key_snapshot.json`, `capabilities_sd15Crs.json`, `imagegen_models.json`

## Limitations

- SD15 routes are **Draft** only. Not AUTO. Not a Certified Character Creator beauty. `sd15Crs.preferred=false`.
- Adept `crs.sd15.control` without a `control_image` / reference is a **txt2img-shaped** graph (ControlNet nodes omitted by design). Live pose-control was proven on Comfy HTTP, not through Character Creator.
- OpenPose annotators require a one-time Hugging Face download into `comfyui_controlnet_aux/ckpts`.
- DWPose onnxruntime is missing; unused by this smoke.
- Qwen / FLUX regression is catalog + object_info, not a full generate.
- Working tree is `feat/crs-flux-auto-one-figure` @ `1c86560` with uncommitted Chief SD15 files, not a clean checkout of `feat/codirector-sanitation-phase1`.
- Helper `adept-sd15-invoke.ps1` prints a `POST ...` banner before JSON; parse the job `id` from the JSON object, not `$PID`.
- Worker message still says `ImageGen (edit) complete` (generic leftover `edit_op`); operation was `image.generate`.
- `GET /api/image-runtime/capabilities` can serve a stale artifact until `write_capabilities_artifact()` is refreshed.

## Binary verdict

```text
GO — SD 1.5 INSTALLED + COMFY CRS CONTROL ROUTE AVAILABLE
```
