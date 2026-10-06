# Wonder3D Feasibility and Runtime Assessment

**Scope:** Character Creator V3 — single-image-to-3D (multi-view normals/colors + mesh extraction)  
**Date:** 2026-08-24  
**Agent:** Subagent B (Kimi Code 2.7)  
**Status:** First draft / paper evidence only. No weights downloaded. No changes to production Comfy, torch, CUDA, or `studio-api/.venv`.

---

## Verdict

```text
NO-GO — WONDER3D MODEL WEIGHTS ARE AGPL-3.0
```

The upstream code is permissive (MIT), but the published pretrained checkpoints (`flamehaze1115/wonder3d-v1.0` on Hugging Face) are labeled **AGPL-3.0**. That is a hard blocker for a closed-source/proprietary Adept UI distribution unless the model card is corrected or a commercially clear alternative checkpoint is identified. The technical path below is documented for completeness, but implementation must not proceed until the license blocker is resolved.

---

## 1. Exact official repo vs. maintained forks / Comfy nodes

| Source | URL | Notes |
|---|---|---|
| **Official code** | https://github.com/xxlong0/Wonder3D | Default branch `main`. CVPR 2024 Highlight. Last push 2025-03-14. |
| **Windows branch** | https://github.com/xxlong0/Wonder3D/tree/main-windows | Community / maintainer Windows setup notes. Still the same repo, not a fork. |
| **ComfyUI integration** | https://github.com/MrForExample/ComfyUI-3D-Pack | Includes `Comfy3D Wonder3D MVDiffusion Model` node, but requires PyTorch3D and tightly couples to Comfy’s Python environment. **Not recommended** for Adept UI per the isolation requirement. |
| **Hugging Face weights** | https://huggingface.co/flamehaze1115/wonder3d-v1.0 | Default pipeline used by the inference examples. License: AGPL-3.0. |
| **OneDrive checkpoints** | SharePoint link in README | Alternative download, but no explicit separate license; README still points to the Hugging Face model. Treat as AGPL-3.0 unless proven otherwise. |

**Recommended repo for a future technical spike:** `xxlong0/Wonder3D` at the `main-windows` branch, only if a license-cleared checkpoint becomes available. The `main` branch does not contain native Windows instructions.

---

## 2. Licenses

| Asset | License | Source |
|---|---|---|
| Wonder3D code | MIT | [LICENSE](https://github.com/xxlong0/Wonder3D/blob/main/LICENSE) |
| Wonder3D paper weights (`flamehaze1115/wonder3d-v1.0`) | **AGPL-3.0** | [model card metadata](https://huggingface.co/flamehaze1115/wonder3d-v1.0) / [HF discussion #5](https://huggingface.co/flamehaze1115/wonder3d-v1.0/discussions/5) |
| tiny-cuda-nn | BSD-3-Clause | [NVlabs/tiny-cuda-nn LICENSE.txt](https://github.com/NVlabs/tiny-cuda-nn/blob/master/LICENSE.txt) |
| instant-nsr-pl | MIT | [bennyguo/instant-nsr-pl](https://github.com/bennyguo/instant-nsr-pl) |
| NeuS | MIT | [Totoro97/NeuS LICENSE](https://github.com/Totoro97/NeuS/blob/main/LICENSE) |
| nerfacc | MIT | [nerfstudio-project/nerfacc LICENSE](https://github.com/nerfstudio-project/nerfacc/blob/master/LICENSE) |
| diffusers | Apache-2.0 | Hugging Face |
| transformers | Apache-2.0 | Hugging Face |
| xformers | Apache-2.0 / BSD-3-Clause | Meta |
| PyTorch | BSD-3-Clause | Meta |

**Blocker:** The AGPL-3.0 weight license conflicts with shipping Wonder3D as a silent/essential Recommended component in a proprietary product. The code and dependency stack are otherwise permissive.

---

## 3. Windows viability

- **Native Windows:** Supported only via the `main-windows` branch. Setup requires Anaconda, a CUDA Toolkit matching the driver, Visual Studio/C++ build tools for `cl.exe`, and a source build of `tiny-cuda-nn`.
- **Known issues:**
  - `instant-nsr-pl` reconstruction is reported to be unstable on Windows (issue #27). Users often switch to the NeuS backend.
  - `num_workers` in `instant-nsr-pl/datasets/ortho.py` can cause `OSError: [Errno 22]` on Windows; must be reduced.
  - `subprocess.CalledProcessError: where cl` requires `cl.exe` on PATH.
- **Community consensus:** WSL2 Ubuntu is frequently described as more stable and faster than native Windows for the reconstruction step (issue #29: 10 min view extraction on Windows vs. ~30 sec on WSL2, ~6 min mesh extraction).
- **Conclusion:** Windows is **possible but fragile**. The reconstruction backend should be selectable (Instant-NSR vs. NeuS) with NeuS as the safer Windows default.

---

## 4. Python / CUDA / PyTorch requirements

Official `main` requirements.txt pins:

```text
--extra-index-url https://download.pytorch.org/whl/cu117
torch==1.13.1
torchvision==0.14.1
diffusers[torch]==0.19.3
xformers==0.0.16
transformers>=4.25.1
bitsandbytes==0.35.4
pytorch-lightning<2
omegaconf==2.2.3
nerfacc==0.3.3
torch_efficient_distloss
rembg
segment_anything
gradio==3.50.2
# ... (see full file in repo)
```

Plus:

```bash
pip install git+https://github.com/NVlabs/tiny-cuda-nn/#subdirectory=bindings/torch
```

The `main-windows` branch example uses the same PyTorch 1.13.1+cu117 line.

**CUDA:** The `main` branch is documented against CUDA 11.7/11.8. Windows community reports use CUDA 11.8. `tiny-cuda-nn` must be compiled against the installed CUDA.

---

## 5. VRAM and host RAM typical requirements

- **VRAM:** 8 GB is reported as sufficient for the reconstruction step (issue #29). Users advise unloading the multi-view diffusion model before reconstruction to free memory.
- **Host RAM:** WSL2 users recommend ~24 GB total and dedicating ~14 GB to the WSL2 VM. Native Windows will likely need a similar working set for the reconstruction optimizer.
- **Target hardware:** This workstation has an RTX 5090 with 32 GB VRAM and 64 GB+ host RAM expected, so capacity is not the bottleneck.

---

## 6. RTX 5090 (Blackwell / sm_120) compatibility risk

- **RTX 5090** uses compute capability **sm_120** (Blackwell).
- **PyTorch support:** Stable Blackwell support first appeared in PyTorch **2.7.0** with CUDA **12.8** wheels. Earlier PyTorch builds (1.13.1, 2.1, etc.) do not include sm_120 kernels and will fail with:
  ```
  CUDA error: no kernel image is available for execution on the device
  ```
- **Official Wonder3D pins torch==1.13.1+cu117.** Running that exact environment on an RTX 5090 is **not viable**.
- **Mitigation:** Create an isolated venv with a modern PyTorch (2.7+ / CUDA 12.8+ or 13.0+). However, `diffusers==0.19.3` and `xformers==0.0.16` are not tested against PyTorch 2.7, and `tiny-cuda-nn` must be rebuilt for the new CUDA. This is a **significant integration risk**, not a confirmed blocker, but it means a live GPU smoke test on the exact 5090 is mandatory before any production claim.
- **Current Comfy torch:** Not inspected directly because ComfyUI is not in this repo root. The `studio-api/.venv` has **no torch installation** (verified), so production API Python is not contaminated.

---

## 7. Input resolution, output views, and expected runtime

- **Input:** Any size is accepted, but the model internally resizes to **256 × 256**. The README explicitly states: *“Any images will be first resized into 256x256 for generation, so images after such a downsample that still keep clear and sharp features will lead to good results.”* Centered foreground objects occupying ~80% of image height are recommended.
- **Output:** **6 views** of color images and **6 matching normal maps**, produced by a cross-domain MVDiffusion pipeline. The example code uses `make_grid(images, nrow=6, ncol=2)` showing the 12-panel grid layout.
- **Post-processing:** The generated views feed either:
  - `instant-nsr-pl` (Neuralangelo-ortho-wmask config) for fast reconstruction, or
  - `NeuS` for smoother, more robust but slower reconstruction.
- **Runtime:** Paper claims **2–3 minutes total** for a single image on appropriate hardware. Real-world reports vary widely (seconds for view generation, minutes for mesh extraction; Windows can be significantly slower).

---

## 8. Anime vs. realistic character notes

- The model was trained primarily on **photorealistic / rendered object images** (e.g., Objaverse, GSO). It is **not specifically trained on anime characters**.
- Literature reports a domain gap: stylized drawings, cartoons, and sketches can confuse the contour lines with internal texture, causing messy textures and shape degradation ([DrawingSpinUp](https://arxiv.org/html/2409.08615v1), Fig. 2/11).
- For Character Creator use cases that mix realistic and stylized characters, expect:
  - Realistic/prop inputs: generally good results, though thin structures and complex backgrounds can still fail.
  - Anime/stylized inputs: higher artifact rate; may require pre-processing or an alternative model trained on stylized data.
- **No live provenance** on Adept character designs yet. Mark this as a qualitative risk.

---

## 9. Isolated venv requirement

**YES.** Per Adept UI build laws and the fragility of the Wonder3D dependency stack, this runtime must never be installed into:

- `studio-api/.venv`
- The production ComfyUI Python environment
- Any existing avatar/audio/video venv under `data/`

Adept already uses the same isolation pattern for MAGI GPU upscaling (`data/runtimes/realesrgan-ncnn-vulkan`) and for multiple feature-specific venvs (`data/m210b-*`). Wonder3D should follow the same pattern.

---

## 10. Camera convention

The README documents the generated views in the **input-view related camera system** (not a world canonical system):

- **Elevation:** 0° for all 6 views.
- **Azimuth:** 0°, 45°, 90°, 180°, -90°, -45° respectively.
- **Projection:** Orthographic (not perspective).
- The front view (azimuth 0°) is initialized as the input view.

**Mapping to Adept UI / Character Creator view indices:** **UNMEASURED.** Do not assume an ordering. A live run must print the exact view order from the pipeline before any camera-to-view-index mapping is wired into production code.

---

## 11. Recommended integration plan (if license is cleared)

1. **Create a new runtime root:**
   ```
   data/runtimes/wonder3d/
   ├── venv/                 # isolated Python 3.10+ venv
   ├── repo/                 # shallow clone of xxlong0/Wonder3D main-windows
   ├── ckpts/                # license-cleared model weights
   ├── sam_pt/               # Segment Anything checkpoint
   ├── outputs/              # per-job working directory
   └── manifest.json         # installed version, provenance, probe result
   ```

2. **Install inside the isolated venv:**
   - Modern PyTorch 2.7+ with CUDA 12.8+ (required for RTX 5090).
   - Compatible diffusers/transformers/xformers versions (to be determined experimentally).
   - `tiny-cuda-nn` built from source against the matching CUDA.
   - Optional `NeuS` cloned into `repo/NeuS` for the Windows-safe reconstruction path.

3. **Worker interface:**
   - A thin Python subprocess worker in the venv exposes two operations:
     - `generate_multiview(input_image_path, output_dir)` → returns the 12-panel grid and the 6 individual view files.
     - `extract_mesh(view_dir, method='neus', output_path)` → returns a textured mesh.
   - The Studio API spawns the worker via `subprocess.run`, passing JSON paths and reading JSON/PNG outputs. No direct import of Wonder3D code into the Studio API process.

4. **Model readiness gate:**
   - Add a Setup Wizard component for the isolated venv + weights.
   - Reuse the existing `data/runtimes` pattern and `magi/realesrgan_runtime.py` style manifest/probe.
   - The probe must import `torch`, run a tiny forward pass on the RTX 5090, and verify `torch.cuda.get_arch_list()` includes `sm_120`.

5. **Do not integrate as a Comfy node.** ComfyUI-3D-Pack exists but would force the Adept runtime into the Comfy Python environment and add PyTorch3D build complexity, violating the isolation rule.

---

## 12. Machine inspection (read-only)

```text
GPU:        NVIDIA GeForce RTX 5090
Driver:     610.62
CUDA UMD:   13.3
VRAM:       32,607 MiB total (≈2,861 MiB in use at inspection time)
Host OS:    Windows 10/11 (win32 10.0.26200)
```

- `studio-api/.venv` does **not** contain `torch` (verified by import test and site-packages inspection). No production Python torch was touched.
- Existing Adept isolation evidence:
  - `data/runtimes/realesrgan-ncnn-vulkan/` (MAGI GPU upscaling) with binary, models, manifest, and cached zip.
  - `data/runtimes/avatar/`, `data/runtimes/index-tts2/`, etc.
  - Multiple isolated feature venvs: `data/m210b-ace-venv`, `data/m210b-kvenv`, `data/m210b-qwen-voice-clone-venv`, `data/m210b-sfx-venv`, etc.
- No Wonder3D runtime, weights, or venv were created or downloaded.

---

## 13. Open questions / risks

1. **License:** Is there an ungated, commercially usable Wonder3D checkpoint? If not, the component cannot be recommended/essential.
2. **Blackwell port:** Can `diffusers==0.19.3` and the custom `flamehaze1115/wonder3d-pipeline` run under PyTorch 2.7+ without code changes? A live spike must answer this.
3. **Camera mapping:** What is the exact view order returned by the pipeline? Must be measured live before wiring to the Character Creator camera layout.
4. **Reconstruction backend:** Which backend (Instant-NSR vs. NeuS) is stable and fast enough on native Windows for the target workflow?
5. **Anime quality:** What preprocessing or fallback is needed for stylized Adept characters?

---

## 14. Alternatives evaluated (not wired)

The V3 law says: if Wonder3D is unsuitable, stop and evaluate another dedicated open-source multi-view engine. Do **not** rebuild generator-invented Back as a workaround.

| Engine | Notes | Action |
| --- | --- | --- |
| Era3D (`pengHTYX/Era3D`) | Successor from the same authors; typically AGPL-adjacent. | Not a license escape. |
| InstantMesh | Mesh-first; different product contract than three camera stills. | Owner decision later. |
| Zero123++ / SV3D | Different licenses and view conventions; not measured here. | Owner decision later. |

No alternative was installed. Character Creator V3 keeps the Wonder3D adapter **license-blocked** until a commercially clear checkpoint exists.

---

## 15. References

- Wonder3D official repo and README: https://github.com/xxlong0/Wonder3D
- Windows branch README: https://github.com/xxlong0/Wonder3D/blob/main-windows/README.md
- Paper: https://arxiv.org/abs/2310.15008
- Hugging Face model card (AGPL-3.0): https://huggingface.co/flamehaze1115/wonder3d-v1.0
- Windows install issue #29: https://github.com/xxlong0/Wonder3D/issues/29
- instant-nsr-pl Windows issue #27: https://github.com/xxlong0/Wonder3D/issues/27
- ComfyUI-3D-Pack: https://github.com/MrForExample/ComfyUI-3D-Pack
- PyTorch Blackwell / sm_120 support: https://github.com/pytorch/pytorch/issues/159207
- PyTorch 2.7+ CUDA 12.8 guidance: https://docs.salad.com/container-engine/tutorials/machine-learning/pytorch-rtx5090
- tiny-cuda-nn: https://github.com/NVlabs/tiny-cuda-nn
