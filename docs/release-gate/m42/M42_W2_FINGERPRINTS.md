# M42 Wave 2 — Fingerprints

Fingerprints cover graph structure (volatile inputs redacted), builder source, node inventory, and model inventory.

Stored in:

- Registry `fingerprints.graphHash` for Certified entries
- Append-only certification records
- `artifacts/m42/w2/workflow_fingerprints.json`
- `config/image-workflows/workflow-fingerprints.json`

QueueWorker enforces drift for Certified pinned contracts via `assert_no_graph_drift`.
