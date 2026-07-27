# M30E MODEL KNOWLEDGE REGISTRY

| Field | Value |
|-------|-------|
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting SHA | `5af34eff0a5207febf05ef6cc4a3e4f7d572eb15` |
| Implementation SHA | `bdc43f8e70cc69d767089f9ed2b0358c7fb82f42` |
| Documentation SHA | `PLACEHOLDER_DOCS_SHA` |
| Provider Manifest SHA | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` |
| Date | 2026-07-27 |

## Packs

| modelId | status | runtime |
|---------|--------|---------|
| z_image | ACTIVE | production |
| ltx_2_3 | ACTIVE | not_production_ready |
| wan_2_2 | ACTIVE | not_production_ready |
| fal_seedance | ACTIVE | production |
| fal_kling / fal_veo / fal_runway | VERIFIED | experimental |
| seedream / nano_banana_pro / gpt_image_fal | QUARANTINED | product_approval_required |

## Commands

`python -c "from app.codirector.model_intelligence.loader import validate_all; print(validate_all())"`
