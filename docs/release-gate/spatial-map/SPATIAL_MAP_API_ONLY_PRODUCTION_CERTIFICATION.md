# Spatial Map API-Only Production Certification

**Governing document for this milestone.**

Local Atlas designer reports stay historical / deferred. Do not cite them as a certified Local production path:

- `LOCAL_SPATIAL_LAYOUT_COMPILER_QWEN_CERTIFICATION.md`
- `LOCAL_ATLAS_DESIGNER_CERTIFICATION.md`
- `LOCAL_SPATIAL_FLUX_CONTROL_ATLAS_CERTIFICATION.md`
- `CODIRECTOR_SPATIAL_MAP_EXPRESS_FINALIZATION.md` (Local/API Express form)

GPT Image 2 behavior is frozen. This milestone only retires Local Atlas from production Express routing/UI.

**Verdict:** `GO — SPATIAL MAP API-ONLY GPT IMAGE 2 PRODUCTION PATH + LOCAL ATLAS PIPELINE RETIREMENT LIVE E2E CERTIFIED`

Auditors:

- Kimi uninstall/Comfy: **PASS — UNINSTALL / DEPENDENCY / COMFY HEALTH**
- Kimi product routing: **PASS — PRODUCT ROUTING GPT-ONLY**
- Composer 2.5: **PASS**

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| Working tree at cert | uncommitted API-only cleanup on `b615645` |
| Named project | Adept Stability Cert `2bc632b8-b329-4d3b-bc40-b68dc41b6bb1` |
| Production map (never write Atlas) | Supplementary View Assist Cert `e6f64c3b-2533-4549-a476-bf0dcb90d298` / Atlas `9f7d4571-9444-41fa-b4c2-29c27919736a` |
| Historical Local cert map (not overwritten) | Local Atlas Designer Cert `a6176a4c-c25c-48c2-9077-ee8932ec4ced` |
| Live cert map | API-Only GPT Image 2 Cert `c88e12ef-0133-4156-95e4-ec8619d49011` |
| Generated Atlas | `a34fe381-a452-4d39-8d33-93ce11e5958e` (`geometrySource=designed`) |

Review URLs left running:

- Creator UI `http://127.0.0.1:5173/`
- Studio API `http://127.0.0.1:8758/`
- Comfy `http://127.0.0.1:8188/` (Desktop Comfy reused; supervisor `--force` was not used)

Evidence: `docs/release-gate/spatial-map/evidence/api-only/`.

---

## Product

Express Spatial Map creation is GPT Image 2 only.

- Title: **Create Spatial Map with Co-Director**
- Atlas Engine: GPT Image 2 (or GPT-required + Open API Settings)
- No Generation Method Local/API
- No Environment Type Interior/Exterior
- Environment Description + `(?)`, Library, Upload, preview, Generate, failure/retry remain
- Standard MoGe/VGGT **reconstruction** stays on `SpatialMapStartChooser` (`design` vs `reconstruct`). That is not Local Atlas design.

---

## Implementation

| Area | Change |
| --- | --- |
| `SpatialMapExpressForm.tsx` / `expressReadiness.ts` | API-only readiness and progress |
| `SpatialMapPanel.tsx` / `atlasGateRetry.ts` | Express always `generationMethod: "api"`; Express reconstruct start no longer sends `local` |
| `atlas_provider.py` | `LOCAL_ATLAS_CANDIDATES = ()`; local resolver returns `LOCAL_ATLAS_NOT_PRODUCTION_CERTIFIED` |
| `atlas_generate.py` | Express `generationMethod=local` coerced to `api` |
| Compilers | Left in place as Deferred R&D |

---

## Uninstall R&D weights

Audit: `flux1-dev.safetensors` and InstantX Union were raw-Comfy R&D only. Production FLUX stills remain `imagegen_flux_checkpoint = flux1-kontext-dev.safetensors`. Catalog `flux1_dev_local` stays optional Setup stills (now unlinked). InstantX is not a Setup Essential.

Deleted:

- `…/diffusion_models/flux1-dev.safetensors` (23,802,932,552 bytes)
- `…/controlnet/instantx_flux1_dev_union.safetensors` (6,603,953,920 bytes)
- Reclaimed **28.32 GB**

Preserved: Kontext, `clip_l`, `t5xxl_fp16`, `ae`. Hugging Face cache leftover noted, not deleted.

After delete, Comfy `:8188` 200. `ControlNetLoader` no longer lists InstantX. `UNETLoader` still lists `flux1-kontext-dev.safetensors`.

---

## Tests

| Suite | Result |
| --- | --- |
| Backend Spatial Map / compiler / dual-route / local resolver | **49 passed** |
| Prop + FLUX CRS protected | **36 passed** |
| Spatial Map vitest | **151 passed** (19 files) |
| Playwright UI / isolation (`:5173`) | **7 passed** |
| Playwright live GPT Image 2 I2I | **1 passed in 3.2m** |

Frozen GPT continuity refuses description-only T2I (`Environment continuity requires an image-conditioned GPT Image 2 path`). Live generate used supplementary-view reference `7780805f-…` for GPT I2I. That is the certified Express create path on this project.

---

## E2E TRACE

| Stage | Verdict | Evidence |
| --- | --- | --- |
| User action | PASS | Express Generate on cert map with description + uploaded environment reference |
| Frontend | PASS | Atlas Engine GPT Image 2; no Local/API/Interior/Exterior; request `generationMethod=api` `hostedModelId=gpt-image-2-kie` |
| API | PASS | `atlas.generate` Express coerced/sent as API |
| Backend | PASS | Production resolver GPT-only; Local candidates empty |
| Persistence | PASS | Cert map `c88e12ef-…` background `a34fe381-…`, `geometrySource=designed` after generate |
| Runtime | PASS | GPT Image 2 (Kie). No Comfy Local Atlas / Qwen / FLUX / MoGe Express design job |
| Result | PASS | New Atlas on cert map |
| Reload | PASS | Playwright Save/reload isolation; production Atlas unchanged |
| Downstream | N/A | ERS / Scene Creator handoff not in this cleanup |

Automatic NO-GO checks: production Atlas still `9f7d4571-…`. Historical Local cert map not overwritten. Studio API recycled without `--force` Desktop Comfy.

---

## Manual review

1. Open `http://127.0.0.1:5173/` → Adept Stability Cert → Co-Director → Spatial Map.
2. Confirm Atlas Engine GPT Image 2 and no Local/API or Interior/Exterior.
3. Production default map should be Supplementary View Assist Cert with the existing Atlas.
4. API-Only GPT Image 2 Cert holds the new designed Atlas `a34fe381-…`.
