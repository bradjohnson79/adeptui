# M42 W1 — Image Provenance

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Schema** | `studio-api/app/image_runtime/provenance.py` |
| **Artifact** | `artifacts/m42/w1/image_provenance_schema.json` |

## ImageProvenance fields

workflow · workflowVersion · runtime · provider · references · prompt · seed · parentImages · generationTime · validation · continuity · approval · projectLocation

Matches video provenance philosophy. QueueWorker must write provenance on every successful generation in **Wave 2** — not claimed complete in Wave 1.
