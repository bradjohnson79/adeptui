# M42 Wave 3 — Generate Studio

Generate Studio (`ImageGenPanel` → workspace `futureDestination: "generate"`) is the filmmaker image product surface.

- Family selector from readiness (ZImage / FLUX / Qwen / Imagen + status badges)  
- Session Preset picker  
- Recommendation card: whyThisModel + time/VRAM/cost (overridable)  
- Batch 1–8 via `api.imageProduct.generate`  
- No workflow-key picker  
- Job monitoring via `ImageJobStage` pipeline  

Artifact: `artifacts/m42/w3/generate_studio_results.json`.
