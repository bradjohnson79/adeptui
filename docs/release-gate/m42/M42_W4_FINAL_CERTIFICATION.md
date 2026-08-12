# M42 Wave 4 — Final Certification

| Field | Value |
|---|---|
| **Phase** | M42 Phase 4.2 Wave 4 — Advanced Image Editing |
| **Branch** | phase2/m42-advanced-image-editing |
| **Baseline** | phase2/m42-image-product-integration (Wave 3 **GO**) |
| **Verdict** | **GO** |
| **wave4Go** | 	rue |
| **RuntimeCertificationPreserved** | 	rue (wave1/2/3 GO preserved) |
| **Stamped** | 2026-07-30 |

## Product path (locked)

`	ext
CreativeContext → ImageEditIntent → Unified Resolver → pinned imageRuntime → QueueWorker (execute-only) → Output Gate (semantic) → DerivedAsset → EditProvenance → VersionGraph
`

## Required certified edit set

zimage.ref_edit, zimage.inpaint, zimage.outpaint, image.upscale ⊆ certifiedProductionPathEditWorkflowKeys.

## Delivered

- ImageEditIntent + operation taxonomy + Editing Recipes + EditLayer model
- Mask store + ImageMaskEditor + layer-aware Edit Workspace
- Leaf builders: inpaint / outpaint / upscale (live dual-stage Certified)
- Semantic Output Gate + visual edit history thumbnails
- Version graph + human approval pipeline (review notes, Production Master)
- Batch edit apply API
- Co-Director propose_image_edit (+ batch) with Bible CreativeContext digest
- FLUX Kontext conversational interface stub (**Blocked** until certified)
- Legacy specialized edit callers migrated; unresolved bypass list empty

## Wave 5 handoff

Wave 4 owns professional non-destructive editing, masks, control assets, edit lineage, and approval.

Wave 5 owns **identity & continuity** (must not be claimed here):

- character identity locks; face/body/wardrobe/hair/age continuity
- environment / prop / style continuity
- identity embeddings / IC-LoRA / multi-angle packs
- continuity validation across scenes/shots; Bible enforcement
- batch generation with identity controls

Wave 6P remains later beta certification.

## Non-claims

- No Wave 1–3 redesign; no certification fabrication
- No identity continuity enforcement (Wave 5)
- Draft/Deferred/Blocked (including FLUX Kontext) are **not** production-ready
- No destructive overwrite of source / Production Master
- No product-side builder imports or direct queue_prompt

## Evidence

- Gate: rtifacts/m42/w4/wave4_gate_results.json (wave4Go: true)
- Live cert: M42_W4_LIVE_CERTIFICATION.md + cert JSON under rtifacts/m42/w4/
- Tests: studio-api/tests/test_m42_w4_image_edit.py (14 passed)
- Companion reports: all M42_W4_*.md in this folder
