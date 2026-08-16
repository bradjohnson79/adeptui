# Scene Creator Multi-Reference — Future Capability

**Status:** Planning note only. Not an implementation milestone.  
**Date:** 2026-08-16  
**Does not change:** Production Grounding + Integrity **GO**, Add **NO-GO**.

## Desired future packet

```text
Character identity   (approved Character Creator pixels)
+ Prop identity      (approved Prop Creator pixels)
+ Environment identity (ERS composite pixels)
+ Spatial / Co-Director structured context (placements, attachments, camera)
```

Example on Schnick: Korri pixels + cup pixels + ERS pixels in one Certified generation, with Spatial Map blocking and camera hash still attached.

## Current certified capacity

| Family | Visual sources | Certified path |
| --- | --- | --- |
| Qwen 2512 | 0 | `qwen2512.txt2img` |
| FLUX | 1 | `flux.img2img` |
| Z-Image | 1 | `zimage.ref_edit` |

The runtime `ReferencePacket` already names roles (`character_reference`, `prop_reference`, `environment_reference`, spatial, cinematography). Today the provider compile consumes **at most one** visual file. Extra bound assets are `semantic_only` or `unsupported`. That honesty is certified; it is not a product substitute for multi-ref pixels.

## Blocker

No Certified local graph loads character + prop + environment pixels together. Draft stubs (`qwen.multi_reference`, `qwen.edit`, `qwen.reference`, `flux.reference`) must not be enabled as a workaround.

## Future requirement

A genuinely Certified multi-reference generate/edit path that:

- is visually proven (pixels, not prompt adjectives)
- preserves explicit packet roles
- consumes actual character, prop, and environment files
- does not silently drop a bound source
- does not silently substitute model or family
- stays capability-driven
- integrates through the existing `ReferencePacket`
- does not require replacing Scene Creator

Do not design the future graph in this note.
