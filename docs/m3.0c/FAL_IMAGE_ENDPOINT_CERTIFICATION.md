# M3.0c — FAL Image Endpoint Certification

## Certification rule

This document records repository evidence only. No fal image endpoint is certified or
claimed as wired. `studio-api/app/fal_catalog.py` has `FAL_IMAGE_MODELS = {}` and the
manifest is unchanged.

| Image family | Status | Evidence / next decision |
|---|---|---|
| Seedream | **PRODUCT_APPROVAL_REQUIRED** | Not registered in `FAL_IMAGE_MODELS`; product must approve a specific model and input contract. |
| Nano Banana Pro | **PRODUCT_APPROVAL_REQUIRED** | Not registered in `FAL_IMAGE_MODELS`; product must approve a specific model and input contract. |
| GPT Image | **PRODUCT_APPROVAL_REQUIRED** | Not registered in `FAL_IMAGE_MODELS`; product must approve a specific model and input contract. |

No endpoint IDs are supplied here because none are verified in the repository. Adding a
guessed ID would make the UI advertise a request the queue cannot reliably submit.

## Approval-ready checklist

- [ ] Product selects the exact fal model page/model family and approves cost, licensing,
  safety, latency, and output policy.
- [ ] Engineering records the provider-confirmed endpoint ID and input/output schema.
- [ ] Engineering adds a `FalModel` entry with `media_type="image"` to
  `FAL_IMAGE_MODELS`.
- [ ] Engineering adds and unit-tests the family-specific argument builder.
- [ ] API model listing and UI filtering show the new image row.
- [ ] Credential failure and provider failure remain fail-closed.
- [ ] One live request is run with a real approved credential and its request ID/artifact
  are recorded in a follow-up evidence document.
- [ ] Product approval and live proof are reviewed before status changes to VERIFIED.

## Existing video scope

The existing video engines remain the four catalogue entries in
`studio-api/app/fal_catalog.py`: Seedance, Kling, Veo, and Runway. This document does
not add or alter video endpoints.

## Current conclusion

Image endpoint certification is **PENDING** product approval and live provider proof.
Local still-image generation remains the ComfyUI path already documented in the M3.0a
matrix.
# M3.0c fal.ai Image Endpoint Certification

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Product decision | **1B — Provider Manifest unchanged** |
| Manifest sha256 | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` |
| Code registry | `studio-api/app/fal_catalog.py` — `FAL_IMAGE_MODELS = {}` |

## Classifications

| Family | Classification | Notes |
|--------|----------------|-------|
| Seedream | PRODUCT_APPROVAL_REQUIRED | Not registered; no endpoint id added this milestone |
| Nano Banana Pro | PRODUCT_APPROVAL_REQUIRED | Not registered |
| GPT Image | PRODUCT_APPROVAL_REQUIRED | Not registered |
| Kling (video) | VERIFIED_IMPLEMENTED_NOT_LIVE_TESTED (I2V catalog) | Video only — see fal video matrix |
| Seedance (video) | VERIFIED_AND_LIVE_TESTED (prior T2V); queue path M3.0c | Video only |

## Approval-ready queue (future integration)

Before any image family may be coded:

1. Product approves the model intent and Manifest edit.
2. Real fal.ai endpoint identifier is verified from fal's model page (not guessed).
3. Input/output contracts documented.
4. Current provider availability confirmed.
5. Native platform mapping specified.
6. Paid-operation + security requirements implemented.
7. Live job executed **or** route labeled unverified and unavailable to ordinary users.

## Still-image production path for M3.0c

Local ComfyUI Z-Image remains the authorized still-image generator. fal image families stay out of `FAL_IMAGE_MODELS` for this gate.
