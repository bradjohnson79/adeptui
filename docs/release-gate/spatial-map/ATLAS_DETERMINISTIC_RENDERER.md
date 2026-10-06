# Atlas Deterministic Renderer

**Governing document for the shared reconstruct-then-render plate.**  
**Version:** 2026.08.1

This renderer is an Adept module, not a generative model. MoGe-2 and VGGT-1B-Commercial must use the **same** plate path.

## Contract

Inputs: point map (H×W×3), optional depth, optional normals, optional camera/FOV, source colors.

Process (deterministic, no hidden per-bench rotations):

1. Valid samples only (finite points, positive depth when present).
2. Floor / up / forward / center from the cloud (eigen basis + locked signs).
3. Virtual overhead camera.
4. **Mandatory view:** `TOP_DOWN_ORTHOGRAPHIC`.
5. Internal helper views: high-angle and isometric.
6. Source-color splat.
7. Unknown / invalid samples: transparent or muted confidence fill.
8. PNG + provenance JSON.

Forbidden:

- Diffusion
- Style knobs
- Painting over bad geometry
- Treating the plate as a photo-class Qwen/FLUX edit

Repeatable inputs → the same plate is a feature.

Implementation: `studio-api/app/spatial_map/geometry/renderer.py`  
Renderer id: `adept.atlas.deterministic.v1`

## Live SenseNova plate (2026-08-26)

MoGe-2 Express used this renderer on corridor `1211dd83-e3f6-4d17-bf2b-669ec5961418`. VGGT did not produce a plate (`MODEL_ACCESS_GATED`). Provenance recorded GPU RTX 5090, no CPU fallback, no diffusion, no style knobs. Owner review is required before any engine promotion. Viewport was not built.
