# M42 Wave 4 — Architecture

| Field | Value |
|---|---|
| **Phase** | M42 Phase 4.2 Wave 4 — Advanced Image Editing |
| **Branch** | phase2/m42-advanced-image-editing |
| **Baseline** | Wave 3 GO (wave3Go: true) |

## Canonical path

`	ext
Surface (EditWorkspace / Co-Director)
→ EditingRecipe / EditLayer stack / CreativeContext
→ ImageEditIntent
→ compile_edit_request → ImageIntent
→ WorkflowResolver (allow_draft=False)
→ pinned imageRuntime
→ QueueWorker (execute-only)
→ Output Gate (structural + semantic)
→ DerivedAsset + EditProvenance + VersionGraph
`

No parallel edit runtime. Leaf builders are invoked only via workflow_execute.build_leaf_graph. Production execution requires Certified edit workflow keys.

## Key packages

- studio-api/app/image_product/edit_*.py, 
ecipes.py, layers.py, masks.py, ersions.py, kontext.py
- studio-api/app/workflows/image_edit_tools.py — inpaint / outpaint / upscale builders
- studio-web — ImageEditWorkspace, ImageMaskEditor
