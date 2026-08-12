# Image Workflow Inventory (M42 W1 Draft)

Authoritative machine registry: `config/image-workflows/certified-registry.json`

| workflowKey | Category | Status | Builder |
|---|---|---|---|
| `zimage.txt2img` | Generation | Draft | `app.workflows.image_tools:build_zimage_txt2img_workflow` |
| `zimage.ref_edit` | Reference | Draft | `app.workflows.image_tools:build_zimage_ref_workflow` |
| `checkpoint.txt2img` | Generation | Draft | `app.imagegen_workflows:build_txt2img_workflow` |
| `checkpoint.img2img` | Editing | Draft | `app.imagegen_workflows:build_img2img_edit_stub` |
| `image.upscale` | Restoration | Draft | TBD Wave 2 |
| `image.chroma_key` | Utility | Draft | `app.generation_tools.ops:run_chroma_key` |

Nothing is Certified until Wave 2 live certification.
