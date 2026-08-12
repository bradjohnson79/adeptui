# M42 W1 — Reference Asset Architecture

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Schema** | `studio-api/app/image_runtime/reference_assets.py` |
| **Artifact** | `artifacts/m42/w1/reference_asset_schema.json` |

## ReferenceAsset

```yaml
referenceId
type: character | environment | prop | vehicle | wardrobe | lighting | pose | composition | style | palette
approvedVersion
relationships
sourceImages
continuityTags
```

Frozen types become the backbone for IC-LoRA, multi-reference generation, storyboard, Director, and Production Bible. Wave 1 defines the schema; Wave 2 binds reference IDs into certified workflows; Wave 5 enforces identity registries.
