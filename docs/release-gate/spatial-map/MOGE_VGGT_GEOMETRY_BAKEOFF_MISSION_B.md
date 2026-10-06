# Mission B — Reconstruct → Render Geometry Bake-off

**Governing docs:** [`MOGE_VGGT_GEOMETRY_BAKEOFF.md`](./MOGE_VGGT_GEOMETRY_BAKEOFF.md), [`ATLAS_DETERMINISTIC_RENDERER.md`](./ATLAS_DETERMINISTIC_RENDERER.md)

This is a **separate verdict** from Mission A. Mission A remains:

`GO — ADEPT UI ESSENTIAL COMPONENTS AGREEMENT + MOGE-2 SETUP REGISTRATION CERTIFIED`

## Intermediate language (owner-gated)

Owner visual review is required before any engine promotion. This step does **not** issue:

- `GO — MOGE-2 EXPRESS GEOMETRY SELECTED`
- `GO — VGGT STANDARD GEOMETRY SELECTED`

Until the owner accepts a usable plate:

`NO-GO — GEOMETRY RECONSTRUCTION ATLAS NOT YET USABLE`

Product sentence remains out of scope:

`GO — ADEPT UI GEOMETRY-BASED SPATIAL MAP ATLAS PRODUCTION CERTIFIED`

Viewport / Approve / Look was **not** built.

## Routing (unchanged)

| Path | Engine | Renderer |
|---|---|---|
| Express, 1 observed image | MoGe-2 | `adept.atlas.deterministic.v1` |
| Standard, 1 observed image | MoGe-2 (explicit fallback) | same |
| Standard, 2+ real observed images | VGGT-1B-Commercial | same |
| Co-Director / Qwen extra views | inferred only — not observed spatial truth | must not masquerade as VGGT |

## Observed GPU smoke — MoGe-2 Express

| Field | Observed |
|---|---|
| Project | `0ffe56e2-0d58-4926-91bf-0f947898d02e` |
| Source asset | `1211dd83-e3f6-4d17-bf2b-669ec5961418` |
| Device | `cuda` — NVIDIA GeForce RTX 5090 |
| Torch | `2.10.0+cu130` |
| CPU fallback | **false** |
| Duration | 53.938 s |
| VRAM max | 3,093,660,160 bytes |
| Point / depth / normals | 720×1280×3 / 720×1280 / 720×1280×3 |
| Weights | `Ruicheng/moge-2-vitl-normal` — license **unconfirmed** |
| Mandatory plate | TOP_DOWN_ORTHOGRAPHIC |
| Diffusion / style knobs | none |

Isolation: `data/runtimes/moge2` (GitHub `microsoft/MoGe`). Not Comfy, Studio API venv, Adept Bots, or MCP.

## VGGT — gated, not Ready

| Field | Observed |
|---|---|
| Source | cloned `facebookresearch/vggt` → `data/runtimes/vggt/src` |
| `sourceInstalled` | true |
| `runtimeReady` | **false** |
| `commercialModelAccess` | **false** |
| `modelReady` | **false** |
| `ready` | **false** |
| Status | `MODEL_ACCESS_GATED` |
| Model id | `facebook/VGGT-1B-Commercial` only |
| Forbidden | `facebook/VGGT-1B` |
| Single-view VGGT smoke | **not run** — commercial weights absent |
| Multi-view | **not run** — no second real observed angle |

VGGT gated status did not block MoGe-2 Express.

## Owner review strip

`docs/release-gate/spatial-map/evidence/geometry_bakeoff/owner_review_strip.png`

Tiles present: SOURCE / MOGE TOP-DOWN. VGGT TOP-DOWN absent (gated).

Usefulness notes (not a promotion):

- Corridor volume (lobby, receding hall, side alcoves) is visible in the splat.
- Doors, elevator plates, and the far figure are not readable as a production floor plan.
- Unknown space stays muted. No invented rooms. No diffusion.

## Tests

- `studio-api/tests/test_atlas_deterministic_renderer.py`: 9 passed
- `studio-api/tests/test_geometry_runtime_status.py`: 2 passed
- Combined geometry suite: **11 passed**

## Peers

- [GLM 5.2](47fe6c35-8285-4089-bee3-148107d74134): architecture/renderer/confidence PASS. BLOCK-1 VGGT 1-image guard, BLOCK-2 inferred-view provenance, BLOCK-3 matchedRenderer on live report — **repaired**.
- [Kimi K3](7be6c9c9-9423-43e1-b354-4b5bc4bd2cf0): T1–T7 PASS. Zero BLOCK tickets.

## Live URLs

- Creator UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/` (API-only recycle; Desktop Comfy `:8188` left running)
