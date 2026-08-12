# M42 Wave 4 — Output Gate (Semantic)

Structural checks (readable, checksum, dimensions, preview) plus operation-success semantics:

| Class | Check |
|---|---|
| inpaint / object_remove / object_replace | Mask-region pixel delta vs source |
| outpaint / crop_extend | Canvas expanded to expected bounds |
| upscale | Output resolution > source |
| background_remove / transparent_extract | Alpha present when requested |
| reference_edit | Not byte-identical when transform required |

Semantic failure → Output Gate fail (do not register as successful edit).

Artifact: output_gate_results.json (semanticValidation: true).
