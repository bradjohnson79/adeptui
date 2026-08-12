# M42 Wave 2 — Image Runtime Readiness Report

Generated: `2026-07-29T21:32:58Z`

## Summary

- Certified: zimage.txt2img, zimage.ref_edit
- Draft: (none)
- Deferred: flux.txt2img, flux.img2img, flux.reference, flux.edit, qwen.txt2img, qwen.edit, qwen.reference, checkpoint.txt2img, checkpoint.img2img, image.upscale, image.chroma_key
- Blocked: imagen.txt2img, imagen.edit, imagen.reference
- Available for certification: zimage.txt2img, zimage.ref_edit

## Model families

- **zimage**: installed=False statusHint=Blocked — Z-Image weights not found on disk
- **flux**: installed=False statusHint=Deferred — FLUX weights not installed — Deferred
- **qwen**: installed=False statusHint=Deferred — Qwen Image weights not installed — Deferred
- **imagen**: installed=False statusHint=Blocked — Provider unavailable or credentials not configured.
- **checkpoint**: installed=False statusHint=Deferred — Legacy generic checkpoint adapter — prefer family keys (flux.*/qwen.*)

## Workflows

- `zimage.txt2img` — Certified (family=zimage, certifiable=True)
- `zimage.ref_edit` — Certified (family=zimage, certifiable=True)
- `flux.txt2img` — Deferred (family=flux, certifiable=False)
- `flux.img2img` — Deferred (family=flux, certifiable=False)
- `flux.reference` — Deferred (family=flux, certifiable=False)
- `flux.edit` — Deferred (family=flux, certifiable=False)
- `qwen.txt2img` — Deferred (family=qwen, certifiable=False)
- `qwen.edit` — Deferred (family=qwen, certifiable=False)
- `qwen.reference` — Deferred (family=qwen, certifiable=False)
- `imagen.txt2img` — Blocked (family=imagen, certifiable=False)
- `imagen.edit` — Blocked (family=imagen, certifiable=False)
- `imagen.reference` — Blocked (family=imagen, certifiable=False)
- `checkpoint.txt2img` — Deferred (family=checkpoint, certifiable=False)
- `checkpoint.img2img` — Deferred (family=checkpoint, certifiable=False)
- `image.upscale` — Deferred (family=utility, certifiable=False)
- `image.chroma_key` — Deferred (family=utility, certifiable=False)
