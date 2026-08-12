# M42 Wave 2 — Live Certification

## Dual-stage results

Both required workflows passed leaf + production-path certification against live ComfyUI.

Evidence:

- `artifacts/m42/w2/leaf_certification_results.json`
- `artifacts/m42/w2/production_path_certification_results.json`
- `artifacts/m42/w2/workflow_certification_records.jsonl`
- `artifacts/m42/w2/outputs/`

## zimage.ref_edit proofs

- Reference fixture exists and is readable
- Reference hash recorded in provenance
- Invalid / missing reference rejected before queue
- Graph contains `LoadImage` + `TextEncodeZImageOmni` image1 binding (reference consumed)
- Parent / reference relationship recorded on production-path provenance

## Cancellation

See `artifacts/m42/w2/cancellation_results.json`. Fast-workflow stages may be `NOT_OBSERVABLE` without failing certification. Mandatory invariants (no late complete, no asset after cancel, no duplicate registration on retry, next job succeeds, reservation released) are enforced by QueueWorker policy.
