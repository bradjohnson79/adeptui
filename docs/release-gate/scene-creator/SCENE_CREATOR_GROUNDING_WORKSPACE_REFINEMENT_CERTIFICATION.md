# Scene Creator Production Grounding + Integrity

**Date:** 2026-08-16  
**Branch:** `beta`

```text
Implementation certification:    GO — PRODUCTION GROUNDING + INTEGRITY (already certified; not reopened)
Hosted deployment certification: PENDING — this closure (not yet proven on Vercel)
Program-wide Scene Creator:      NOT ALL-GREEN — Localized Add remains NO-GO
```

| Milestone | Status |
| --- | --- |
| Scene Spatial Profile | GO |
| CD → Scene Creator Handoff | GO |
| ERS 2K Production Context | GO |
| Workspace Refinement | GO |
| Production Grounding + Integrity | GO |
| Hosted Grounding Deployment | PENDING |
| Localized Add | NO-GO |

**HEAD (committed):** `c34cdfe55633430f3e982749013684ee07ff9917` (Pass 1/2 ship). Grounding work is in the working tree on this branch until the deployment-closure commit.  
**Hosted UI:** `https://adeptui.vercel.app` (implementation certified against production `studio-web` dist preview `:4173`; hosted SHA is this closure)  
**Studio API:** `http://127.0.0.1:8758/` `/api/health` **200**  
**Preview:** `http://127.0.0.1:4173/` with `STUDIO_API_PORT=8758`  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` (reused; never `POST /api/projects`)

This is the single governing document for Scene Creator production grounding + integrity (Law 30). It does **not** rewrite:

- `SCENE_ERS_2K_PRODUCTION_CONTEXT_CERTIFICATION.md` (Pass 1 **GO**)
- `SCENE_CREATOR_WORKSPACE_REFINE_CERTIFICATION.md` (Pass 2 **GO**)
- `SCENE_CREATOR_FINAL_PRODUCTION_CERTIFICATION.md` (Add still **NO-GO**)
- `SCENE_SPATIAL_PROFILE_RESET_CERTIFICATION.md`

Do not resurrect `:8760`. Do not redesign Scene Creator. Do not invent Draft multi-ref graphs.

## Verdict

```text
GO — SCENE CREATOR PRODUCTION GROUNDING + WORKSPACE REFINEMENT CERTIFIED END TO END
```

Consumption law: an attractive café that silently dropped Korri, the cup, ERS, Spatial Map, or CD context is a fail. Proof is the provider request and the graph-loaded file, then the pixels.

## Certified pixel capacity (unchanged)

| Family | Pixel character/prop/ERS | Multi-ref | Certified path |
| --- | --- | --- | --- |
| Qwen 2512 | NO | NO | `qwen2512.txt2img` only |
| FLUX | YES — one source | NO | `flux.img2img` Certified |
| Z-Image | YES — one `reference_image` | NO | `zimage.ref_edit` Certified |

Character wins the single slot. Prop + ERS stay `semantic_only` + advisory. Qwen + selected Spatial Profile + required visual refs **blocks** generate and recommends Z-Image. No silent Qwen → Z-Image.

## Phase 1 — live drop site (historical)

Preview job `9e5640e6-0774-499f-96ae-5ce1c8639128` loaded Korri casting `b6ab91dd-…` on `zimage.ref_edit` at 512×288, but `imageIntent.referenceIds` dumped ~35 sheet/prop/ERS ids the graph never opened. Cup + ERS pixels stopped at the one-slot graph. Generic human/cup/café takes were historical (profile unset / old candidate), not the current packet compile.

## Phase 2 — Reference Packet

Runtime compiler `studio-api/app/scene_creator/reference_packet.py` (no new table). Enqueue collapses graph refs to `consumedAssetIds` only.

Live D Preview after the fix:

| Field | Value |
| --- | --- |
| Job | `6b86b9f2-5ec1-4d2a-be6a-e677711021f4` **done** |
| Candidate | `333656ed-dad5-42e0-949f-d29af4d05e5d` |
| Shot | `88539183-6fd2-495a-aa48-e406a3653cd5` |
| `purpose` / pixels | `scene_shot_preview` **512×288** |
| Workflow | `zimage.ref_edit` |
| `sourceAssetId` / `referenceIds` | **only** Korri casting `b6ab91dd-9d0a-4e4b-98b4-b26d268950dc` |
| Packet | character `consumed`; cup `semantic_only`; ERS `semantic_only` |
| Integrity | `advisory` fingerprint `de175fbcbc8a2d24` |
| Wall | ~18.7 s (created 07:02:09 → updated 07:02:28) |

Qwen grounded Preview (same shot, profile selected) returned **400**: “This generator cannot use the character and prop pictures already chosen. Choose Z-Image to keep those pictures.” No silent T2I, no family switch.

Hydrate with `spatial_profile_id` now persists Spatial Profile selection so Preview/Final use the same profile the GET overlay showed. Reset Workspace still clears selection (`workspaceReset`).

## Phase 3 — A/B/C/D (consumption, not prettiness)

Same Schnick line. Diagnostic modes are compile-only (no four product buttons).

| Mode | Graph-loaded file | Result |
| --- | --- | --- |
| **A** prompt only | none | `referenceIds=[]` |
| **B** ERS-only | ERS `79a55177-…` | café plate in the single slot; Korri omitted |
| **C** character | Korri `b6ab91dd-…` | identity consumed; ERS semantic |
| **D** full packet | Korri `b6ab91dd-…` only | cup + ERS `semantic_only`; live job `6b86b9f2-…` |

Independent visual of D (`imagegen_edit_94fe190c.png`): extreme close-up of hands holding a glass with green liquid in a café, ceramic cup in the foreground. **Face is out of frame because Camera 1 is ECU**, not because Korri was dropped — the graph loaded `b6ab91dd-…`. Cup likeness in this frame is prompt/spatial semantic, not a second pixel slot (Certified multi-ref does not exist). Honesty **PASS**. Inventing a prettier café by putting ERS in the only slot would have been **FAIL**.

## Phase 4–7 — workspace

Existing panes, Reset Layout, 3D Camera Preview/Final (same handlers), take ×, and Reset vs delete still hold. Playwright `scene-creator-workspace-refine.spec.ts` **1 passed** (5.8s) against `:4173` + `:8758`.

Take delete refuses when `take_memory.lastTimelineAssetId` matches the candidate asset: “This generation is already on the Timeline. Remove it from Timeline before deleting it here.”

## Phase 8 — acceleration

**NO CHANGE.** Final quality was not cut. Re-measured:

| Family | Condition | Observed | Note |
| --- | --- | --- | --- |
| Z-Image | Grounding Preview 512×288 | **~18.7 s** warm (`6b86b9f2-…`) | Turbo 8 steps already |
| FLUX | 1024 img2img / region_edit | **31–45 s** (n≥6 done) | Load-dominated; 512 not faster in Pass 2 |
| Qwen 2512 | ERS 2K 2560×1440 | **~91 s** | Pass 1 native path |

## Phase 9 — integrity

Layer A `SceneCreatorReadiness` on the existing workspace GET:

- Z-Image Schnick shot: `status=advisory`, ticks Character ✓ / Prop ⚠ / Environment ⚠ / Spatial ✓. Green “Production integrity verified” is **not** shown.
- Qwen Schnick shot with the same bound assets: `status=blocked`, ticks fail, Preview/Final gated.

Layer B compact CD JSON via existing Ollama generate, cached by fingerprint, 8s timeout. LLM-down → `llm_unavailable` / “Production connections verified” + creative cross-check unavailable; generate still allowed if Layer A passes. LLM cannot invent a missing asset into a pass. `productionIntegrity.status/fingerprint` stamped on `creativeContext`.

Hydrate GET stays Layer A (fast). Preview/Final invoke Layer B immediately before enqueue.

## Tests

- pytest `test_scene_creator_grounding.py` + cinematographer / spatial profile / attach projection: **50 passed** (grounding file **15 passed** on the final rerun)
- vitest caption / contracts: **18 passed**
- Playwright workspace refine (integrity caption, ticks, panes, Reset): **1 passed**

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — Spatial Profile, ticks, Preview/Final, take ×, Reset |
| Frontend | PASS — CD caption + integrity line + ticks; Qwen blocked in handler; advisory still generates |
| API | PASS — existing workspace GET + cinematographer preview/final |
| Backend | PASS — packet compile; Qwen 400 when profile selected; Z-Image Korri-only refs |
| Persistence | PASS — profile persist on hydrate query; take-memory Timeline refuse; Reset keeps Library/ERS |
| Runtime | PASS — `zimage.ref_edit` loaded Korri casting file only |
| Result | PASS — consumption proven; ECU pixels match camera, not a silent identity drop |
| Reload | PASS — GET recomputes readiness; Playwright rehydrates then Reset clears caption |
| Downstream | N/A — Add remains NO-GO; Timeline delete is refuse-only |

## Manual review

1. Open `http://127.0.0.1:4173/project/2347bf46-3762-4763-86c5-4a6032522278?workspace=scenecreator&scene_id=e4550745-f0ef-44c8-99a5-ef9e20bd47d2&shot_id=88539183-6fd2-495a-aa48-e406a3653cd5&spatialProfileId=792376c5-013c-51dd-8d3a-dae5834ae77e`
2. Confirm “Co-Director production data loaded”, an **advisory** integrity line (not a fake green verified), and Character ✓ / Prop ⚠ / Environment ⚠.
3. Qwen in the generator control must not Preview as grounded. Z-Image Preview must keep Korri in the only picture slot.

Studio API: `http://127.0.0.1:8758/`

## Limitations

- Hosted Vercel frontend is **not** a new SHA; integrity caption/ticks live in `:4173` dist + `:8758`.
- Cup and ERS **pixels** are not loaded on Certified Z-Image/FLUX (one slot). The UI tells that truth (⚠). That is not a milestone fail.
- ECU Preview `6b86b9f2-…` does not show Korri’s face; identity is proven by the loaded file, not by a recognizable portrait in this framing.
- An earlier Qwen Preview (`158e55a6-…`) ran while Spatial Profile selection was still **Reset** (prompt-only desk). After persist-on-hydrate, the same Qwen request is 400.
- Shot `88539183-…` was briefly switched to `qwen2512` during that ungated test and restored to `zimage`.
- Layer B is 8s-bounded; a slow Ollama falls back rather than hanging Preview.
- Add / nano-banana remains **NO-GO**. Draft `qwen.multi_reference` was not enabled.

## Files

- `studio-api/app/scene_creator/reference_packet.py`
- `studio-api/app/scene_creator/readiness.py`
- `studio-api/app/scene_creator/integrity.py`
- `studio-api/app/scene_creator/service.py`
- `studio-api/app/codirector/entity_resolver.py`
- `studio-api/tests/test_scene_creator_grounding.py`
- `studio-web/src/components/CoDirector/SceneCreator/productionContextStatus.ts`
- `studio-web/src/components/CoDirector/SceneCreator/SceneCreatorCore.tsx`
- `studio-web/src/components/CoDirector/SceneCreator/useSceneCreator.ts`
- `studio-web/src/components/CoDirector/SceneCreator/types.ts`
- `tests/e2e/scene-creator/scene-creator-workspace-refine.spec.ts`
