# M42 Character Creator Workflow Report

**Date:** 2026-07-31  
**Mock data:** false  
**Exports:**  
- `artifacts/m42/character-creator/workflow-zimage-txt2img.json`  
- `artifacts/m42/character-creator/workflow-zimage-ref-edit.json`  
- `artifacts/m42/character-creator/workflow-hashes.json`

---

## Certified workflows used by Character Creator pack

| Key | Version | Builder | Pack phase |
|---|---|---|---|
| `zimage.txt2img` | 1.0.0 | `build_zimage_txt2img_workflow` | hero, coverage |
| `zimage.ref_edit` | 1.0.0 | `build_zimage_ref_workflow` | details, performance |

Certification record for ref_edit after correction: `CERT-IMG-ZIMAGE-REF-001-20260731-006`.

---

## zimage.ref_edit graph (corrected)

```text
UNETLoader → ModelSamplingAuraFlow → KSampler
CLIPLoader → TextEncodeZImageOmni (text only) → KSampler.positive
CLIPLoader → CLIPTextEncode (negative) → KSampler.negative
VAELoader → VAEEncode(LoadImage→ImageScale) → KSampler.latent
KSampler → VAEDecode → SaveImage
```

**Not used (removed):** `EmptyLatentImage` + Omni `image1` reference feed.

**Fingerprint:** `graphHash = sha256:c8c2c11cb8306b4dad0782aaa63e6e42a90d9863f016239950fb65a294298f51`  
**Nodes:** UNETLoader, CLIPLoader, VAELoader, LoadImage, ImageScale, ModelSamplingAuraFlow, TextEncodeZImageOmni, CLIPTextEncode, VAEEncode, KSampler, VAEDecode, SaveImage

---

## Validity checks

| Check | Result |
|---|---|
| Workflow JSON valid | Yes (exported) |
| Node IDs / links | Connected (latent from VAEEncode; conditioning from Omni/CLIP) |
| Checkpoint / UNET | Z-Image Turbo via UNETLoader (not CheckpointLoaderSimple) |
| VAE | VAELoader + encode/decode |
| Sampler | KSampler, denoise≈0.72 on ref path |
| Save node | SaveImage present |
| Placeholder workflow | No — production builders only |
| Drift gate | Passes after registry update |

---

## Workflow verdict

**PASS** — Adept UI constructs valid, certified ComfyUI graphs for both txt2img and ref_edit. No placeholder graphs on the Character Creator path.
