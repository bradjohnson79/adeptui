# Character Creator V3 — Certification

**Date:** 2026-08-24  
**Branch:** `feat/character-creator-final-closure`  
**HEAD SHA:** `b6156455e643d5fa430784b3130756f2d8038651` (working tree includes uncommitted V3 multiview remediation)  
**Governing architecture:** [`CHARACTER_CREATOR_V3_ARCHITECTURE.md`](./CHARACTER_CREATOR_V3_ARCHITECTURE.md)  
**License audit:** [`MULTIVIEW_ENGINE_LICENSE_AUDIT.md`](./MULTIVIEW_ENGINE_LICENSE_AUDIT.md)

**Live review URLs:**
- Creator UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/` (`/api/healthz` → 200 `{"status":"ok"}`)
- Retired `:8760` was not started

---

## Verdict

**NO-GO — CHARACTER CREATOR V3 MULTIVIEW ENGINE NOT CERTIFIED**

The license-cleared named adapter **runs**. Official Qwen Image Edit 2509 produced live Side / 3/4 / Back on this RTX 5090, reject unlinked a Library candidate, per-angle remake worked, approved ids persisted as `cc_v3` after reload, Co-Director `@Mira Vale` still points at Front, and a 21:9 sheet was composed.

Production certification is refused because **Back identity is not CRS-usable**. Two live Back jobs returned a true rear camera but collapsed to a flat silhouette. The approved Front on Mira Vale is also a collage, not a single figure. Official-only quality therefore fails the owner identity gate. The optional community angles LoRA was not installed (provenance deferred). Character Angles is **not** production-certified.

Wonder3D remains AGPL-blocked forever. No Flux / Krea / Qwen-as-Front silent fallback. `generate_view("back")` remains `BACK_RETIRED`.

---

## Gates

| Gate | Verdict |
| --- | --- |
| 1 Krea character-multiview role | **PARTIAL** — Krea stays in Image Generator / Prop / Setup; removed from Character Creator |
| 2 Wonder3D | **REJECTED** — AGPL-3.0 weights; never downloaded; Setup `wonder3d_multiview` never Ready |
| 3 Multiview engine feasibility | **LIVE RUN** — three Comfy jobs on `cuda:0 NVIDIA GeForce RTX 5090`; Side and 3/4 keep wardrobe/identity; **Back identity FAIL** |
| 4 Adapter / backend | **IMPLEMENTED** — `engine=qwen_image_edit_2509`; READY only if Installed + Runtime + GPU + Model + License Clear |
| 5 Frontend | **IMPLEMENTED** — Generate / Remake / Approve / Reject confirm; no Create Back View; no Wonder3D/Krea in dropdown |
| 6 Live generate / reject / remake / approve | **LIVE** on Mira Vale (`cf4437c7-…`) in Adept Stability Cert; reject Back → asset 404; remake Back → new asset |
| 7 Sheet + JSON + reload | **LIVE** — sheet `a9bce9ae-…`; `schema=cc_v3`; `jsonRevision=2`; angle asset ids survive reload; `@Mira Vale` still Front |
| 8 Playwright | **3 passed** chrome + honest-error path; does **not** certify a fresh GPU generate |

---

## Engine

| Field | Evidence |
| --- | --- |
| Engine | `qwen_image_edit_2509` (named Character Angles adapter) |
| Weights | `Qwen/Qwen-Image-Edit-2509` Apache-2.0 |
| Workflow | `qwen_edit_2509.edit` |
| GPU | `cuda:0 NVIDIA GeForce RTX 5090 : cudaMallocAsync` · VRAM total 34190458880 · free ~2.5–4.7 GB while running |
| Duration | First set ~674 s wall (model load + three sequential jobs) · Back remake ~58 s |
| Prompt IDs | Side `2cc4bb0a-…` · 3/4 `c172ddf8-…` · Back first `13fa8cd5-…` · Back remake tracked as asset `eee05279-…` |
| License URLs | https://huggingface.co/Qwen/Qwen-Image-Edit-2509 · https://github.com/QwenLM/Qwen-Image |

Images: `docs/release-gate/character-creator/evidence/cc_v3_angles/`

---

## Tests

| Suite | Result |
| --- | --- |
| `studio-api/tests/test_cc_v3.py` | **15 passed** |
| `characterV2Studio.presence.test.ts` | **3 passed** |
| Playwright V3 express / live / standard | **3 passed** (`ADEPT_BETA_TARGET=1`, Vite `:5173`, API `:8758`) |

---

## Peers

- [GLM 5.2 license/architecture](6c8aa9e6-0302-463f-81ca-1bec508d465e): **READY FOR PRIMARY REVIEW** — Wonder3D never Ready; files-on-disk ≠ Ready; named adapter, not silent fallback
- [Kimi K3 adversarial QA](35c1b2ff-6612-4cfd-ac19-f57f48ebb7f2): blocking GPU-probe CPU pass-through and non-atomic enqueue — **repaired** (`_gpu_probe` requires CUDA tokens; partial enqueue now saves started slots). Playwright live spec still does not certify a fresh generate (documented)

---

## E2E TRACE

| Step | Result |
| --- | --- |
| User action | PASS — Generate Character Angles / Remake / Reject / Approve |
| Frontend | PASS — buttons wired; disabled when engine or Front lock missing |
| API | PASS — `/multiview/generate`, `/{angle}/regenerate`, reject, approve |
| Backend | PASS — enqueue `qwen_edit_2509.edit` from approved Front |
| Persistence | PASS — angle asset ids + `cc_v3` survive reload |
| Runtime | PASS — live Comfy on RTX 5090 |
| Result | **FAIL** — Back not photoreal / not CRS-usable |
| Reload | PASS — sheet + JSON + `@Mira Vale` Front |
| Downstream | PASS — 21:9 sheet composed (includes silhouette Back) |

---

## Limitations

- Back quality failed official-only Gate 3 identity. Community angles LoRA not used.
- Mira Vale approved Front is a collage of a man; profile still says woman. Pre-existing data, not a silent model swap.
- Angle upscale is honest `UPSCALE_NOT_WIRED`.
- Playwright does not click a fresh GPU generate when angles already exist.
