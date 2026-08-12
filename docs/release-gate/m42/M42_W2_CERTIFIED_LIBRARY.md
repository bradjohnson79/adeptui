# M42 Wave 2 — Certified Image Workflow Library

## Required local (Certified)

| Workflow Key | Status | Stage 1 Leaf | Stage 2 Production Path |
|---|---|---|---|
| `zimage.txt2img` | Certified | PASS | PASS |
| `zimage.ref_edit` | Certified | PASS | PASS |

## Modern families (foundation — not forced Certified)

| Family | Keys | Typical status |
|---|---|---|
| FLUX | `flux.txt2img`, `flux.img2img`, `flux.reference`, `flux.edit` | Deferred until weights + live cert |
| Qwen Image | `qwen.txt2img`, `qwen.edit`, `qwen.reference` | Deferred until weights + live cert |
| Google Imagen | `imagen.txt2img`, `imagen.edit`, `imagen.reference` | Blocked without credentials |
| Legacy checkpoint | `checkpoint.txt2img`, `checkpoint.img2img` | Deferred — prefer family keys |

## Rules

- Never fabricate Certified.
- Exact inclusion: `requiredLocal ⊆ certifiedProductionPathWorkflowKeys`.
- Append-only ledger: `artifacts/m42/w2/workflow_certification_records.jsonl`.
- Registry holds `certificationRecordId` pointers only.
