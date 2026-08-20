# Co-Director World-State Intelligence — Governing Document

**Status:** GOVERNING for Revision C  
**Law 30:** This is the single governing document for this milestone. Older Co-Director, Revision A, and Revision B reports remain authoritative for their domains. This document governs the additive world-state intelligence layer only.

**Current program completion report:** [../REVISION-ABC-FINAL-CLOSURE.md](../REVISION-ABC-FINAL-CLOSURE.md)  
**Historical / invalid prior GO:** [02-LIVE-CERTIFICATION.md](./02-LIVE-CERTIFICATION.md)

**Architecture:** A. JEPA observes/embeds/compares/predicts. Co-Director interprets meaning. Adept UI performs action.

## Product law

Co-Director remains the governing authority. JEPA never directs production, never independently mutates scenes, and never independently accepts/rejects generated imagery.

Revision C is an additive intelligence layer underneath Co-Director. It complements:

- **Revision A** — temporal video intelligence (VideoChat3 — "What visibly happened?")
- **Revision B** — creation/spatial intelligence (CRS, Spatial Map, Scene Intent — explicit production facts)

Revision C (V-JEPA) provides: "How does this visual state relate to prior/expected visual states?"

## Authority ladder

```text
Explicit creator correction
  > Approved canon
  > Approved Spatial Map
  > Scene Intent / production facts
  > Co-Director reasoning
  > JEPA world-state signal
  > raw perception
```

If JEPA disagrees with approved production truth: Co-Director may flag the discrepancy. JEPA may not silently overwrite anything.

## Contracts

- `WorldStatePacket` (`world-state-v1`) — provider-independent world-state comparison. Metadata + embedding reference only. No raw tensors in project JSON.
- `CoDirectorWorldIntelligencePolicy` — creator policy for world intelligence (off/automatic/review_on_change)
- `WorldReferenceAnchor` — approved world state for comparison
- `IntentionalChangeRecord` — creator-confirmed intentional state transitions

## Setup / models

| Component | Classification |
|---|---|
| `vjepa2_world_intelligence` | Advanced/Recommended (`required=False`) |

Classification may be promoted to Essential only if:
- licensing is clear (PASS — MIT ✓)
- runtime is practical (ViT-L ~2.5GB VRAM ✓)
- measured value is strong (pending certification)
- it materially improves normal Adept UI workflows (pending)

Creator-facing Setup language:
> **Co-Director World Intelligence** — Helps Co-Director compare scenes, detect world-state drift, and preserve visual world consistency.

## Model selection

Primary model: `facebook/vjepa2-vitl-fpc64-256` — ViT-L/16, 256px, 64 frames, ~300M parameters, ~2.5GB VRAM

Selection rationale:
- ViT-L (1024 hidden, 24 layers, 16 heads) balances quality vs resource cost
- 256px input is efficient for embedding extraction
- 64-frame temporal tubelet gives temporal context for scene-state comparison
- MIT licensed, native Transformers support
- No custom code or remote execution required

Advanced variant (future): `facebook/vjepa2-vith-fpc64-256` — ViT-H, ~5GB VRAM (hardware-gated)

V-JEPA 2.1: PENDING Transformers PR #45497 merge. Not required for v1.1 GO.

## Frozen systems

Do not alter:
- Revision A `TemporalContinuityPacket` and video intelligence contracts
- Revision B `PerceptionPacket`, `SpatialDraft`, `SpatialMapDocument` production fields
- `CoDirectorContinuityPolicy` on `SceneTimelineMaster`
- `VideoChat3-4B` and `InternVideo3-8B` setup entries
- `grounding_dino_tiny`, `sam21_hiera_tiny`, `depth_anything_v2_small` setup entries
- `REQUIRED_FOR_GENERATION` — world intelligence must never block generation
- ComfyUI, generation adapters, MAGI

## Out of scope for v1.1

- Full generative world simulation
- SceneCraft v1.2 (future)
- V-JEPA 2.1 integration (pending Transformers support)
- Always-on GPU residency (worker loads/unloads per request)
- Auto-rejection based on JEPA scores alone
- New primary UI panels ("JEPA Studio", "World Model Panel")
- Raw embedding scores in creator-facing UI
- Per-project fine-tuning

## V1.1 success condition

```text
Approved visual world
        ↓
new generation / edit
        ↓
JEPA world-state comparison
        ↓
Co-Director understands
whether the world remained coherent
        ↓
creator receives useful advice
```

Without requiring the user to understand JEPA.

## V1.2 readiness condition

The architecture leaves behind reusable interfaces for SceneCraft:
- world state
- state comparison
- state transition
- approved anchors
- intentional revisions
- reference retrieval
- world anomaly detection

SceneCraft should consume these without rewriting Revision C.

## Final verdict language

Only:

`GO — CO-DIRECTOR WORLD-STATE INTELLIGENCE & JEPA INTEGRATION CERTIFIED`

or:

`NO-GO — CO-DIRECTOR WORLD-STATE INTELLIGENCE & JEPA INTEGRATION NOT CERTIFIED`
