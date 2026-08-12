# M42 Wave 3 — Co-Director Image Intelligence

- `propose_image_generate` preview runs `recommend` + `prompt_intel` before approve  
- Preview shows whyThisModel + time/VRAM/cost  
- Tool schema: purpose / modelFamilyPreference / presetId / acceptExpandedPrompt (no workflow key)  
- ProductionIntent `_image_generate` → `image_product.service.generate_images` only  
- Web `execute.ts` `queueImageGeneration` / `queueAvatarGeneration` → `api.imageProduct.generate`  
- CreativeContext digest from Bible package when available  

Artifact: `artifacts/m42/w3/codirector_results.json`.
