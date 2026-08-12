# M42 Wave 4 — Live Certification

Dual-stage live certification against ComfyUI completed via scripts/m42_w4_live_certify.py.

| Stage | Result |
|---|---|
| Leaf certification | PASS — required edit keys |
| Production-path certification | PASS — ImageEditIntent → resolve → pin → execute → Output Gate |

Certified production-path edit keys:

- zimage.ref_edit
- zimage.inpaint
- zimage.outpaint
- image.upscale

Evidence: leaf_certification_results.json, production_path_certification_results.json, live_certification_summary.json, rtifacts/m42/w4/outputs/, rtifacts/m42/w4/previews/.

No fabricated Certified status. Upscale uses ImageScaleBy when ESRGAN models are absent (honest capability path).
