# Co-Director Intelligent Selection, Tracking & Inpainting — Governing Document

**Status:** GOVERNING for Revision D  
**Law 30:** This is the single governing document for Revision D. Revision A, B, and C governing files remain authoritative for their domains. Do not extend those files into select / track / protect.

**Program:** Adept UI v1.1 — final feature revision (Open Source / Free)

**Completion report (later):** [REVISION-D-UNIFIED-COMPLETION.md](./REVISION-D-UNIFIED-COMPLETION.md)

---

## Product law

The creator describes the edit. Adept UI determines the technical inputs.

```text
User Intent
  → Co-Director (task-aware perception router)
  → Semantic selection / SAM 2.1
  → Optional depth (Depth Anything V2 Small)
  → Optional world (V-JEPA) / temporal (VideoChat3)
  → PerceptionSelectionPacket
  → Existing ImageEditIntent or Timeline disclosed range/retake
  → Result
```

Do **not** route GPU perception through chat `route_turn`. Embedded services only. Chat tools may propose an edit that already has a selection packet.

Authority ladder (frozen):

```text
Explicit filmmaker instruction
  > approved CRS / approved Spatial Map slots
  > approved SpatialDraft Accept
  > Co-Director inference
  > raw model detection
```

SAM must not auto-write Spatial Map slots. No `zones[]` on `SpatialMapDocument`.

---

## Repository revision names (do not swap)

| Revision | Domain |
|---|---|
| A | Temporal continuity (VideoChat3 / InternVideo3). TimeLens excluded. |
| B | Creation intelligence (CD Scene Review, SpatialDraft, stills boxes) |
| C | World intelligence / V-JEPA (advisory only) |
| D | Intelligent selection, tracking, inpainting assistance, Essentials Pack |

PoseCraft is a **consumer** of selection. It is not Revision C Phase 2 and does not download a pose network.

---

## Locked product decisions

1. **Video inpaint gate** — SAM/select + track produces frame masks that feed existing still inpaint / Timeline range-replacement / disclosed batch retake. Native video-inpaint models stay **blocked** and disclosed.
2. **Essentials Pack** — one Setup UX group. Generation stays unblocked (`REQUIRED_FOR_GENERATION` unchanged).
   - Pack ESSENTIAL: `videochat3_4b`, `sam21_hiera_tiny`, `grounding_dino_tiny`
   - Pack RECOMMENDED: `vjepa2_world_intelligence`, `internvideo3_8b` (VRAM-gated), `depth_anything_v2_small`
   - Excluded: TimeLens. VGGT omitted unless an ungated commercially clearable checkpoint appears.
3. **SAM pin** — `facebook/sam2.1-hiera-tiny` only. SAM 3 and Grounded-SAM-2 rejected.
4. **Spatial** — Depth Anything V2 Small (Apache-2.0 Small only). VGGT is not packaged (see [docs/models/vggt/LICENSE_CLEARANCE.md](../../models/vggt/LICENSE_CLEARANCE.md)).
5. **Background removal** — SAM subject mask → transparent PNG. No silent `zimage.inpaint` as rembg.
6. **Execute path** — stills edits stay on `ImageEditIntent`. Do not add a second inpaint compiler.

---

## Contracts

- `PerceptionSelectionPacket` (`selection-v1`) — canonical mask/selection. Single representation.
- Existing `PerceptionPacket` / `SpatialDraft` remain Revision B geometry. Do not replace them.
- Mask PNG persistence: `image_product.masks.save_mask(..., creator="perception")`.
- Cache keys include `projectId` + asset + frame + entity + model/version. No cross-project hits.

---

## Frozen / do not reopen

- Revision A `TemporalContinuityPacket` and TimeLens exclusion
- `SpatialMapDocument` production fields / Architecture B zones
- MAGI fake video-inpaint execute
- `REQUIRED_FOR_GENERATION` inflation
- Creative `pack_essential_*` zips as the intelligence pack
- PoseCraft rewrite
- Hard-coded personal `D:\` paths
- SAM 3, DA-V2 Base/Large (NC), unofficial V-JEPA forks

---

## Creator-facing language

Use: Select, Track, Remove, Replace, Protect, Remove Background.

Do not expose: SAM checkpoint, VGGT architecture, JEPA embeddings, VideoChat tensors.

Missing capability must be honest:

> Intelligent selection is not installed. Open Setup and install the Adept UI Essentials Pack.

---

## Certification

Live evidence is required. Backend green is not GO.

Final language only:

```text
GO — ADEPT UI v1.1 OPEN-SOURCE FEATURE SET COMPLETE
```

or

```text
NO-GO — ADEPT UI v1.1 REVISION D / ESSENTIALS PACK NOT CERTIFIED
```
