# Co-Director Context Leak + Scene/Prompt Ownership Repair

Governing report for this mission. Historical: `UNIVERSAL_SCENE_INTELLIGENCE_COMPLETION.md` remains historical and is not cited as current truth for leak/prompt ownership.

## Verdict

**NO-GO**

Implementation, unit/API, disposable Playwright, and Scene 3 CD-owned regression are **LIVE VERIFIED**. The mission gate also requires **Kimi K3 + GLM 5.2 + GPT-5.6 Sol** all AGREE. Those three peer reviews could not be launched (`Other Models usage limit reached`). Grok was not used as a substitute. Missing AGREE = NO-GO.

## Identity

| Field | Value |
|---|---|
| Branch | `feat/character-creator-final-closure` |
| Starting / HEAD SHA | `64724a531d297ebe62ee074a279cb75ba07c5731` (working-tree repair, uncommitted) |
| Local creator UI | `http://127.0.0.1:5173/` |
| Studio API | `http://127.0.0.1:8758/` (`/api/healthz` 200) |
| API recycle | `oldPid=21096` → `newPid=20036` |
| COMFY BEFORE | PID `45768`, healthy, ~32.3 GB free |
| COMFY AFTER | `:8188` healthy, PID unchanged (`unchanged=True`), ~30.7 GB free |
| COMFY RESTARTED? | **NO** |

## Scope (done)

Cursor inspected and repaired Co-Director wiring only. Scene 3 was not manually finished. PoseCraft / Spatial Map implementations were not deleted. Cinematic templates were not expanded. Comfy `:8188` was not restarted.

## Root-cause repairs

### Failure A — leaked platform prose

- Turn-intent gate (`studio-api/app/codirector/routing/turn_intent.py`) classifies `timeline_prepare` / `scene_revision` / `production_retry` vs `platform_question` **before** knowledge intercept.
- Quoted dialogue (`CADE: "Where is the Adept?"`) is stripped so `?` is not a platform question.
- Sync + stream (`service.py`) skip `knowledge_reply` / `render_knowledge_context_block` on production turns.
- Active-scene Retry / revision is forced onto `timeline.prepare_scene` before the knowledge intercept.
- `adept-platform`, `adept-system-map`, `spatial-map`, `posecraft` are `creator_chat: false` — kept on disk, excluded from creator chat retrieve + spoken replies.
- `creator_response_gate.py` last-fence denylist: Spatial Map, PoseCraft, Standalone, Image Runtime, Local Video Runtime, Adept is the filmmaking app, Environment Creator Express.

### Failure B — batch count = Timed Prompt count

- Persist one scene-level compiled prompt (`compile_generator_prompt`) as one Timed Prompt `0–duration`.
- `compile_batch_prompts` is not used for persistence (transient H3 windowing only).
- Later batches are render windows: empty `promptSegments`; duration only.
- `project_prompts_to_legacy` skips render-window batches and does not mint N Timed Prompts from N batches.
- Request builder falls back to the scene-level Timed Prompt when a batch has no own segments.
- Explicit `0–10:` / `10–20:` regions still persist multiple Timed Prompts.

## Tests (measured)

| Suite | Result |
|---|---|
| Leak unit (`test_codirector_turn_intent_leak.py`) | **passed** |
| Prompt vs batch matrix 10/1, 30/2, 30/3, 30/2+3 regions | **passed** |
| Persistence multi-batch (1 prompt, length = scene duration) | **passed** |
| Platform knowledge spoken-redirect still Environment Creator | **passed** |
| Playwright disposable A+B | **2 passed (42.3s)** |
| Playwright Scene 3 CD-owned | **1 passed (35.9s)** |

Disposable A: 30s continuous scene, 1 environment + 1 character, 2 batches, 1 Timed Prompt 0–30, no platform prose.  
Disposable B: unrelated 10s / 1 batch / 1 prompt, same contract.

## Scene 3 (inspect only)

CD processed the original request against existing scene `d0162b33-9ba6-4bb9-91b5-512a96ef965d`. Cursor did not write the prompt, seed Cade/Venture bindings, merge prompts, or patch Timeline JSON.

Observed:

- duration **30**, batches **2** (15 + 15)
- **1** compiled scene prompt (no persisted `0–15` / `15–30` window texts)
- `@CadeOConnor` + `#VentureCorridorScene` (`global_found`)
- dialogue `Where is the Adept?`
- card: Scene Prepared / MiniMax H3; no Spatial Map, PoseCraft, Standalone, Image Runtime, Local Video Runtime, or `Adept is the filmmaking app`

Evidence: `artifacts/functional-audit/universal-scene-samples/scene3-regression.json`

## Peer review

| Reviewer | Result |
|---|---|
| Kimi K3 | **NOT RUN** — other-models usage limit; no Grok substitute |
| GLM 5.2 | **NOT RUN** — same |
| GPT-5.6 Sol | **NOT RUN** — same |

## E2E TRACE

| Stage | Verdict |
|---|---|
| User action | **PASS** — CD UI chat (disposable + Scene 3 original request) |
| Frontend | **PASS** — stream POST `/api/codirector/chat/stream` |
| API | **PASS** — `timeline.prepare_scene` / sceneProduction |
| Backend | **PASS** — prepare + persist |
| Persistence | **PASS** — 1 Timed Prompt, N batches; reload kept tags |
| Runtime | **N/A** — prepare only, no generation |
| Result | **PASS** — Scene Prepared card; no leak |
| Reload | **PASS** — Scene 3 master re-read after UI reload |
| Downstream | **PASS** — Open/Generate in Timeline on card; no Timeline repair |

## Limitations

- Required peer AGREE trio unavailable in this session.
- `test_timeline_reconcile.py::test_reconcile_copies_temperature_movement_and_camera_optics` remains a pre-existing fail: legacy camera reconcile is frozen (`ADEPT_RECONCILE_LEGACY_CAMERAS`).
- Scene 3 ACTION still repeats the red-hot temperature sentence once. Out of scope (cinematic compiler quality freeze).
- Knowledge packets remain on disk for Settings/readiness; they are excluded from creator chat retrieve.

## Remaining to flip NO-GO → GO

Re-run the same question with **Kimi K3, GLM 5.2, and GPT-5.6 Sol**. Three AGREE required. Do not substitute Grok.
