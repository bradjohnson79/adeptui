# M42 Wave 3 — Image Session Presets

| Field | Value |
|---|---|
| **Phase** | M42-W3 |
| **Status** | Operational |
| **API** | `/api/image-product/projects/{id}/presets` |

## Built-in presets

1. Concept Art  
2. Storyboard  
3. Character Sheet  
4. Environment Sheet  
5. Marketing Artwork  
6. YouTube Thumbnail  
7. Poster  
8. Matte Painting  

Each stores: `preferredModelFamily`, `aspectRatio`, `qualityPreset`, `resolution`, `guidance`, `promptTemplate`, `defaultReferenceAssetTypes[]`.

## Behavior

- Built-ins are immutable; users save project copies via POST.  
- Applying a preset fills Generate Studio / Co-Director propose fields; overrides allowed before execute.  
- Artifact: `artifacts/m42/w3/presets_results.json`.
