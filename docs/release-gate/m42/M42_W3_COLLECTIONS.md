# M42 Wave 3 — Production Collections

| Field | Value |
|---|---|
| **Phase** | M42-W3 |
| **Status** | Operational |
| **API** | `/api/image-product/projects/{id}/collections` |

## Seeded collections

- Episode 1 Concepts  
- Bridge References  
- Costume Designs  
- Approved Characters  
- Marketing Artwork  

## Behavior

Named groups of asset IDs per project. CRUD + add/remove assets. Collections do **not** bypass ImageProvenance. Library UI filters by `collectionId` and can add the selected asset to a collection.

Artifact: `artifacts/m42/w3/collections_results.json`.
