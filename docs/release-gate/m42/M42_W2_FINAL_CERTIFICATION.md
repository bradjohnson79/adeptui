# M42 Wave 2 — Final Certification

| Field | Value |
|---|---|
| **Phase** | M42 Phase 4.2 Wave 2 |
| **Branch** | `phase2/m42-certified-image-workflows` |
| **Baseline** | `phase2/m42-image-runtime-foundation` |
| **Verdict** | **GO** |
| **wave2Go** | `true` |
| **ModernModelFoundationReady** | `true` |
| **imageProductionCertified** | `true` (required local only) |

## Certified production path

```text
requiredLocalProductionWorkflowKeys ⊆ certifiedProductionPathWorkflowKeys
```

- `zimage.txt2img` — leaf PASS + production-path PASS
- `zimage.ref_edit` — leaf PASS + production-path PASS

Cloud production keys remain empty / Blocked unless separately live-certified.

## Ownership handoff — Wave 3

Wave 2 owns certified runtime + modern-model foundation.

Wave 3 owns product exposure of certified model families through:

- Generate Studio
- Co-Director
- Director
- Storyboard
- Character Builder
- Environment Builder
- Asset Library

Wave 3 also eliminates legacy imagegen parameter callers listed in `artifacts/m42/w2/legacy_callers.json`.

Wave 4 — advanced editing / reference workflows.  
Wave 5 — identity preservation / continuity / film-specific pipelines.

## Non-claims

- FLUX / Qwen Image / Imagen are **not** claimed Production Ready unless live-certified (currently Deferred/Blocked).
- No Generate Studio / Co-Director / Director UX redesign in this wave.
- No fabricated certification evidence.
