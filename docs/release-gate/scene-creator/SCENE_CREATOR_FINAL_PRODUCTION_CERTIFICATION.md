# SCENE CREATOR FINAL PRODUCTION CERTIFICATION

**Date:** 2026-08-15 (FLUX closure run)  
**Branch:** `beta`  
**Implementation SHA:** `c45ac84` (recommend lockstep)  
**HEAD SHA:** `c45ac84`  
**Remote SHA:** `c45ac84` (`origin/beta`)  
**Vercel Production SHA:** `c45ac84` (GitHub Production deployment success)  
**Hosted UI:** `https://adeptui.vercel.app` bundle `assets/index-DJ2jRThv.js` contains `scene-creator-open-standard` and `codirector-popup`  
**Studio API:** `http://127.0.0.1:8758/` `/api/health` **200** after restart. Same process is reachable at `https://api-beta.adeptui.org`.  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`  
**Scene:** `e4550745-f0ef-44c8-99a5-ef9e20bd47d2`  
**Shot:** `2a58894b-b5d4-4e86-b068-7cd156199d98` (Shot 3, ECU Korri with cup, 1280×720)  
**Source take A:** `e0d3af5e-b63d-4974-b999-7c5543f7624e` (`imagegen_edit_5c8d7959.png`, 1280×720)  
**Camera hash:** `542a31ee7e39cb76`  
**Flag:** `SCENE_IMAGE_CORE=1`  
**GPU:** RTX 5090. Comfy `/free` only when queue empty. Certified `flux.img2img` graph not changed.

This is the single governing document for this milestone (Build Law 30). Put this FLUX closure run at the top. The historical Z-Image Add/Remove NO-GO is preserved below as an audit trail and is not rewritten.

`qwen.edit` stays unpublished. Do not resurrect `:8760`. Never `POST /api/projects`. Recommend ≠ routing: `keepCurrentAllowed` remains `true`.

## Verdict

```text
NO-GO — SCENE CREATOR PRODUCTION SYSTEM NOT CERTIFIED END TO END
```

Independent visual verifier ([Visual pixel FAIL check](3c508783-0aba-43f8-90ca-462fa840fba7)):

```text
FAILED — Add mask region shows horizontal smear/highlights/slats with no recognizable folded café napkin
```

## Blocker (this pass)

FLUX Add on Shot 3 did not synthesize a recognizable napkin. Stop rule fired. No Z-Image fallback, no graph/sampler/mask-architecture/provider work, no inheritance chain, no hosted A–T.

| Op | Family | Job | Asset | File | Mask | Visual |
|---|---|---|---|---|---|---|
| Remove | FLUX `flux.img2img` + composite | `186f04f2-81fb-4be1-a0bc-ef1d42519639` | `73f59257-b3b3-4e45-b702-8614067ff1eb` | `imagegen_edit_8673053e.png` | `mask-015368e4bf40` 1280×720 | **PASS** — left background person gone; café/window fill; Korri/cup unchanged; outside-mask mean abs diff **0.11**; `regionCompositeApplied=true`; camera `542a31ee7e39cb76` |
| Add | FLUX `flux.img2img` + composite | `31219cde-49d4-43ef-b6ca-9d99e5305b42` | `0568ad17-d58c-46ca-91d9-94bb9c5c4d1e` | `imagegen_edit_2a2972f5.png` | `mask-85e2e7342541` 1280×720 | **FAIL** — no folded café napkin; horizontal smear/highlights/slats in mask; outside-mask mean abs diff **0.10** (surroundings stable) |
| Modify | FLUX `flux.img2img` + composite | `4ec0bfc4-79dc-4f75-8938-6a6c1a9515d2` | `cf0f0279-b7be-40c0-9401-2af3123e7721` | `imagegen_edit_cfd17809.png` | `mask-1abcf087437c` 1280×720 | **PASS** — irritated Korri; identity + cup held |
| Replace | FLUX `flux.img2img` + composite | `47dbe065-e159-45c0-8fa7-c7600718b9ad` | `59f36901-b14e-46ab-9615-f3dc87f64107` | `imagegen_edit_8e6a9476.png` | `mask-99dc26459b07` 1280×720 | **PASS** — one teal mug; original gone; Korri still holds it |

Masks were encoded and persisted at **exactly 1280×720**. Job params still show Comfy generation `width/height=1024` (frozen `flux.img2img` graph) then post-download composite back to 1280×720. That is not a mask-size FAIL.

Qwen refuse: HTTP **400** (this pass).

## What this pass changed (code)

Recommend registry only. Routing unchanged. `keepCurrentAllowed: True` unchanged. Selecting Z-Image still enqueues Z-Image.

- `studio-api/app/image_core/recommend.py` — `_RECOMMENDED_FAMILY` remove/add **flux** (was zimage)
- `studio-web/.../regionEdit.ts` — `recommendOperationFamily` lockstep: all four ops FLUX
- Tests: `test_image_core.py`, `regionEdit.test.ts`, Playwright G retitled to Remove → FLUX with Keep Current

Live `GET /api/image-core/recommend?operation=remove&family=zimage` after API restart:

```json
{"recommendedFamily":"flux","keepCurrentAllowed":true,"recommended":false,"family":"zimage","supported":true}
```

Unit: Image Core **16 passed**. regionEdit vitest **24 passed**.

## Stopped (stop rule)

- Agent B inheritance chain A → Remove B → Add C → Approve C → FLUX Final D: **not run**. Add C is not pixel-valid.
- Agent C hosted focused checks + one A–T: **not run**. Pixel gate failed first. No extra A–T during this fail.

## E2E TRACE (FLUX closure)

| Stage | Verdict |
|---|---|
| User action | N/A — cert jobs via Scene Creator region-edit API (same path as UI) |
| Frontend | PASS — lockstep recommend FLUX; Keep Current still allowed (unit + live recommend). Hosted A–T not rerun this pass |
| API | PASS — recommend FLUX; Qwen 400; region-edit enqueue FLUX |
| Backend | PASS — Core `flux.img2img`; `regionCompositeApplied=true`; no silent family swap |
| Persistence | PASS — candidates/assets/masks 1280×720 on disk |
| Runtime | PASS — Comfy FLUX jobs `done` |
| Result | FAIL — Add pixels not a napkin |
| Reload | N/A — inheritance/reload GET not run after stop |
| Downstream | N/A — Final/Library/Timeline chain not run |

## Limitations

- FLUX Add on this ECU did not produce a cert-valid napkin insert. Remove on the same composite path **did** remove the left background person.
- Frozen `flux.img2img` graph still generates at 1024 then composites. Graph was not changed.
- Kie FLUX 422 remains a separate provider issue.
- Unrelated dirty timeline/avatar/`.runtime` files were **not** committed.

## Manual review

1. Open `https://adeptui.vercel.app/project/2347bf46-3762-4763-86c5-4a6032522278?workspace=scenecreator`
2. Region Edit recommend for Remove/Add should say FLUX; Keep Current (Z-Image) must still be available.
3. Inspect pixels: Remove `73f59257` vs Add `0568ad17` (napkin FAIL).

Studio API left running at `http://127.0.0.1:8758/`.

---

# Historical NO-GO (Z-Image Add/Remove pixel fail) — audit trail

**Date:** 2026-08-15  
**Branch:** `beta`  
**HEAD SHA:** `2d8eddb` (implementation) / cert commit `58dd75e`  
**Remote SHA:** `2d8eddb` (`origin/beta` at that implementation)  
**Vercel Production SHA:** `2d8eddb` (GitHub deployment success)  
**Hosted UI:** `https://adeptui.vercel.app` bundle `assets/index-rZSmStdv.js` contains `scene-creator-open-standard` and `codirector-popup`  
**Studio API:** `http://127.0.0.1:8758/` `/api/health` **200** after restart. Same process is reachable at `https://api-beta.adeptui.org`.  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`  
**Scene:** `e4550745-f0ef-44c8-99a5-ef9e20bd47d2`  
**Shot:** `2a58894b-b5d4-4e86-b068-7cd156199d98` (Shot 3, ECU Korri with cup, 1280×720)  
**Flag:** `SCENE_IMAGE_CORE=1`  
**GPU:** RTX 5090. Comfy `/free` only when queue empty. Comfy Desktop not killed.

This is the single governing document for this milestone (Build Law 30).

Historical (do not recertify from these files; verdicts unchanged):

- `SCENE_CREATOR_IMAGE_GENERATION_CORE_MIGRATION_CERTIFICATION.md` (NO-GO)
- `SCENE_CREATOR_FINISHING_RELIABILITY_CERTIFICATION.md` (NO-GO)
- `SCENE_CREATOR_EXPRESS_STANDARD_AUDIT.md` (Express-as-editor superseded)
- Deprecation map: `SCENE_CREATOR_LEGACY_GENERATION_DEPRECATION_MAP.md`

`qwen.edit` stays unpublished. Do not resurrect `:8760`. Never `POST /api/projects`.

## Verdict

```text
NO-GO — SCENE CREATOR PRODUCTION SYSTEM NOT CERTIFIED END TO END
```

Independent verifier ([Scene Creator verifier](48b46211-2260-4eaf-9072-70e46d38b646)):

```text
FAILED — Pixel Add/Remove visual FAIL (Z-Image inpaint)
```

## Blocker

Z-Image native inpaint **Add** and **Remove** did not produce pixel-valid edits on Shot 3.

| Op | Family | Jobs | Visual |
|---|---|---|---|
| Remove | zimage.inpaint | `31a1ebfd`, `c7177d1a`, `905335fe` | FAIL — extra person/lamp still present. First 1024×1024 mask left an oval seam; later 1280×720 native-mask attempts were no-ops |
| Add | zimage.inpaint | `1806d421`, `c361145f`, `074bc641` | FAIL — no meaningful insert (steam/napkin). One attempt left a dark oval blob |

Routing completed (`status=done`, Core path). Routing is not quality.

## What passed

### Architecture (flag-ON)

- Express launcher → Standard `workspace=scenecreator`. No Express generate route (`scene_creator_express_generate` 4xx).
- `region_edit_shot` → `image_core.preflight` then `image_core.generate`. Flag-ON does **not** call `_enqueue_compiled`.
- Scene does not send `forceWorkflowKey` / certified 1024×1024 as intent. Core pins after resolve.
- `GET /api/image-core/recommend` is the registry. UI consumes it; `regionEdit.ts` is fallback lockstep only.
- Structured cinematographer JSON + ERS (`ersPackageId`, `ers_composite_asset_id`, `reference_image_ids`) stay on `creativeContext`.
- `_honest_t2i_instead_of_strategy_a` is DEPRECATE (flag-OFF / draft only). Core failure = FAIL.
- Compact Co-Director popup handoff: `markOpenPopupAfterNav` + `data-testid=codirector-popup`.

### Image Core hardening

- Purposes: `scene_shot_preview`, `scene_shot_final`, `region_edit`, `final_region_edit`.
- Idempotency: `purpose + sourceAssetId + cameraStateHash + modelId + operation + edit_operation + maskAssetId`.
- Job params now persist `purpose` and `operation`.
- FLUX `flux.img2img` still does not consume a mask in the certified graph. After download, unmasked source pixels are composited back (`regionCompositeApplied=true`) so identity/camera survive. Native `zimage.inpaint` is **not** re-composited (that seam was the oval artifact).
- `"Edit operation: …"` is no longer appended to the Comfy prompt (it was burning into FLUX pixels).

### Pixel proofs that did pass

Source take A: `e0d3af5e-b63d-4974-b999-7c5543f7624e` (`imagegen_edit_5c8d7959.png`, 1280×720). Camera hash `542a31ee7e39cb76`.

| Op | Model | Job | Asset | Visual |
|---|---|---|---|---|
| Modify | FLUX `flux.img2img` | `2314d5e3-d534-4f46-a7bd-b16f99c14e36` | `358473d7-9527-47eb-a63c-43d615b2b489` | PASS — irritated expression; Korri identity; cup kept; composite on |
| Replace | FLUX `flux.img2img` | `ebd96f5c-35fa-48cd-a6e6-17e66d1c565e` | `7e663e48-d3e6-46bd-bb6f-2815d50ecf1f` | PASS — one teal mug; original gone; scene stable; composite on |
| Qwen edit | qwen2512 | — | — | PASS — HTTP 400 before enqueue |

### Inherited Final (routing)

| Job | Provenance |
|---|---|
| FLUX `2fb8cc4e-da22-4895-9837-55e5740c9071` | `purpose=scene_shot_final`, `operation=image.edit`, `source_asset_id=10094cb3-…` (approved Add D), `workflowKey=flux.img2img`, `qualityProfile=final`, `finalStrategy=A`, `fallbackApplied` unset |
| Z-Image `81aa6a90-f20c-4102-8b90-e2f266622aee` | `purpose=scene_shot_final`, `operation=image.edit`, `sourceAssetId=90fef23d-…`, `workflowKey=zimage.ref_edit`, **`drift=false`** |

Final pixels inherit the failed Add D. Lineage is correct; quality is not.

### API adapter

| Provider | Job | Result |
|---|---|---|
| Fal | `dc99ae0f-e100-4a9e-afe7-00bcc1f9f725` | **done.** `providerPreference=cloud`, `hostedModelId=flux-fal`, `falImageModelId=fal-ai/flux/dev`, `purpose=scene_shot_preview`, `operation=image.generate`. Scene → Core → direct Fal (not Comfy proxy) |
| Kie FLUX | `ebac8b21-514a-47d7-a72d-b46efbb6a101` | **FAILED** `422 The model name you specified is not supported`. Exact blocker for Kie FLUX, not “API unavailable” |

### Tests

- Image Core + region-edit + composite: **38 passed**
- Character routing + Prop parity: **64 passed**
- Hosted Playwright A–T: **20 passed (42.3s)**  
  `PLAYWRIGHT_BASE_URL=https://adeptui.vercel.app`  
  `STUDIO_API_BASE=http://127.0.0.1:8758` (same Studio API as `https://api-beta.adeptui.org`; hosted API hostname was blocked by the agent sandbox)  
  `ADEPT_BETA_TARGET=1`  
  Includes D (`data-testid=codirector-popup`).

## E2E TRACE

| Stage | Verdict |
|---|---|
| User action | PASS — Express Open Scene Creator → Standard; region-edit / Final / recommend |
| Frontend | PASS — hosted bundle `2d8eddb`; Playwright A–T 20/20 |
| API | PASS — Core recommend/preflight/generate; Qwen 400 |
| Backend | PASS — flag-ON region-edit via Core; no silent Core→legacy fallback |
| Persistence | PASS — candidates, approve D, library asset, camera hash |
| Runtime | PASS — local Comfy FLUX/Z-Image jobs complete; Fal cloud job complete |
| Result | FAIL — Add/Remove pixels not valid |
| Reload | PASS — Playwright T; GET shot candidates persist |
| Downstream | N/A — Final sourced D, but D failed quality |

## Limitations

- FLUX Modify/Replace quality depends on post-download mask composite, not a masked Comfy graph. Changing `flux.img2img` nodes would be `WORKFLOW_GRAPH_DRIFT`.
- Z-Image inpaint on this ECU did not remove a blurred extra or insert steam/napkin at cert strength.
- Kie official id mapped to `"flux"` is rejected (422).
- Unrelated dirty timeline/avatar/`.runtime` files were **not** committed.

## Manual review

1. Open `https://adeptui.vercel.app/project/2347bf46-3762-4763-86c5-4a6032522278?workspace=scenecreator`
2. Confirm compact Co-Director popup after Express → Standard.
3. Inspect Shot 3 takes: Modify `358473d7` and Replace `7e663e48` vs Add/Remove failures above.

Studio API left running at `http://127.0.0.1:8758/`.
