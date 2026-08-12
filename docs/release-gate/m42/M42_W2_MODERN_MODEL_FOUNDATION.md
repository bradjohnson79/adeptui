# M42 Wave 2 — Modern Model Integration Foundation

## Purpose

Prepare FLUX, Qwen Image, and Google Imagen as first-class Image Runtime citizens without Wave 3 product UX.

## Delivered

| Capability | Evidence |
|---|---|
| Discovery | `artifacts/m42/w2/modern_model_discovery.json` |
| Provider registry | `config/image-runtime/provider-registry.json` |
| Capability probe | `artifacts/m42/w2/runtime_capabilities.json` |
| Family registry keys | `flux.*`, `qwen.*`, `imagen.*` in certified-registry |
| Contract extensions | `modelFamily`, `capabilities.*` on CanonicalImageWorkflowContract |
| Readiness report | `M42_W2_IMAGE_RUNTIME_READINESS_REPORT.md` |

## ModernModelFoundationReady

Does **not** require FLUX/Qwen/Imagen to be Certified unless installed and live-certified. Requires discovery, registration, unified routing, extended contracts, provider abstraction, capability detection, and readiness reporting.
