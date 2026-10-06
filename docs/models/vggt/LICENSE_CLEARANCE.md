# VGGT-family — License Clearance

> **SUPERSEDED 2026-08-26** by [`docs/setup/ESSENTIAL_COMPONENT_REGISTRY.md`](../../setup/ESSENTIAL_COMPONENT_REGISTRY.md) and [`docs/setup/ESSENTIAL_COMPONENTS_LICENSE_AND_TERMS.md`](../../setup/ESSENTIAL_COMPONENTS_LICENSE_AND_TERMS.md). `vggt_1b_commercial` is now registered **ESSENTIAL** Spatial Intelligence with `MODEL_ACCESS_GATED` / `REQUIRES_EXTERNAL_ACCEPTANCE`. Production weights are `facebook/VGGT-1B-Commercial` only. Retain this file only as a historical audit of the 2026-08-20 non-commercial VGGT-1B omission.

Reviewed on `2026-08-20`. Historical verdict below is **not** current product classification.

This document is a technical compliance audit for Adept UI implementation gating. It is **not** professional legal advice.

## Verdict

```text
OMIT / NOT PACKAGED — VGGT NOT CLEARED FOR ADEPT UI v1.1 ESSENTIALS
```

VGGT must **not** be an Essential, Recommended Setup card, or silent download for Adept UI v1.1 Open Source / Free.

## Why

| Checkpoint | Finding |
|---|---|
| `facebook/VGGT-1B` | Non-commercial. Rejected. |
| `facebook/VGGT-1B-Commercial` | Custom Meta license, military exclusion, **gated** Hugging Face access (application / contact form). Not suitable as a quiet OSS Essential. |

Code and weights are not Apache-2.0 / MIT ungated pins. Prompt §37: a component that cannot legally fit the intended distribution model must not quietly become Essential.

## v1.1 spatial substitute

Spatial intelligence for Revision D is **Depth Anything V2 Small** (`depth_anything_v2_small`), already cleared Apache-2.0 (Small only). See [../depth-anything-v2-small/LICENSE_CLEARANCE.md](../depth-anything-v2-small/LICENSE_CLEARANCE.md).

Classification: **RECOMMENDED** in the Essentials Pack. Not `required=True`. Not in `REQUIRED_FOR_GENERATION`.

## Re-open rule

Re-evaluate VGGT only if an **ungated**, commercially clearable checkpoint is published and a later named Setup decision records it. Do not download `VGGT-1B` as a fallback.
