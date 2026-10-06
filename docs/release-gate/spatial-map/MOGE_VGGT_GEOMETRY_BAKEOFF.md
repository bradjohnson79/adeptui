# MoGe-2 / VGGT Geometry Bake-off

**Governing document for reconstruct → render.**  
**Version:** 2026.08.1

Qwen / FLUX Image Edit is **not** the Atlas camera. That attempt is historical: [`SPATIAL_MAP_DIRECT_QWEN_AB_TEST.md`](./SPATIAL_MAP_DIRECT_QWEN_AB_TEST.md).

## Routing (do not change)

| Path | Engine | Renderer |
|---|---|---|
| Express, 1 observed image | MoGe-2 | Shared deterministic TOP_DOWN |
| Standard, 1 observed image | MoGe-2 (explicit fallback; do not pretend multi-view exists) | Same |
| Standard, 2+ **real** observed images | VGGT-1B-Commercial | Same |
| Co-Director / Qwen Edit extra views | Inferred reasoning support only — not observed spatial truth | Must not masquerade as VGGT evidence. See [`QWEN_SUPPLEMENTARY_VIEW_ASSIST_CERTIFICATION.md`](./QWEN_SUPPLEMENTARY_VIEW_ASSIST_CERTIFICATION.md). |

Unseen space = UNKNOWN / LOW CONFIDENCE. No invented rooms. No diffusion in this bake-off.

JEPA stays advisory. It does not generate geometry and must not fail a true overhead plate for “looks unlike the photo.”

## Acquisition

- MoGe: clone `microsoft/MoGe`. Official HF weights only when install is authorized. Weights license remains **unconfirmed**.
- VGGT: clone `https://github.com/facebookresearch/vggt`. Production weights **only** `facebook/VGGT-1B-Commercial`. Forbid `facebook/VGGT-1B`.
- Isolated venvs: `data/runtimes/moge2` and `data/runtimes/vggt`.
- Python supervisor/process control only. No PowerShell install scripts.

VGGT may remain `MODEL_ACCESS_GATED`. That must not block MoGe-2 Express.

## Owner review

Review strip: SOURCE / MOGE TOP-DOWN / VGGT TOP-DOWN / VGGT MULTI-VIEW if any.

Owner judges usefulness (corridor shape, floor, walls, doors/elevators, holes, scale) — not pretty.

Intermediate language only after owner review:

- `GO — MOGE-2 EXPRESS GEOMETRY SELECTED`
- `GO — VGGT STANDARD GEOMETRY SELECTED`
- `NO-GO — GEOMETRY RECONSTRUCTION ATLAS NOT YET USABLE`

Do **not** build Viewport / Approve / Look until a usable plate exists **and** the owner reviews it.

Product sentence not in scope until a later mission:

`GO — ADEPT UI GEOMETRY-BASED SPATIAL MAP ATLAS PRODUCTION CERTIFIED`

## SenseNova corridor

- Project: `0ffe56e2-0d58-4926-91bf-0f947898d02e`
- Source: `1211dd83-e3f6-4d17-bf2b-669ec5961418`

## Live bake-off evidence (2026-08-26)

Observed, not predicted.

| Fact | Value |
|---|---|
| Isolated MoGe source | `data/runtimes/moge2/src` from `microsoft/MoGe` |
| Isolated MoGe venv | `data/runtimes/moge2/venv` — Torch `2.10.0+cu130`, CUDA True, RTX 5090 |
| Isolated VGGT source | `data/runtimes/vggt/src` from `facebookresearch/vggt` |
| Isolated VGGT venv | `data/runtimes/vggt/venv` |
| VGGT 1-image corridor | `VGGT_REQUIRES_TWO_OBSERVED_IMAGES` — MoGe-2 explicit fallback |
| VGGT weights | absent — `MODEL_ACCESS_GATED` |
| VGGT Ready | **false** (clone ≠ Ready) |
| MoGe infer | GPU, 53.938s, VRAM max 3,093,660,160 bytes, `cpuFallback=false` |
| Points / depth / normals | 720×1280×3 / 720×1280 / 720×1280×3 |
| Weights repo | `Ruicheng/moge-2-vitl-normal` — weights license **unconfirmed** |
| Renderer | `adept.atlas.deterministic.v1` — mandatory `TOP_DOWN_ORTHOGRAPHIC` |
| Diffusion / style knobs | none |
| Viewport / Approve / Look | **not built** |
| Engine promoted | **false** |

Evidence paths:

- Source copy: `docs/release-gate/spatial-map/evidence/geometry_bakeoff/source.png`
- Owner strip: `docs/release-gate/spatial-map/evidence/geometry_bakeoff/owner_review_strip.png`
- MoGe top-down: `docs/release-gate/spatial-map/evidence/geometry_bakeoff/moge2/plates/top_down_orthographic.png`
- High-angle / isometric: same `plates/` folder
- Provenance: `docs/release-gate/spatial-map/evidence/geometry_bakeoff/moge2/plates/provenance.json`
- Report: `docs/release-gate/spatial-map/evidence/geometry_bakeoff/bakeoff.json`

### Usefulness notes for owner review

The reconstruct-then-render path ran on the SenseNova corridor. The mandatory plate is a source-color splat of the MoGe-2 point map, not a painted Atlas. Corridor volume (foreground lobby, receding hall, side alcoves) is visible. Doors, elevator call plates, and the far figure are not readable as a production floor plan. Unseen space stays empty/muted. VGGT top-down is absent because commercial weights are gated.

Owner judges usefulness. Intermediate language is **not** issued by this bake-off step:

- not `GO — MOGE-2 EXPRESS GEOMETRY SELECTED`
- not `GO — VGGT STANDARD GEOMETRY SELECTED`

Until the owner accepts a usable plate:

`NO-GO — GEOMETRY RECONSTRUCTION ATLAS NOT YET USABLE`

Product sentence remains out of scope:

`GO — ADEPT UI GEOMETRY-BASED SPATIAL MAP ATLAS PRODUCTION CERTIFIED`
