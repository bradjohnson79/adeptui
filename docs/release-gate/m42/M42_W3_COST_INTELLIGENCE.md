# M42 Wave 3 — Cost / Resource Intelligence

| Field | Value |
|---|---|
| **Phase** | M42-W3 |
| **Status** | Operational |
| **API** | `POST /api/image-product/recommend` |

## Envelope

```yaml
recommendedFamily: flux | qwen | imagen | zimage
whyThisModel: "…"
estimates:
  generationTimeSec: number
  vramGb: number | null
  costUsd: number | null
  costLabel: "Local GPU" | "$0.04"
  providerKind: local | cloud
alternatives: [...]
overridable: true
```

## Rules

- Photoreal → FLUX if Certified else ZImage  
- Stylized/anime → Qwen else ZImage  
- High-quality cloud edit → Imagen else `zimage.ref_edit`  
- Estimates from registry VRAM profiles + `config/image-runtime/cloud-price-table.json`  
- Never invent Certified status  

Artifact: `artifacts/m42/w3/cost_intelligence_results.json`.
