# M41 4.1B — UI Integration Report

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |

## Surfaces verified (wiring)

| Surface | Integration |
|---|---|
| Generate Studio `Txt2VidPanel` | Existing APIs; local I2V still start-frame gated |
| Director One/Three Frame | `render kind=scene`; WAN+middle → `wan.three_frame` via resolver |
| Shot render | `POST …/render kind=shot` → `render_shot` |
| Timeline | `kind=timeline` reuses outputs; `kind=batch_timeline` regenerates all |
| Generation Tools extend | Queues `video_extend` → local last-frame I2V |
| Generation Tools upscale | Remains Deferred; badge maps to **Deferred** |
| LipSync | Existing lipsync routes → `lipsync.latentsync` |
| Diagnostics | `/diagnostics/video-runtime` lists Certified Workflow Library |
| m29 Production Suite | Still flag-gated; uses same studio render/lipsync jobs |

## Honesty fixes

- `mapGenerationToolStatus("DEFERRED")` → `Deferred` (was Unknown)
- Compatibility / registry: no `production_ready` until CERTIFIED
- Gate phase label: `M41-4.1B`

## Playwright

`tests/e2e/m41/m41-41b-certified-workflows.spec.ts` — registry, resolver, gate, diagnostics page.
