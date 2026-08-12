# M42 Wave 4 — Inpaint / Outpaint

| Op | Workflow | Builder notes |
|---|---|---|
| inpaint / object_remove / object_replace | zimage.inpaint | ImageToMask + VAEEncodeForInpaint |
| outpaint / crop_extend | zimage.outpaint | ImagePadForOutpaint |
| upscale | image.upscale | ImageScaleBy (×2) when no ESRGAN |

Specialized Generation Tools (enqueue_imagegen_specialized) migrate through image_product.edit_service.enqueue_edit.

Artifacts: inpaint_results.json, outpaint_results.json, 
estoration_results.json.
