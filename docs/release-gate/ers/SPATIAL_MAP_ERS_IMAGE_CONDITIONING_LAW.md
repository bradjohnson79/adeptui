# Spatial Map / ERS Image-Conditioning Law

**Status:** GOVERNING for this Express Phase 5 amendment (2026-08-16)  
**Git:** no commit, no push, no Vercel deploy  
**Branch / HEAD:** `beta` / `3980b6051269514b5b3c38eb066c005a1a5fe850`  
**Project reused:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` (no new project)

This document supersedes remaining T2I-allowed paths for Spatial Map / Atlas continuity / Environment Reference Sheets. It does **not** globally remove T2I. Brand-new Atlas creation with **no** source image remains explicit T2I (`zimage.txt2img`).

---

## Final verdict

**SPATIAL MAP / ERS IMAGE-CONDITIONING LAW — VERIFIED**

T2I is no longer the selected, compiled, or submitted operation when a source environment image exists. Live GPT Image 2 ERS on Schnick submitted `gpt-image-2-image-to-image` with a public file URL for the authoritative source. Qwen ERS remains `qwen2512.ref` (`LoadImage` → `TextEncodeQwenImageEdit`). Visual Canon is honestly `unavailable` and did not replace I2I.

This verdict does **not** by itself issue Express `READY FOR VERCEL DEPLOYMENT`. Pixel same-set leftover from Qwen Phase 2 remains a listed limitation.

---

## Why GPT used to resolve to T2I

Three cooperating defects — not a missing Kie adapter. `KIE_IMAGE_I2I_BY_DOCK["gpt-image-2-kie"]` was already `gpt-image-2-image-to-image`.

1. **UI pinned T2I.** `ERS_GPT_OFFICIAL_ID = "gpt-image-2-text-to-image"`.
2. **Handler stripped pixels then lied.** `_force_ers_honest_t2i` popped `sourceAssetId`, stamped `operationIntent=text_to_image`, appended “not pixel image-to-image”, then later reattached `input_urls`. Compile’s Kie route used `i2i = bool(source_asset_id or edit)` → official stayed T2I. **CDX-035.**
3. **Atlas continuity was T2I.** `atlas_generate` always pinned `zimage.txt2img` even when a source photo existed.

Dispatcher also dropped `forceWorkflowKey` / `lockModelFamily` (**CDX-039**). GPT eligibility was “Kie ready” only, not I2I.

---

## Contract (binding)

When Spatial Map / ERS / Atlas **already has** an environment plate:

- One `authoritativeSourceAssetId` (original environment first, then Atlas) rides the request for the whole job.
- Qwen → `qwen2512.ref`. If that workflow is unavailable → **block**. No `qwen2512.txt2img`.
- GPT Image 2 → `gpt-image-2-image-to-image` + `input_urls` from `public_api_base_url/api/assets/{id}/file`. If I2I or the public URL is unavailable → **block**. No `gpt-image-2-text-to-image`.
- No silent provider swap. No prompt-only “use this image”.
- UI provenance: `GPT Image 2 · Image Edit` / `Qwen Image · Reference`. Never “Text to Image” for these ops.

True no-source Atlas creation remains T2I. ERS without a source image cannot execute.

---

## Qwen ERS

| Gate | Evidence |
|---|---|
| Selected operation | `qwen2512.ref` (`forceWorkflowKey`, `lockModelFamily`). Dispatcher now forwards both. |
| Source asset | Authoritative id = original then Atlas. Schnick original `4d3062e8-8c30-4230-8376-bc25d1d4f735` (`Korri Coffee House.png`, Comfy `studio/atlas_shot.png`). |
| Runtime image input | Graph still wires `LoadImage` node 5 → `TextEncodeQwenImageEdit` 6/7 (`image: [5,0]`) → `KSampler` pos=`[6,0]` neg=`[7,0]`. Registry `qwen2512.ref` **Certified**. |
| Live graph proof | **Retained** from Phase 2: job `588fc5ac-252e-4b12-89d2-0d7a35dd183d`, Comfy prompt `496c9b44-d7f6-4259-91b8-cb6c09d17224`, `LoadImage.image=studio/atlas_shot.png`. This packet did not re-run a GPU Qwen sheet. |
| Output | Phase 2 Library `c1b26209-0480-432e-8328-b1cb8e10bc85` — **not** the Schnick café visually. Limitation retained. |

Tests: T2I-ready + I2I unavailable → ERS blocked; I2I ready → `qwen2512.ref`; source reaches `LoadImage` + encoder.

---

## GPT Image 2 ERS

Live Schnick run after API restart with this packet’s code (no new project):

| Gate | Evidence |
|---|---|
| Selected operation | UI/handler pin `kieImageModelId=gpt-image-2-image-to-image`, dock `gpt-image-2-kie`. Execution `deed265e-fe05-4a39-ae6f-e0c41517bf39`. |
| Source asset | `authoritativeSourceAssetId` / `source_asset_id` / Library parent = `4d3062e8-8c30-4230-8376-bc25d1d4f735`. |
| Hosted image input | Job `1831766c-9205-4018-ac04-f483cf0f005d` `kieCreateTask`: **model** `gpt-image-2-image-to-image`; **input_urls** `https://api-beta.adeptui.org/api/assets/4d3062e8-8c30-4230-8376-bc25d1d4f735/file`; **taskId** `ecdf607ae91888e75a0cc62b76076597`. `gpt-image-2-text-to-image` **absent**. Prompt lie “not pixel image-to-image” **absent**. |
| Output | Job **done**. Library `4330d965-9dca-4af4-99fc-a01dc1baf538` (`codirector_ers_deed265e_sheet`, parent `4d3062e8-...`). Sheet `db095959-5678-4f11-98d1-e93e0810d119` composite updated. Observed sheet is a labeled Schnick Coffee / Korri’s Coffee House ERS. Same-set scoring vs the photo is **not** this law’s binary. |

Public file URL was HTTP 200 (`image/png`) before submit. Kie fetched that URL; metadata/prompt “use this image” was not accepted as proof.

---

## Atlas continuity

| Mode | Operation |
|---|---|
| No source image | Explicit T2I creation: `zimage.txt2img`. Legal. |
| Source / `attachment_asset_ids` present | Qwen `qwen2512.ref` + `sourceAssetId`, or GPT `gpt-image-2-image-to-image` + `input_urls`. Never `zimage.txt2img`. Spatial Map generate/replace now passes the original environment / background asset as attachments. |

---

## Visual Canon

Retried `POST /api/vision/environment-canon` on Atlas `caa72759-d965-41f9-b1d5-77cdcf9b9614` via `chat_kie` / `gemini-3-pro`.

**Result:** `availability=unavailable`, `unavailableReason=HTTP 200` (provider returned HTTP 200 with empty chat content). Not TLS this retry. Canon text **did not** replace I2I. Pixels were still required and were submitted.

Sheet provenance `semanticGate.verdict=NOT_VERIFIED` (`vlm_error`) — advisory, honest.

---

## Tests

Backend (law suite): **62 passed**  
`tests/test_qwen_i2i_ers.py` `tests/test_ers_image_product.py` `tests/test_ers_2k_context.py` `tests/test_ers_scene_intent_grounding.py` `tests/test_atlas_generate_i2i.py` `tests/test_image_product_execution_pin.py`

Kie create-task / catalog (includes I2I model assertion): **passed** (`tests/test_kie_image_catalog.py`).

Frontend: **19 passed**  
`ersGenerator.test.ts` `ersGenerator.eligibility.test.ts` `useErsGeneration.test.ts`

`studio-web` `tsc -b`: **exit 0**. Production build: **passed**. Dist contains `gpt-image-2-image-to-image`.

Existing T2I assertions for ERS were **flipped** to the law (not weakened). Character / generic T2I catalog tests still expect T2I as the default dock mapping — T2I was not globally removed.

---

## CDX re-verify (this packet)

| ID | Prior | Now |
|---|---|---|
| CDX-035 | Prompt said “not pixel I2I” while URLs attached; compile stayed T2I | **FIXED + LIVE VERIFIED.** createTask model is I2I; `input_urls` are the public source file; T2I Market id not submitted. |
| CDX-039 | Dispatcher dropped `forceWorkflowKey`; eligibility ignored I2I | **FIXED** in dispatcher + `isGptImage2I2IReady` / Qwen I2I block. Tests assert the kwargs. |
| Atlas source lineage | Always `zimage.txt2img` | **FIXED** for source-present Atlas; T2I only when there is no plate. |

Remaining Phase 5 CDX ids (012–015, 019, 020, 028–032, 037, 038, 042, 072) are **not** closed by this law.

---

## Limitations (honest)

- Qwen Phase 2 2K sheet is still not the Schnick café. This packet did not redesign whole-sheet ERS.
- Visual Canon VLM remains unavailable (empty Gemini content). Canon cannot be cited as architecture lock.
- Authority split remains: ERS pixels prefer the original photo; Visual Canon router still requires the Atlas, which is a different building than the photo.
- `edit_op` on the GPT job commit is labeled `edit` in worker messaging (`ImageGen (edit) complete`); the Market operation submitted was **image-to-image generate**, not T2I.
- Beta stop script did not own the live `:8758` uvicorn (started outside supervisor). API was restarted in-place so this packet’s Python loaded. `:8760` continues to serve `studio-web/dist` via the existing proxy. No Vercel.

---

## E2E TRACE

| Stage | Result |
|---|---|
| User action | GPT Image 2 selected for Schnick ERS (`ers.generate`) |
| Frontend | Pins `gpt-image-2-image-to-image` (built dist) |
| API | `POST /api/codirector/projects/…/executions` → execution `deed265e-…` |
| Backend | Handler keeps `source_asset_id`, sets `input_urls`, refuses T2I official |
| Persistence | Job params + Library asset `4330d965-…` parent `4d3062e8-…`; sheet composite updated |
| Runtime | Kie createTask `gpt-image-2-image-to-image` + public file URL; task `ecdf607ae91888e75a0cc62b76076597` |
| Result | Job done; ERS PNG in Library |
| Reload | Sheet `db095959-…` `ers_composite_asset_id=4330d965-…` |
| Downstream | Pixel same-set vs photo **not** certified here; Visual Canon unavailable |

Qwen path: **PASS** (graph + Phase 2 live retain). GPT path: **PASS** (createTask pixels). T2I path for continuity: **absent**.

---

## Beta (manual review)

- Creator UI: `http://127.0.0.1:8760/`
- Studio API: `http://127.0.0.1:8758/` (`/api/health` 200)

No commit / push / Vercel in this packet.
