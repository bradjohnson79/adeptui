# Spatial Map Direct Qwen A/B

> **HISTORICAL.** Qwen visual Atlas is **rejected as the primary Atlas camera**. Keep reconstruction packet JSON. Never feed the structural guide raster as photo-class truth. Current geometry work is governed by [`MOGE_VGGT_GEOMETRY_BAKEOFF.md`](./MOGE_VGGT_GEOMETRY_BAKEOFF.md) and [`ATLAS_DETERMINISTIC_RENDERER.md`](./ATLAS_DETERMINISTIC_RENDERER.md).

Governing document for this (closed) Qwen A/B mission. The compiler report remains historical for the dual-condition path and is **not** a visual-generation winner.

## Verdict

`NO-GO — SPATIAL MAP ATLAS GENERATION NOT CERTIFIED`

Neither route produced a useful roofless Atlas. No production route was promoted. Viewport / Approve / Regenerate chrome was **not** built. Playwright product closure was **not** run. Comfy MCP was **unavailable**. Final product GO is blocked.

A/B intermediate language is **not** earned:

- not `GO — DIRECT QWEN ATLAS PATH SELECTED`
- not `GO — SPATIAL RECONSTRUCTION COMPILER REPAIRED`

Owner visual review is required before any later promotion. This report presents both plates; there is no winner to promote.

## Execution order (observed)

FORENSICS → MINIMAL ROUTE A → MATCHED A/B → OWNER VISUAL REVIEW (this handoff) → **STOP**

Architecture decision: **both fail**. No third fallback invented.

## Branch / runtime

- Branch: `feat/character-creator-final-closure`
- HEAD: `b6156455e643d5fa430784b3130756f2d8038651` plus uncommitted Atlas forensics / Route A work
- Project (forensics + A/B): SenseNova Integration Lab `0ffe56e2-0d58-4926-91bf-0f947898d02e`
- Source: `1211dd83-e3f6-4d17-bf2b-669ec5961418` (1280×720 Combat Chamber corridor)
- Guide: `f7afc120-59ba-4b59-929c-44393c3efd0e` (96×480, 2 colors)
- Packet: `sr_ef7120b2ec5c` (3×15 corridor, reused)
- Local UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/` (API-only recycle; Desktop Comfy `:8188` left running)
- GPU: NVIDIA GeForce RTX 5090, CUDA, no silent CPU fallback
- Comfy MCP: **unavailable** — `/history`, `/system_stats`, `/object_info`, saved graphs only

## Forensics (Route B)

Evidence: `docs/release-gate/spatial-map/evidence/forensics_20260825/`

| Stage | Result |
|---|---|
| Source | PASS — readable 1280×720 |
| Packet | PASS — 3×15 corridor, internally consistent |
| Guide raster | Valid schematic of the packet. Not a corrupt file. Dishonest as a photo-class reference. |
| Upload | As-is (`studio/spatial_structural_guide.png` + source) |
| Plus encode | image1=guide, image2=source |
| EmptyLatent | 1024×1024 |
| Output | Source at sides + vertical center corruption + blue corners |

**First malformed stage:** `plus_dual_ref_incompatible_guide_as_image1`

The guide is a contributing input, not independently guilty as JSON. The first dishonest visual stage is feeding that 96×480 two-color plate to Qwen as Plus `image1`.

Live forensic job: `13796030-1053-4e20-9949-7cd03f8dd52e` → asset `5dbce5e6-9c53-4d67-958e-9b09f252c1c2` (70.341 s). Same plate as prior bake-off.

## Route A (minimal)

New draft key `qwen2512.atlas_direct` (`generationRoute=direct_qwen_atlas`).

Live graph (`19c1015f-f2b2-4ee8-af8e-b7be1f942428`): one `LoadImage` (source only), `TextEncodeQwenImageEdit` pos+neg, `EmptyLatentImage` 1024², `KSampler` 28 / CFG 4 / denoise 1.0. **No** guide, Plus, VAEEncode latent, mask, ControlNet, or new guide.

Default production path remains Route B until a winner exists. Route A is opt-in via `generationRoute`.

## Matched A/B

Evidence: `docs/release-gate/spatial-map/evidence/atlas_direct_ab/`

| | Route A | Route B |
|---|---|---|
| Graph | `qwen2512.atlas_direct` | `qwen2512.atlas` |
| Refs | source only | guide + source |
| Size / steps / seed | 1024 / 28 / 20260825 | 1024 / 28 / 20260825 |
| Wall | **77.033 s** | **70.519 s** |
| Pixel gate | PASS (`pixelKind=atlas`, `needsVlm=true`) — **false PASS** | `FAIL_CORRUPTION` |
| Asset | `51e8bec4-5815-487c-8456-b6b8f2f00e8d` | `b3050fb8-f07f-4359-a38a-0b0bf3b94227` |
| Honest visual | Same corridor, blue restyle, **still eye-level**. Not a roofless Atlas. | Source at sides, center column + blue corners. |

Performance: neither is materially faster (Δ 6.5 s). Complexity does not earn its place — Route B is slightly faster and **corrupted**.

Automatic gate may reject corruption. It cannot promote a route. The pixel classifier labeled Route A `atlas` because the frame is square with balanced edge energy. That is not a top-down map.

## Owner visual review

Presenting both plates. There is **no** production winner.

Please inspect (on disk; some agent indexers skip PNGs):

- `docs/release-gate/spatial-map/evidence/atlas_direct_ab/ROUTE_A_direct.png` (1,694,351 bytes)
- `docs/release-gate/spatial-map/evidence/atlas_direct_ab/ROUTE_B_compiler.png` (1,162,054 bytes)
- Library assets: A `51e8bec4-5815-487c-8456-b6b8f2f00e8d`, B `b3050fb8-f07f-4359-a38a-0b0bf3b94227`

Required of a useful Atlas (all must hold): no corruption; recognizable same environment; actual roofless/top-down or high-angle transformation; useful spatial readability; acceptable time.

Agent visual finding (not a substitute for the owner): **both fail**. Route A is cleaner than Route B and still the wrong camera.

## Architecture decision

**STOP.** Do not invent a third fallback in this task. Do not retire the guide from a production visual path that was never certified. Perception/packet remain structured spatial data. Route A remains an unpromoted draft graph.

## What was implemented (not certified)

- Forensic strip + notes
- `qwen2512.atlas_direct` builder and opt-in handler route
- `FAIL_CORRUPTION` pixel reject (Route B live plate and synthetic fixture)
- Matched A/B harness
- Unit tests: 27 passed (`test_qwen2512_atlas_workflow`, `test_atlas_generate_i2i`, `test_spatial_reconstruction_compiler`)

## What was not built (law)

- Production Viewport / Approve / Regenerate / Look replacement
- Playwright disposable-project closure
- Comfy MCP live-graph certification
- Permanent production-route promotion

## Tests

| Suite | Result |
|---|---|
| Atlas workflow + generate + compiler/gate | **27 passed** |
| Playwright product closure | **NOT RUN** — both A/B routes failed; no winning path to certify |
| Comfy MCP | **UNAVAILABLE** |

## Independent verifier

`REJECTED — both A/B routes failed the Atlas transformation; Comfy MCP unavailable`

### E2E TRACE

| Stage | Status |
|---|---|
| User action | N/A — harness, not creator Viewport |
| Frontend | N/A — final UI not built |
| API | PASS — both routes accepted |
| Backend | PASS — Route A one-image graph; Route B Plus dual-ref |
| Persistence | PASS — assets written |
| Runtime | PASS jobs on RTX 5090; no silent CPU fallback |
| Result | FAIL — A wrong camera; B corruption |
| Reload | N/A — no approved Atlas |
| Downstream | N/A |

## Peer review

- [GLM 5.2](a24915c6-bb6f-489b-a180-f7244cb2a50d): **BLOCK** on evidence-label consistency (PNG indexer miss; stale `firstMalformedStage`; `A_preferred` token). Product NO-GO and both-fail/stop agreed. Labels reconciled after the review.
- [Kimi K3](5aa4af9a-04f8-4f3a-b3f8-f3afcce75633): **PASS** — READY FOR PRIMARY REVIEW. Both-fail + stop agreed. Same label repairs listed as non-verdict defects.

Neither peer issued a product GO. Comfy MCP remains unavailable.

## Product language

`NO-GO — SPATIAL MAP ATLAS GENERATION NOT CERTIFIED`

Blockers: no useful roofless Atlas; Comfy MCP unavailable; Viewport/Approve/Regenerate not built; Playwright not run; owner has not accepted a winner.
