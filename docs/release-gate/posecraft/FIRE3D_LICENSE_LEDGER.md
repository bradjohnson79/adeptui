# Fire3D License Ledger — PoseCraft Reconstruct Stage

**Status:** REVIEWED 2026-09-13 · **Production GO: NOT ACCEPT** until a live `--skip-render` infer is proven not to import nvdiffrast/nvdiffrec, and DINOv3 weights are stored on the Adept-internal tree (not Comfy).

Prior Adept finding stands: TRELLIS.2 was **REJECTED as a shipped commercial pipeline** when the product path depended on nvdiffrast / NC renderer lineage (`docs/release-gate/character-creator/MULTIVIEW_ENGINE_LICENSE_AUDIT.md`). This ledger does not reopen that path.

Official notices: [Fire3D THIRD_PARTY_NOTICES.md](https://github.com/xiahongchi/Fire3D/blob/main/THIRD_PARTY_NOTICES.md).

| Component | License | Adept use | Verdict |
| --- | --- | --- | --- |
| Fire3D original code | MIT | Adapter calls official CLI; no fork | ACCEPT |
| TRELLIS.2 code + decoder weights | MIT | Frozen protocol decoders only | ACCEPT (weights) |
| CuMesh | MIT | Mesh postprocess in official CLI | ACCEPT |
| O-Voxel (TRELLIS.2 helpers) | MIT | Official CLI only | ACCEPT |
| AnyUp | upstream (see Fire3D `third_party/anyup/LICENSE`) | Official CLI only | REVIEW ON INSTALL |
| DINOv3 weights + code | Meta DINOv3 License (2025-08-19) | Backbone required by frozen protocol | ACCEPT with covenants |
| nvdiffrast | NVIDIA Source Code License (non-commercial use limitation) | **Must not run** | REJECT in product path |
| nvdiffrec | NVIDIA Source Code License | **Must not run** | REJECT in product path |
| Blender | GPL + asset terms | Not used for first GO (`--skip-render`) | NOT REQUIRED |
| ShapeR preprocessing | CC BY-NC 4.0 | Baseline only | DO NOT SHIP |
| BoxeR loader | CC BY-NC 4.0 | Baseline only | DO NOT SHIP |

## DINOv3 covenants (Adept)

- Redistribute DINOv3 materials only under the same Meta agreement; keep a copy of `DINOV3_LICENSE.md` next to the weights.
- No military / ITAR / warfare / sanctioned end use.
- Do not reverse-engineer the backbone.
- Do not put DINOv3 weights in the Comfy model tree or in git.

## Product path that can become ACCEPT

1. Isolated Linux/WSL2 Fire3D install (not Windows/Comfy CUDA).
2. `fire3d infer --dataset single_image --skip-render` with the Adept 32 GB profile.
3. Live process evidence that `nvdiffrast` / `nvdiffrec` / Blender are not imported for that job.
4. ShapeR/Boxer baselines never installed into the Adept tree.
5. Weights live only under the Adept-internal Fire3D checkpoint root.

Until those five are observed, licensing is **NOT ACCEPT** for production PoseCraft GO.

`LICENSING GATE: NOT VERIFIED — WSL2 Fire3D not installed; nvdiffrast avoidance not live-proven.`
