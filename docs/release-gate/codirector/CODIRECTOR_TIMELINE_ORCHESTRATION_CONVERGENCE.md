# Co-Director Timeline Orchestration Convergence

**Governing document for this milestone.** Historical Co-Director reports remain historical (Law 30).

| Field | Value |
| --- | --- |
| Project | Cade Scenes `fb24ff0f-8772-4d50-a602-ac69d14b5a6b` |
| Scene | Establishing Shot `c6e407e8-122b-45cf-adb2-ad8e485b3034` |
| Shot / BatchBlock | `bb_734b09c1124b` |
| Branch | `feat/character-creator-final-closure` |
| HEAD (committed baseline) | `99665cf76693e359cedc60c50c4405daf1b4e3a1` |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |
| Evidence | `artifacts/release-gate/codirector-timeline-scene-production/` |

## Scope of this GO

**Co-Director orchestration: GO.**  
**Reference persistence / Timed Prompt hydration:** not certified here. That gate is `docs/release-gate/timeline/TIMELINE_REFERENCE_PERSISTENCE_HYDRATION_CERTIFICATION.md`.

## Final verdict

**GO**

Natural-language Cade request → Co-Director preparation events → canonical reference IDs → MiniMax H3 knowledge compiler → real Timeline BatchBlock → shared `submit_batch_generation` → live MiniMax H3 job `c654dc29-2610-4183-872d-b4ed34aef4e7` (Comfy prompt `a69a1aa0-6bb7-4d3b-bf0b-1092518a266a`) → valid video asset `7dc7f73d-bd4b-426b-9835-4090d16d2436` on the same shot.

This is not a UI-only repair.

## Root causes

The workflow was disconnected in several places at once:

1. **Wrong capability.** Timeline scene-building language was stolen by image generation, ERS generate, or `timeline.generate_shot` handoff. Chat talked about the scene but never created a BatchBlock.
2. **Dead Approve Generation.** `timeline.generate_shot` returned a PREVIEW storyboard-style handoff. Approve re-ran the handoff and 409'd. Nothing called `submit_batch_generation`.
3. **Fake generation status.** Execution cards said `Generating shot — 0/1 complete` from child-job placeholders while no GPU job existed.
4. **No shared SceneSpec.** Prompt, refs, duration, and generator lived in chat prose, not Timeline master fields the workflow resolver reads.
5. **Generic prompt dump.** User prose was forwarded instead of a MiniMax H3 compiler using generator knowledge.
6. **Chat dispatch gated only by operational-agent flag.** A later `should_act_timeline` bypass is now explicit so `timeline.prepare_scene` always dispatches.
7. **Re-prepare unique-constraint crash.** Re-attaching Earth Horizon poisoned the DB session; chat died after `route_decision` with no execution card.

## Before / after call graph

### Before (broken)

```text
CoDirectorChat.submit()
  → classify (image.generate | ers.generate | timeline.generate_shot handoff)
  → GenerationQueueCard "Approve Generation"
  → approveExecution() re-runs handoff
  → 409 / 0/1 Generating with no job
  → Timeline shot never created or never submitted
```

### After (authoritative)

```text
CoDirectorChat.submit()
  → classify_generation_authority / classify_intent
  → timeline.prepare_scene
  → prepare_production_request()
      → parse_scene_intent()
      → resolve_project_references()
      → validate_scene_spec_against_generator()
      → compile_generator_prompt()          # MiniMaxH3PromptCompiler
      → create_or_update_shot_from_spec()   # add_batch / patch_batch / scene_references.attach
  → SceneProductionCard (preview, not Generating)

USER clicks Generate in Timeline
  → approveExecution(plan_only=False)
  → generate_prepared_scene()
  → director_timeline_w46.orchestrator.submit_batch_generation()

Timeline Generate button
  → POST /scenes/{id}/batches/{id}/generate
  → submit_batch_generation()               # SAME function

JOB COMPLETES
  → start_completion_watcher
  → apply_shared_completion
  → candidate + visual clip on the same BatchBlock
```

## Existing systems reused

- Timeline `add_batch` / `patch_batch` / `store.save_master` (BatchBlock is the shot)
- `scene_references.attach` (canonical binding IDs)
- `submit_batch_generation` (only video generate path)
- MiniMax H3 adapter `minimax-h3-t2v-local` + knowledge markdown via `load_video_generator_knowledge`
- Generator capability registry / request builder (duration, 21:9 canvas, megapixels)
- Co-Director execution packs + SSE `execution_status`
- Prop Creator visible props + Library environment fallback

## New modules

`studio-api/app/codirector/production/`

- `contracts.py` — `SceneProductionSpec`, `PreparationEvent`, `ResolvedReference`
- `intent_parser.py`
- `reference_resolver.py`
- `generator_validator.py`
- `prompt_compiler.py` — MiniMax-specific compiler, not generic concat
- `timeline_builder.py`
- `orchestrator.py` — `prepare_production_request` / `generate_prepared_scene`
- `errors.py`

Handlers: `timeline_prepare_scene.py`, rewritten `timeline_generate_shot.py`.

UI: `SceneProductionCard.tsx` replaces Approve Generation for `plan_data.sceneProduction`.

## Files changed

### New

- `studio-api/app/codirector/production/*`
- `studio-api/app/codirector/capabilities/handlers/timeline_prepare_scene.py`
- `studio-web/src/components/CoDirector/SceneProductionCard.tsx`
- `studio-api/tests/test_codirector_scene_production.py`
- `tests/e2e/codirector/codirector-timeline-scene-production.spec.ts`
- this document

### Wired / repaired

- `studio-api/app/codirector/capabilities/handlers/timeline_generate_shot.py`
- `studio-api/app/codirector/capabilities/registry.py` — `timeline.prepare_scene`
- `studio-api/app/codirector/routing/generation_authority.py`
- `studio-api/app/codirector/routing/unified_intent.py`
- `studio-api/app/codirector/service.py` — `should_act_timeline` + follow-up dispatch
- `studio-api/app/codirector/execution/dispatcher.py` — `preparationReady` → PREVIEW, never QUEUED
- `studio-api/app/codirector/execution/status_messenger.py`
- `studio-web/src/components/CoDirector/CoDirectorMessage.tsx`
- `studio-web/src/components/CoDirector/liveExecutionSync.ts`
- `studio-web/src/components/CoDirector/types.ts`
- `studio-web/src/styles.css`
- `studio-api/app/director_timeline_w46/generation/adapters/minimax_h3_local.py` — 21:9 listed
- `studio-api/app/director_timeline_w46/generation/request_builder.py` — MP + non-16:9 canvas
- `studio-api/app/director_timeline_w46/generation/adapters/comfy_render_scene.py` — ignore ghost `outputAssetIds`

### Removed / disabled for Timeline requests

- Storyboard **Approve Generation** is not shown when `sceneProduction` is set
- Chat no longer claims **Generating** during prepare
- Timeline prepare is not a second video submitter

## Architecture

Intent → `SceneProductionSpec` → generator-specific prompt compiler → Timeline BatchBlock → shared generate.

Co-Director does not generate video itself.

## Reference resolution evidence

| Query | Status | Type | Canonical IDs |
| --- | --- | --- | --- |
| Cade's Starfighter | FOUND | Prop Reference Sheet | Prop `6868078f-cda7-4427-8f85-fd318cf4a141` · PRS asset `6e8da820-7c8a-4dc8-825a-15c6d3bf7f59` · tag `%CadeSStarfighter` · binding `8800f37e-5756-4b3a-8d64-0fd51f847400` |
| Venture Spaceship | FOUND | Prop Reference Sheet | Prop `2601f525-…` · PRS asset `579355ac-ea5f-496a-a11d-32be5ead49a0` · tag `%VentureSpaceship` · binding `b6bc484f-7579-4eb0-ab66-b7251f052901` |
| Earth Horizon | FOUND | Environment (Library image; no ERS profile) | Asset `9a23b664-fdb6-4bab-a2ed-f4d432247d44` · tag `#EarthHorizon` · binding `f442e0f7-1591-4855-890e-c5c3cf9e9b35` |

Chat reports Earth Horizon as detected **and** states a full ERS profile was not present. It does not silently continue unbound.

Runtime sockets: `ref_image_0` Earth Horizon, `ref_image_1` Venture, `ref_image_2` Starfighter.

Scale: Venture over 1 km vs Starfighter 9.8 m → **102:1** encoded in `SceneProductionSpec.scale_relationships` and the compiled SPATIAL section.

## MiniMax H3 configuration evidence

| Field | Landed value |
| --- | --- |
| Requested generator | MiniMax H3 / `minimax-h3` |
| Adapter | `minimax-h3-t2v-local` |
| Duration | 10.0 s requested · legal 10.125 s / 243 frames @ 24 fps |
| Aspect | 21:9 |
| Quality | Megapixels 2.0 (`h3Resolution.mode=manual`) |
| Batch count | 1 |
| Mode | Reference-to-Video (`generationMode=reference`) |
| Output file | 1120×480, ~10.02 s, H.264 + AAC |

## Timeline evidence

- Shot id: `bb_734b09c1124b`
- `migrationMetadata.sourceProductionRequestId`: `4a78ab29e3ce0446f3e83155`
- Prompt persisted on `promptSegments[0].text`
- Bindings persisted on the segment
- After generate: status `CandidateReady`, `currentTakeAssetId=7dc7f73d-…`, visual clip `bbvclip_bb_734b09c1124b`

Follow-up “Make the portal larger…” updated **the same** `sceneId` / `shotId` and recompiled the MiniMax prompt (portal + slow). Existing take remained attached.

## Runtime evidence

| Item | Value |
| --- | --- |
| queueJobId | `c654dc29-2610-4183-872d-b4ed34aef4e7` |
| comfy_prompt_id | `a69a1aa0-6bb7-4d3b-bf0b-1092518a266a` |
| runtime | `adept-comfy-8188` MiniMaxH3ReferenceToVideo / ref2va |
| UNET | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` |
| Job | `running` at 25% then 83% then `done` — never labeled Generating from a click alone |
| Video | `data/assets/…/7dc7f73d-bd4b-426b-9835-4090d16d2436.mp4` · 1,343,208 bytes · ffprobe 10.016 s · 1120×480 · video+audio |

Submit used the Timeline generate route, which calls the same `submit_batch_generation` Co-Director `generate_prepared_scene` imports.

## Playwright evidence

```text
npx playwright test tests/e2e/codirector/codirector-timeline-scene-production.spec.ts --project=chromium
2 passed (6.5s)
```

- API stream: Timeline, 10 s, 21:9, MiniMax H3, Megapixels 2.0, 3 references, compiled prompt, PREVIEW, shot on master
- UI: Scene Prepared card, Generate in Timeline, Open in Timeline, **no** Approve Generation, **no** `Generating shot — 0/1 complete`

Playwright did not click Generate (would start a second GPU job after live certification already completed).

## Regression

- Unit: `test_codirector_scene_production.py` + `test_codirector_generation_authority.py` — **29 passed**
- Shared generate import test asserts `generate_prepared_scene` → `submit_batch_generation`
- Other generators still use the same Timeline generate service; only MiniMax compiler is H3-specific
- ERS “build an Environment Reference Sheet” no longer steals Timeline-use phrasing

## Phase 33 review

| Question | Answer |
| --- | --- |
| Only one Timeline generation service? | **YES** — `submit_batch_generation` |
| Does Co-Director call it? | **YES** — `generate_prepared_scene` |
| Does Timeline UI call the same service? | **YES** — `POST .../batches/{id}/generate` |
| References by canonical asset ID? | **YES** |
| MiniMax prompt compilation generator-specific? | **YES** |
| Generation state from the real job? | **YES** after submit; prepare is PREVIEW |
| Timeline shot is source of truth? | **YES** |
| Follow-up edits modify the same shot? | **YES** — live `bb_734b09c1124b` |
| Refresh restores state? | **PARTIAL** — Timeline master + execution `plan_data` persist; dedicated UI refresh walk not re-run after generate |
| Retries avoid duplicate shots? | **YES** — `sourceProductionRequestId` reuse |

## Limitations (disclosed, not blockers for this chain)

- Earth Horizon resolved as a Library environment image; no Environment Creator ERS profile existed. Chat says so.
- Scene still contains leftover unused draft `bb_121876ef0f4b` (Batch 1) from earlier create. The production shot is Batch 2 / Establishing Shot.
- Live Generate this run used the Timeline HTTP generate endpoint (same service). Co-Director **Generate in Timeline** is wired to `approveExecution` → `generate_prepared_scene`.
- Draft/fast H3 path (`draftMode=true`, `fast_generation=true`) was the configured Timeline live path.
- Actual encoded canvas was 1120×480 21:9; request builder also records a 2.0 MP 1920×1088 legal canvas note.

## Tests

| Suite | Result |
| --- | --- |
| `pytest` scene production + authority | 29 passed |
| Playwright Cade scene production | 2 passed |
| Live MiniMax H3 generate | Job done, video valid, shot attached |

## Beta / runtime

- Studio API `http://127.0.0.1:8758/api/healthz` **200** (PID 44464 after last API-only recycle)
- Creator UI `http://127.0.0.1:5173/` **200**
- Comfy `GET http://127.0.0.1:8188/system_stats` **200**

```text
COMFY BEFORE: PID 34484 / healthy
COMFY AFTER:  PID 34484 / healthy
COMFY RESTARTED?: NO
WHY?: Ordinary API recycle + UI/API orchestration. :8188 left alone.
```

## Manual review

1. Open Cade Scenes at `http://127.0.0.1:5173/`
2. Open Co-Director (timeline workspace)
3. Confirm the Scene Prepared card for Scene / Establishing Shot
4. Open in Timeline → shot `bb_734b09c1124b` with MiniMax H3, 10 s, 21:9, bound refs, Take A video
5. Do not restart Comfy
