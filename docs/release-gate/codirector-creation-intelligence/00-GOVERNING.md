# Co-Director Creation Intelligence — Governing Document

**Status:** GOVERNING for Revision B  
**Law 30:** This is the single governing document for this milestone. Older Spatial Map, Scene Creator, and Character Creator reports remain historical unless they certify frozen subsystems this revision must not reopen.

**Architecture:** A only. Sibling `SpatialDraft`. Do **not** add `zones[]` to `SpatialMapDocument`.

## Product law

Can Co-Director infer this reliably? If yes, automate it. If no, keep user control. Co-Director governs whether or not the chat panel is open.

Filmmaker stays in creative control. Accept is the only write from perception into Spatial Map slots.

## Authority ladder

```text
Explicit filmmaker instruction
  > approved CRS / approved Spatial Map slots
  > approved SpatialDraft Accept
  > Co-Director inference
  > raw model detection
```

Once the filmmaker corrects a fact, Co-Director must not reverse it.

## Contracts

- `PerceptionPacket` (`creation-perception-v1`) — geometry only. No furniture lists. No SAM logits / DINO tokens.
- `SpatialDraft` (`spatial-draft-v1`) — sibling persist via `ProjectTraitRow` category `spatial_draft`. Never a production field on `SpatialMapDocument`.
- Accept-into-slot writes only through existing `place_character` / `place_prop` / `create_camera`. Hard 4 / 4 / 4.
- Zone language is glossary phrases on the draft, not Architecture B ERS zones.

## Frozen systems

- Single-CRS Character Creator (`CharacterCore.tsx`, `visual_sheet.py` coerce)
- `SpatialMapDocument` production fields, `limits.py` 4/4/4, `ers_contracts.py`, Amendment #3
- `CameraShotPacket` schema, `SceneIntent`
- `video_intelligence/` including `gpu_lease.py` API (stills uses sibling `preflight_for_stills`)
- MAGI
- Certified image capability IDs; `qwen.edit` unpublished
- Setup `catalog.py` as the only component registry

## Setup / models

Optional Testing geometry only. Dedicated installer `stills_perception_hf`. Never Hunyuan fallback.

License memos:

- [docs/models/grounding-dino-tiny/LICENSE_CLEARANCE.md](../../models/grounding-dino-tiny/LICENSE_CLEARANCE.md)
- [docs/models/sam21-hiera-tiny/LICENSE_CLEARANCE.md](../../models/sam21-hiera-tiny/LICENSE_CLEARANCE.md)
- [docs/models/depth-anything-v2-small/LICENSE_CLEARANCE.md](../../models/depth-anything-v2-small/LICENSE_CLEARANCE.md)

Do not add these ids to `REQUIRED_FOR_GENERATION`.

## Out of scope

Architecture B zones-in-ERS, Pose Landmarker, Qwen-Image-Edit-2511, FreqEdit, identity embeddings, closed-loop regen, MAGI perception, Revision A worker moves.

## Certification

Live visual evidence is required. Backend green is not GO.

Final language only:

```text
CERTIFIED COMPLETE — FULL-STACK E2E VERIFIED
```

or

```text
NO-GO — FULL-STACK E2E NOT VERIFIED
```

or

```text
E2E BLOCKED — <blocker>
```

Current certification report: [01-CERTIFICATION.md](./01-CERTIFICATION.md)
