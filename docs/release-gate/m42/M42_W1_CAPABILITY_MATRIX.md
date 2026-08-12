# M42 W1-3 — Image Capability Matrix

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Artifact** | `artifacts/m42/w1/capability_matrix.json` |

## Workflow categories

Generation · Editing · Reference · Restoration · Utility · Training · Identity · Compositing · Publishing

## Readiness legend

| Value | Meaning |
|---|---|
| `working` | Live product path today |
| `partial` | Wired but incomplete / generic |
| `draft` | Draft registry entry only |
| `draft_registry_only` | Schema/registry only (e.g. identity) |
| `blocked` | Explicitly unavailable |
| `not_implemented` | No product path |

## Highlights

| Capability | Category | Draft workflow | Readiness |
|---|---|---|---|
| Text to Image | Generation | `zimage.txt2img` | partial |
| Image to Image / ref | Editing / Reference | `zimage.ref_edit` | partial |
| Upscale | Restoration | `image.upscale` | draft |
| Chroma key | Utility | `image.chroma_key` | working |
| Identity preservation | Identity | — | draft_registry_only (Wave 5) |
| Inpaint / Outpaint / Multi-ref | Editing / Reference | — | not_implemented |

No capability is Production Ready until Wave 2 Certified.
