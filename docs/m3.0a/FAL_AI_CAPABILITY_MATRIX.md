# M3.0a - fal.ai Capability Matrix

Generated from `studio-api/app/fal_catalog.py`. Every row is an endpoint the queue worker can
actually submit to today. Nothing here is aspirational: a model appears only once its real
fal endpoint id and argument builder exist in the repository.

| Field | Value |
|-------|-------|
| Source of truth | `studio-api/app/fal_catalog.py` (`FAL_MODELS`, `FAL_IMAGE_MODELS`) |
| API | `GET /api/fal/models` |
| Co-Director | read tool `get_cloud_render_status` |
| Date | 2026-07-27 |
| Live proof | `docs/m3.0a/FAL_AI_REAL_JOB_RESULTS.md` |

---

## 1. Video engines (wired)

Catalogue entries describe the **registered fal endpoint** on each `FalModel` (today: all
image-to-video). Argument builders may select a different endpoint for a specific request
shape; that is documented separately and is not an invented catalogue id.

| Engine id | Label | Owner | Registered fal endpoint (catalogue) | Catalogue mode | Media | Durations (s) | Default | End frame |
|-----------|-------|-------|-------------------------------------|----------------|-------|---------------|---------|-----------|
| `fal_seedance` | Seedance 2.0 (fal.ai) | ByteDance | `bytedance/seedance-2.0/image-to-video` | image_to_video | video | 4-12 | 5 | yes |
| `fal_kling` | Kling 2.5 Turbo Pro (fal.ai) | Kuaishou | `fal-ai/kling-video/v2.5-turbo/pro/image-to-video` | image_to_video | video | 5, 10 | 5 | no |
| `fal_veo` | Veo 3.1 (fal.ai) | Google | `fal-ai/veo3.1/image-to-video` | image_to_video | video | 4, 6, 8 | 8 | no |
| `fal_runway` | Runway Gen-3 Turbo (fal.ai) | Runway | `fal-ai/runway-gen3/turbo/image-to-video` | image_to_video | video | 5, 10 | 5 | no |

### Seedance text-to-video fallback (implemented + live-tested)

When `build_fal_arguments` is called for `fal_seedance` **without** a start image, the
builder falls back to the existing Seedance T2V endpoint already coded in
`fal_catalog.py`:

| Item | Value |
|------|-------|
| Status | **Implemented + live-tested** |
| Fallback endpoint | `bytedance/seedance-2.0/text-to-video` |
| Evidence | `docs/m3.0a/FAL_AI_REAL_JOB_RESULTS.md` (request id `019fa1fc-e05f-7d80-9908-e6d0c3e8d4fc`, artifact `artifacts/m30a-fal/seedance_t2v_4s_480p.mp4`) |
| Catalogue row mode | Remains `image_to_video` (registered I2V id above); T2V is the no-image builder branch |

### Image-to-video accuracy

| Engine | I2V endpoint status | Live I2V proof |
|--------|---------------------|----------------|
| `fal_seedance` | Registered I2V id in catalogue; used when `image_url` is present | **Not** live-tested in the one-job budget (T2V was the submitted job) |
| `fal_kling` | Registered I2V only; no T2V fallback in builder | Not live-tested |
| `fal_veo` | Registered I2V; builder has a separate no-image branch to `fal-ai/veo3.1` (T2V-style) that is **code-present**, not live-tested here | Not live-tested |
| `fal_runway` | Registered I2V only; no-image requests raise (needs start image) | Not live-tested |

No additional fal video endpoint ids are claimed beyond what appears in `fal_catalog.py`
and the live T2V proof above.

---

## 2. Image engines (not registered - approval queue)

`FAL_IMAGE_MODELS` is empty and `GET /api/fal/models` returns no `media_type: "image"` rows.

The following fal image families are **not registered** in this repository (approval queue /
product decision required before any endpoint id is added):

| Family | Registration status |
|--------|---------------------|
| Seedream | **Not registered** (approval queue) |
| Nano Banana | **Not registered** (approval queue) |
| GPT Image | **Not registered** (approval queue) |

No endpoint ids are invented here. An endpoint id recalled from memory is a guess; a guessed
id produces a model the settings UI offers, the Co-Director recommends, and the queue then
fails on. Still-image generation runs locally through ComfyUI
(`studio-api/app/imagegen_workflows.py`).

**To wire an image family**, three things are needed and nothing else in the stack has to
change:

1. The verified fal endpoint id (from fal's own model page) after product approval.
2. A `FalModel` entry with `media_type="image"` in `FAL_IMAGE_MODELS`.
3. An argument builder branch in `build_fal_arguments` for that family's input schema.

---

## 3. Capability dependencies

| Capability | Requires | Behaviour when unmet |
|------------|----------|----------------------|
| Any fal render | Stored fal key | Queue job fails closed; no mock or fixture output |
| Any fal render | Key accepted by fal | `FalAuthError` naming Project Settings -> Integrations |
| Engine list in UI | Nothing - catalogue is static | Always listed; usability depends on credential state |
| `GET /api/fal/usage` | Admin-scoped key | HTTP error from fal; render-only keys cannot read billing |
| Co-Director cloud advice | `get_cloud_render_status` | Reports `credentialState` and per-state guidance |

---

## 4. Per-media routing

`FalModel.media_type` exists so callers can filter without pattern-matching on ids:

- `list_fal_models()` - everything.
- `list_fal_models_by_media("video")` - the four rows above.
- `list_fal_models_by_media("image")` - empty until section 2 is satisfied.

`GET /api/fal/models` and the Co-Director read tool both surface `media_type`, so an image
family added later becomes visible everywhere without further plumbing.
