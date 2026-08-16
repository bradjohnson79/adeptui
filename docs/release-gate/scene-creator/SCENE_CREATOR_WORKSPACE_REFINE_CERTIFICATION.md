# Scene Creator Workspace Refine (Pass 2)

**Date:** 2026-08-16  
**Branch:** `beta`  
**HEAD:** `a1963770b91b67e078dee55f1e33b44ee1c2417b`  
**Hosted UI:** `https://adeptui.vercel.app` (this addendum certified against production `studio-web` dist preview `:4173`, not a new Vercel SHA)  
**Studio API:** `http://127.0.0.1:8758/` `/api/health` **200**  
**Preview:** `http://127.0.0.1:4173/` with `STUDIO_API_PORT=8758`  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` (reused; never `POST /api/projects`)

This is the sibling Pass 2 addendum under `docs/release-gate/scene-creator/` (Law 30). It does **not** rewrite:

- `SCENE_ERS_2K_PRODUCTION_CONTEXT_CERTIFICATION.md` (Pass 1 **GO**)
- `SCENE_CREATOR_FINAL_PRODUCTION_CERTIFICATION.md` (Add still **NO-GO**)
- `SCENE_SPATIAL_PROFILE_RESET_CERTIFICATION.md`

Do not resurrect `:8760`. Do not redesign Scene Creator.

## Verdict

```text
GO — SCENE CREATOR WORKSPACE REFINE CERTIFIED
```

## Identity trace (Korri)

Live Schnick compile after the fix (shot `88539183-…`, character `c49371ed-…`):

| Field | Value |
| --- | --- |
| `approved_casting_asset_id` | `b6ab91dd-9d0a-4e4b-98b4-b26d268950dc` |
| provider `referenceImage` / `sourceAssetId` | `b6ab91dd-…` (casting, not ERS plate) |
| ERS composite | `79a55177-10be-438b-9ae7-477c1781abe7` (last in `reference_image_ids`) |

Root cause: empty N/E/S/W caused `compile_shot_prompt` / enqueue to `insert(0)` the ERS composite, so the provider primary ref was the café sheet. Image Core then compiled `zimage.txt2img` with empty `referenceIds`.

Fix (not extra prompt text):

1. Identity refs lead; ERS composite is appended.
2. `compile_image_request` copies `referenceImage` / `reference_image_ids` into `referenceIds` (ERS T2I still strips pixels).
3. Scene shots with identity refs use certified `zimage.ref_edit` and copy the casting id onto `sourceAssetId` so the worker loads the file.

Live Preview job `9e5640e6-0774-499f-96ae-5ce1c8639128`: **done**, `purpose=scene_shot_preview`, **512×288**, `workflow=zimage.ref_edit`, `sourceAssetId=b6ab91dd-…`. ~24 s wall.

## Preview vs Final

| | Low-Res Preview | Final Quality Render |
| --- | --- | --- |
| `purpose` | `scene_shot_preview` | `scene_shot_final` |
| `quality_profile` | `draft` | `final` |
| 16:9 pixels | **512×288** | **1280×720** |
| Qwen/FLUX steps | 20 / 12 (Preview only) | family defaults (50 / 20) |
| Z-Image steps | 8 (unchanged turbo) | 8 |

Buttons: right `CinematographerPanel` **and** 3D Camera accordion (`cine-orient-preview` / `cine-orient-final`) call the same `previewCamera` / `finalRender` handlers and the same `cameraStateHash`.

## Local acceleration (measured)

Existing Studio jobs (created_at → updated_at). **Final settings were not reduced.**

| Family | Condition | Observed duration | Note |
| --- | --- | --- | --- |
| Qwen 2512 | Preview 512×288 | 8–19 s (n=4 done) | Already much faster than 1280 |
| Qwen 2512 | 1280×720 | ~32 s (n=1) | Final-class |
| Qwen 2512 | ERS 2K 2560×1440 | ~91 s warm | Pass 1 native path |
| Z-Image | 1024×1024 | 8–14 s (n=10) | Turbo 8 steps; Preview not cut further |
| FLUX | 1024×1024 | 30–36 s | Load-dominated |
| FLUX | 512×288 | ~30 s (n=1) | **No speedup vs 1024 in that sample** |

Optimization applied: Preview sampler steps for Qwen/FLUX only, plus existing draft pixels. Warm Comfy retention is the FLUX/Z-Image story. Do not claim FLUX Preview is faster from the single 512 sample.

## Delete vs Reset

- Take-strip **×** confirms, then `DELETE .../shots/{id}/candidates/{id}` removes the candidate **and** the Library asset.
- Approved takes use a stronger confirm copy.
- **Reset Workspace** still clears the desk and **preserves** Library / Spatial Profile / ERS composite (`79a55177-…`).

## Tests

- pytest: `test_spatial_map_attach_projection.py`, `test_scene_spatial_profile.py`, `test_cinematographer.py` (+ Image Core identity/ref_edit) — **33 passed** earlier; identity addendum tests **3 passed**
- vitest: pane clamp/persist, contracts, CD caption — **14 passed**
- Playwright: `tests/e2e/scene-creator/scene-creator-workspace-refine.spec.ts` against `:4173` + API `:8758` — **1 passed** (5.2s)
- Live Preview: job `9e5640e6-…` **done** with Korri casting on `zimage.ref_edit` at 512×288

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — profile select, accordion generate, layout splitters, take ×, Reset |
| Frontend | PASS |
| API | PASS |
| Backend | PASS — identity lead, draft preview, candidate delete endpoint |
| Persistence | PASS — pane localStorage; Reset keeps ERS asset `79a55177-…` |
| Runtime | PASS — live `zimage.ref_edit` Preview, Korri `sourceAssetId` |
| Result | PASS — Korri casting is provider primary ref |
| Reload | PASS — caption rehydrates from GET (Pass 1); Reset clears caption |
| Downstream | N/A — Timeline / Add not reopened |

## Limitations

- Hosted Vercel frontend is not a new SHA for this Pass 2 UI; certify against `:4173` dist + live `:8758`.
- Live GPU **Final** was not re-run this pass; Final remains 1280×720 / family default steps by contract (`purpose=scene_shot_final`, `allowDraft=false`).
- One earlier Preview (`2562f6a0-…`) failed with `Reference image required` before `sourceAssetId` was copied; that failed candidate may still be on the take strip until the filmmaker deletes it with ×.
- Qwen 2512 still has `supportsReferences: false`; pixel identity uses Z-Image `ref_edit` (Certified). Qwen scene shots stay T2I.
- Qwen may still paint extra figures in ERS environment panels (Pass 1 visual limitation).
