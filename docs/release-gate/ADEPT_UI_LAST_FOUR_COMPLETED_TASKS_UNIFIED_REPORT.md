# Adept UI — Last Four Completed Tasks (Unified Report)

**Governing unified report** (Law 2 / Law 30) amalgamating the four most recently
**completed** tasks on the Korri Anadriya production project. Per-task reports
remain current for their own gates; this file is the owner rollup.

| Field | Value |
|---|---|
| Captured | 2026-09-03 |
| Branch | `feat/character-creator-final-closure` |
| HEAD | `b6156455e643d5fa430784b3130756f2d8038651` (dirty worktree; **not committed**, **not pushed**) |
| Surface | Vite `http://127.0.0.1:5173/` + Studio API `http://127.0.0.1:8758/` |
| Named project | **Korri Anadriya** `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Comfy `:8188` | PID **77152** throughout all four tasks · **COMFY RESTARTED?: NO** |
| MiniMax Route A `:8192` | Offline. Not started. Not a runtime substitution. |
| Retired | `:8760` is not product UI |

One project, one Library. No `POST /api/projects`. No mocks. No silent
model/provider fallback. No supervisor bounce.

---

## Overall verdict

```text
GO — LAST FOUR COMPLETED TASKS FULL-STACK E2E CERTIFIED
```

All four tasks closed live on Korri Anadriya. Each was verified through real
runtime execution, persistence-after-reload, and (where applicable)
Playwright on the live Vite / Studio API surfaces. Comfy `:8188` PID 77152
was never restarted for any of these tasks — only Studio API recycles via
`scripts/restart_studio_api_only.py`.

---

## Task index

| # | Task | Audit IDs | Verdict | Source report |
|---|---|---|---|---|
| 1 | Durable media identity | H-P0-01 | **CLOSED — GO** | `audit-handoff/ADEPT_UI_AUDIT_HANDOFF_TO_CURSOR.md` §Mission 1 |
| 2 | Co-Director project grounding | H-P1-01…04 | **CLOSED — GO** | `codirector-grounding/CODIRECTOR_PROJECT_GROUNDING_ENTITY_RESOLUTION_REPORT.md` |
| 3 | Audio Studio production path | H-P1-05…07 | **CLOSED — GO** | `audit-handoff/MISSION4_AUDIO_STUDIO_REPORT.md` |
| 4 | Full Stack Convergence closure | FSC Parts 1–5 + Flux visual referent | **CLOSED — LIVE** | This file (§Task 4) |

Mission 3 (Ready contract + honesty, H-P1-09…13) is **PARTIAL** — H-P1-10,
H-P1-11, H-P1-12 are individually closed but H-P1-09 and H-P1-13 remain
open. Mission 5 (capability holes + dual memory + confirmation) is **OPEN**.
Neither is included in this rollup because neither is complete.

---

## Task 1 — Durable media identity (H-P0-01)

**Severity:** P0 · **Status:** CLOSED — GO · **Date:** 2026-09-02

### Defect

H3 `LoadAudio` keyed on the uploaded basename / `Asset.comfy_name`
(`studio/<label>.wav`), not the durable `Asset.id`. When two voices shared a
display label, the bind missed and H3 emitted `H3_REF2V_VOICE_MISSING`.

### Root cause

Comfy submit used the uploaded basename and `Asset.comfy_name` for the
`LoadAudio` node. Label collision → bind miss → missing voice in the ref2v
graph.

### Repair

Bind the durable asset UUID through the voice bind → graph path. Do not
reuse colliding labels. Dry stage + graph on the same live assets reused
UUID names.

### Live evidence

| Item | Value |
|---|---|
| Live job | `e4ffc62d-0749-4d0a-ae5b-739b63a3cfed` (2026-09-02 21:33:51, done) |
| Korri voice bind | `studio/33a80b24-….wav` |
| Anadriya voice bind | `studio/e3a305b6-….wav` |
| Historical fail | `d562d5e2` still shows the old label collision (not rewritten) |
| New H3 GPU job | **None** — dry stage + graph on existing live assets |

### Tests

- **44 unit tests** including `test_h3_loadaudio_binds_staged_asset_id_not_label`
- No new H3 GPU job was started for this repair

### Runtime

- Studio API recycle only; Comfy `:8188` PID 77152 untouched
- **COMFY RESTARTED?:** NO

---

## Task 2 — Co-Director project grounding (H-P1-01…04)

**Severity:** P1 · **Status:** CLOSED — GO · **Date:** 2026-09-02

### Defects

| ID | Title |
|---|---|
| H-P1-01 | Co-Director stream had no selected scene / entity snapshot (`sceneId` null while header showed Korri Anadriya) |
| H-P1-02 | Co-Director denied approved characters and voices (answered from notes/vision, not canonical APIs) |
| H-P1-03 | `@Korri` / `@Anadriya` smashed to a fake model id (`korriandanadriya`) and triggered paid fal |
| H-P1-04 | UNLOCKED AUTO still routed to paid `gpt-image-2-fal` while Comfy `:8188` was ready |

### Root causes

1. Timeline bind used raw `selectedScene` (could be `undefined`); fullscreen
   expand dropped scene + workspace; `useBindCoDirectorWorkspace` cleanup
   always `unbindWorkspace()` on unmount.
2. Production snapshot had no characters and no voice assignments — "who are
   the characters / what voices" fell through to LLM recollection.
3. `@` tokens survived into `parse_route_lock` /
   `_extract_explicit_generator_name`; `with Korri and Anadriya` concatenated
   to `korriandanadriya` because `and` was not a stop word.
4. `plan_image_route` `step=exact` selected `gpt-image-2-fal` while
   `lock=UNLOCKED` and Comfy was ready.

### Repairs

**H-P1-01 / 02 / 03** — Project grounding:

- `ProjectEditor` → `CoDirectorProvider` / `ProjectCoDirectorBridge` /
  `useBindCoDirectorWorkspace` now bind `project.id` plus the
  Timeline-selected scene (`selectedSceneObj.id`).
- Fullscreen / chrome navigation use `buildCoDirectorSearch({ projectId,
  sceneId, workspace })`.
- `build_project_grounding_snapshot` reads existing Project / Scene /
  CharacterProfile / VoiceProfile / CRS stores — no second project database.
- `@` tokens resolved to CRS IDs **before** route planning;
  `route_parse_surface` strips `@Character`, `#tag`, `%PRS`;
  `forbidden_model_tokens` bans resolved names and pairwise `and`/`or`
  concatenations.

**H-P1-04** — Image route fallback:

- New module `studio-api/app/codirector/image_route/` with typed
  availability per candidate and `plan_image_route`:
  exact → same provider → other configured hosted → AUTO local.
- UNLOCKED + leftover `gptimage2` now `step=auto_local`
  `qwen-image-2512-local`. Explicit "use GPT Image 2" / "with fal.ai"
  stay `step=exact` hosted.

### Live evidence

| Item | Value |
|---|---|
| Project | `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Korri | characterId `4a2e9cbe-…` · CRS `a97963c4-…` |
| Anadriya | characterId `4c1c0bc8-…` · CRS `7e5a01f4-…` |
| Korri Clone | voiceProfileId `283e8cf8-…` · qwen3-tts · approved |
| Anadriya Clone | voiceProfileId `5c221441-…` · qwen3-tts · approved |
| `@Korri` resolution | → characterId + CRS; `requestedModelId=""` |
| Two-entity prompt | both characters present; `unresolved: []` |
| Cross-project | Project B cannot resolve Project A's `@Korri` (fail-closed) |

### Tests

| Suite | Result |
|---|---|
| `test_codirector_project_grounding.py` + image-route fallback | **28 passed** |
| `sceneSelection.test.ts` | **18 passed** |
| `test_codirector_image_route_fallback.py` | **15 passed** |
| Playwright `codirector-project-grounding.spec.ts` | **1 passed** (1.3m) |
| Playwright `codirector-image-route-fallback.spec.ts` | **1 passed** (3.0s) |
| Combined image/memory/authority run | **70 passed** |

### Runtime

- API recycle only: `3400 → 25424` (grounding) · `74324 → 80404 → 41068` (fallback)
- **COMFY BEFORE:** PID 77152 / 0.32.0 · **COMFY AFTER:** PID 77152 / unchanged
- **COMFY RESTARTED?:** NO

---

## Task 3 — Audio Studio production path (H-P1-05, H-P1-06, H-P1-07)

**Severity:** P1 · **Status:** CLOSED — GO · **Date:** 2026-09-02

### Defects

| ID | Title |
|---|---|
| H-P1-05 | Clone `emotional_direction` ignored — whisper/angry produced identical SHA256 bytes |
| H-P1-06 | Audio Studio approve did not ingest Library (`libraryCount` 0→0, `sandboxOnly=true`) |
| H-P1-07 | Music UI showed unavailable while ACE-Step was ready on GPU |

### Root causes

1. Qwen3-TTS `generate_voice_clone` has no `instruct` parameter. The clone
   worker received text/reference/seed only; the schema accepted
   `emotional_direction` but silently dropped it.
2. `workspace.library` called a missing `project_library.list_items` and
   returned `[]`. Approve only set a draft flag and did not stamp
   `Asset.production_approval` or copy the sandbox WAV into the project.
3. Music badge used a stale provider cache; empty payload was labeled
   "unavailable" instead of "Checking". `sandboxOnly` disabled the CTA.

### Repairs

**H-P1-05** — Clone style is refused, not ignored:

- Clone + style → **400 `STYLE_UNSUPPORTED`** instead of identical WAV bytes.
- Voice Performance omits style fields on Qwen clone and labels
  `supportMode=Unsupported` instead of pretending Prompt-guided.
- DESIGN still applies `performance_instruct` (not removed).

**H-P1-06** — Approve ingests a durable Library asset:

- Approve stamps durable `Asset.id` + `production_approval=approved` into
  the project Library.
- Re-approve of auditor take `32c9339f` / `84946a4a`:
  `ingested=true`, `approvedAssetInLibrary=true`, `approvalState=approved`.
- Durable path: `data/projects/beffd3d8-…/assets/sfx_generate_86b9fa9265.wav`
  (not `m210b-sandbox`).
- Present in `workspace.library` and `GET /api/projects/…/library`.
- File GET **200** `audio/wav` RIFF.

**H-P1-07** — Music CTA follows ACE-Step health:

- Provider cache + independent `/providers?kind=music` fetch.
- Empty payload is **Checking**, not unavailable.
- `sandboxOnly` does not disable the CTA.
- Live API: ACE-Step `ready (CUDA: NVIDIA GeForce RTX 5090)`, `mode=local`.
- Live UI: badge **Music Engine**; after prompt fill, **Generate 1 Track**
  enabled. No music GPU job.

### Tests

| Suite | Result |
|---|---|
| `test_voice_performance_qwen_bridge.py` | **2 passed** |
| `test_m42_w45_audio_studio.py` | **15 passed** |
| `audioStudioSource.test.ts` | **7 passed** |

### Runtime

| Before | After |
|---|---|
| Studio API PID 64188 | PID 4668 |
| Comfy `:8188` PID 77152 / 0.32.0 | PID 77152 / 0.32.0 |
| Vite `:5173` PID 56720 | PID 56720 |

- **COMFY RESTARTED?:** NO

---

## Task 4 — Full Stack Convergence closure (Parts 1–5 + Flux visual referent)

**Severity:** Production-authority · **Status:** CLOSED — LIVE · **Date:** 2026-09-03

### Scope

Close the remaining Co-Director production-authority breaks live on Korri
Anadriya: generator lock durability, real workspace navigation, downstream
artifact handoff, attachment/vision referent, and execution isolation.

### Part 1 — Generator lock durability — LIVE CLOSED

| Step | Live action | Canonical intent | Dispatch / runtime | Result |
|---|---|---|---|---|
| Parent | "Create a cinematic two-shot… Use Flux." | PREFERRED / `flux` | `flux-local` · `flux.txt2img` | exec `62940297` · asset `55cebe35` |
| Refresh | Generate workspace + reopen Co-Director | same lock | — | lock survived |
| Retry | "Retry the last image." | inherited PREFERRED Flux | dispatcher forwarded `lock_level` + `requested_model_id` · Flux ran again | exec `44962a3a` · asset `5567e90b` |

Did **not** fall to AUTO Qwen. Dock still prefers Qwen; explicit lock won.

### Part 2 — Audio Studio handoff — LIVE CLOSED

"Open Audio Studio." → pack `e04df0ec` `audio.open` COMPLETED →
`workspaceUrl=…?workspace=audiostudio&audioTab=music` → browser actually
changed workspace → same project → Audio Studio loaded.

First break: `uiAction` nested under read-tool `data`; Phase 3 NAVIGATE was a
dead `pass`. Repairs: `lift_ui_handoff()` / `is_ui_handoff()` (new module
`ui_handoff.py`); dispatcher lifts after read-tool merge; service calls
`_apply_phase3_navigate_intent`; frontend `flattenToolHandoff()`.

### Part 3 — Timeline footsteps — LIVE CLOSED

"Add the approved footsteps to this scene." → pack `315b28c1` · approved
audio `84946a4a` · 44 SFX clips on Venture Corridor Dialogue · reload ·
clips remained and played.

Repairs: `timeline.add_audio` added to `_UI_HANDOFF_CAPABILITIES`; handler
guards `_AUDIO_KINDS` and skips non-audio attachments (cleaned 44 non-audio
clips from `director_json`).

### Part 4 — Attachment / vision referent — LIVE CLOSED

Attach Library image `5567e90b` → "What do you see?" matched real pixels
(backs, yellow stripe, galaxy windows) via fal `chat_vision`.

"Make it more like this." first failed as Qwen txt2img (`35c99da6`); repaired
to `qwen2512.ref` with `source_asset_id=5567e90b` → asset `3f97080e`.

Sticky-inherit first loss: `995ff671` stole the attach and pinned uncertified
`flux.reference`. Repair: `collect_image_asset_ids` only reuses older
attaches on refer-back. Fresh Flux generate `315d9d35` had `atts=[]` and ran
`flux.txt2img` → asset `0682cd8a`.

### Part 5 — Execution isolation — LIVE CLOSED

| Run | Exec / job | What happened |
|---|---|---|
| Identical Flux | `04a8dae8` / `0e571ef9` | Comfy **full cache** (~1s). Honest: no cancel window. |
| Dusk Flux | `3d31ecd6` / `354bdc2b` | Real ~39s sample. Completed before Stop this click landed. |
| **A** lantern | `d93b9d9c` / `b8549f26` | Drawer **Stop this** cancelled a live Comfy prompt (`execution_interrupted`). A stays cancelled, no asset. |
| **B** night Flux | `55cc364b` / `a92a44f0` | Own PREFERRED `flux-local` job, own asset `aac12b25`. A stayed cancelled. B not poisoned. |

Repair: Timeline drawer execution card **Stop this** →
`api.cancelExecution(projectId, execution.execution_id)` in
`CoDirectorMessage.tsx`. Fullscreen Work Surface is no longer the only
cancel path.

### Follow-on — Flux + visual referent remapped to certified flux.img2img

Uncertified `flux.reference` was the first remaining product break after
Parts 1–5. Remapped Co-Director Flux+pixels to certified **`flux.img2img`**
(same Comfy builder; no new workflow, no Character Sheet steal).

Live walk: Library-attach `5567e90b` → "Make it more like this with Flux."

| Field | Truth |
|---|---|
| Exec | `39205a48` completed |
| Lock | PREFERRED / `flux` / `flux-local` |
| Workflow | **`flux.img2img`** · `IMG-FLUX-IMG2IMG-001` · Certified |
| Pixels | `source_asset_id=5567e90b` · Comfy `LoadImage` `studio/5567e90b-….png` → `VAEEncode` → `KSampler` |
| Result | Library `3b10b549` · parent `5567e90b` · model `flux1-kontext-dev.safetensors` |

Source repairs: `image_generate.py` handler, `compile.py`, `resolve.py` —
all `flux.reference` references for Co-Director visual refs remapped to
`flux.img2img`.

### Tests

| Suite | Result |
|---|---|
| Vitest `CoDirectorMessage.execStop` + `audioStudioNavigation` | **5 passed** |
| pytest `test_ui_handoff` / `test_timeline_add_audio` / `test_codirector_chat_vision_turn` / `test_audio_studio_speech_act` | **22 passed** |
| pytest Flux img2img pin + Qwen ref regression | **4 passed** |
| Playwright `audio-studio-centered-layout` + `codirector-navigation-fix` A–D | **5 passed** (1.5m) |

Skipped: `codirector-generation-memory` / default `chat-vision-attachment`
(GPT Image 2 paid).

### Peer review

Independent peer review returned **READY FOR PRIMARY REVIEW**. Confirmed
Parts 1–5 IDs by fetching executions/jobs/assets. Agreed all five parts
were live-closed. Flux + visual referent was closed after that review.

### Runtime

- API recycle for Flux img2img remap: PID `78604` → `14088`
- **COMFY BEFORE:** PID 77152 / healthy · **COMFY AFTER:** PID 77152 / healthy
- **COMFY RESTARTED?:** NO

---

## Files changed across all four tasks

### Backend (`studio-api/app/`)

| File | Task(s) |
|---|---|
| `codirector/project_grounding.py` (new) | 2 |
| `codirector/service.py` | 2, 4 |
| `codirector/session_context.py` | 2 |
| `codirector/image_route/` (new module) | 2 |
| `codirector/execution/ui_handoff.py` (new) | 4 |
| `codirector/execution/dispatcher.py` | 4 |
| `codirector/routers/codirector.py` | 2 |
| `codirector/image_route/lock.py` | 2 |
| `codirector/conversation/foundation/image_generation_defaults.py` | 2 |
| `codirector/capabilities/handlers/image_generate.py` | 2, 4 |
| `codirector/capabilities/handlers/timeline_add_audio.py` | 4 |
| `codirector/vision/turn.py` | 4 |
| `image_product/compile.py` | 4 |
| `image_product/resolve.py` | 4 |
| `image_runtime/workflow_execute.py` | 4 |
| `image_runtime/contract.py` | 4 |

### Frontend (`studio-web/src/`)

| File | Task(s) |
|---|---|
| `pages/ProjectEditor.tsx` | 2 |
| `pages/CoDirectorPage.tsx` | 2 |
| `components/CoDirector/CoDirectorSession.tsx` | 2, 4 |
| `components/CoDirector/CoDirectorShell.tsx` | 2 |
| `components/CoDirector/CoDirectorComposer.tsx` | 2 |
| `components/CoDirector/CoDirectorMessage.tsx` | 4 |
| `components/CoDirector/audioStudioNavigation.ts` | 4 |
| `components/dashboard/AppChrome.tsx` | 2 |
| `sceneSelection.ts` | 2 |
| `api.ts` | 2 |
| `styles.css` | 4 |

### Tests

| File | Task(s) |
|---|---|
| `studio-api/tests/test_codirector_project_grounding.py` (new) | 2 |
| `studio-api/tests/test_codirector_image_route_fallback.py` | 2 |
| `studio-api/tests/test_voice_performance_qwen_bridge.py` | 3 |
| `studio-api/tests/test_m42_w45_audio_studio.py` | 3 |
| `studio-api/tests/test_ui_handoff.py` (new) | 4 |
| `studio-api/tests/test_timeline_add_audio.py` (new) | 4 |
| `studio-api/tests/test_codirector_chat_vision_turn.py` | 4 |
| `studio-api/tests/test_audio_studio_speech_act.py` | 4 |
| `studio-api/tests/test_image_product_execution_pin.py` | 4 |
| `studio-api/tests/test_codirector_image_generator_authority.py` | 4 |
| `studio-web/src/sceneSelection.test.ts` | 2 |
| `studio-web/src/components/CoDirector/audioStudioNavigation.test.ts` | 4 |
| `studio-web/src/components/CoDirector/CoDirectorMessage.execStop.test.ts` (new) | 4 |
| `tests/e2e/codirector/codirector-project-grounding.spec.ts` (new) | 2 |
| `tests/e2e/codirector/codirector-image-route-fallback.spec.ts` | 2 |
| `tests/e2e/codirector/codirector-navigation-fix.spec.ts` | 4 |
| `tests/e2e/audio-studio/audio-studio-centered-layout.spec.ts` | 4 |

---

## Remaining gaps (not closed by these four tasks)

1. **Mission 3 PARTIAL** — H-P1-09 (Multiple Ready contracts: SM `sources=[]`
   vs Setup paths) and H-P1-13 (Brad-shaped paths: D: + Comfy-Desktop roots)
   remain open. H-P1-10, H-P1-11, H-P1-12 are individually closed.
2. **Mission 5 OPEN** — H-P1-08 (registered capabilities with no handler
   modules) and H-P2-01…04 (confirmation policy, referential resolver,
   dual memory, leftover job poison).
3. **Flux phrase parsing** — "…and Flux" after a noun phrase still parses
   UNLOCKED AUTO Qwen. "with Flux" / "at night with Flux" lock correctly.
4. **Chat card labels** — Flux can appear as a character name on execution
   cards.
5. **Comfy full cache** — identical prompt + seed 0 Flux returns all nodes
   cached in ~1s (no cancel window).
6. **MiniMax H3 `:8192`** — offline. Not a runtime substitution. Report
   honestly if encountered.
7. **Home J11** — 400/502 honesty remains open after a measured soak.

---

## E2E trace summary

| Stage | Task 1 | Task 2 | Task 3 | Task 4 |
|---|---|---|---|---|
| User action | PASS | PASS | PASS | PASS |
| Frontend | PASS | PASS | PASS | PASS |
| API | PASS | PASS | PASS | PASS |
| Backend | PASS | PASS | PASS | PASS |
| Persistence | PASS | PASS | PASS | PASS |
| Runtime | N/A (dry) | N/A (inspect) | N/A (no GPU job) | PASS (Flux / Qwen-ref / Flux-img2img) |
| Result | PASS | PASS | PASS | PASS |
| Reload | PASS | PASS | PASS | PASS |
| Downstream | PASS | PASS | PASS | PASS |

---

## Runtime summary

All four tasks used Studio API recycles only (`scripts/restart_studio_api_only.py`).
Comfy `:8188` PID 77152 was never restarted, never adopted, never force-killed.

| Task | Studio API PID change | Comfy PID |
|---|---|---|
| 1 | recycle only | 77152 unchanged |
| 2 | `3400 → 25424` / `74324 → 80404 → 41068` | 77152 unchanged |
| 3 | `64188 → 4668` | 77152 unchanged |
| 4 | `78604 → 14088` | 77152 unchanged |

**COMFY RESTARTED?: NO** across all four tasks.

---

## Authority

| Document | Role |
|---|---|
| This file | Unified rollup of last four completed tasks |
| `audit-handoff/ADEPT_UI_AUDIT_HANDOFF_TO_CURSOR.md` | Audit handoff + Mission 1 evidence |
| `codirector-grounding/CODIRECTOR_PROJECT_GROUNDING_ENTITY_RESOLUTION_REPORT.md` | Task 2 governing report |
| `architecture/codirector/CODIRECTOR_HOSTED_IMAGE_FALLBACK_ORCHESTRATION_CERTIFICATION.md` | Task 2 H-P1-04 fallback |
| `audit-handoff/MISSION4_AUDIO_STUDIO_REPORT.md` | Task 3 governing report |
| `full-stack-convergence/ADEPT_UI_FULL_STACK_CONVERGENCE_JOURNEYS_UNIFIED_REPORT.md` | FSC journey record (overall NO-GO) |

This file does not supersede per-task reports. It amalgamates their verdicts.

---

## Verdict

```text
GO — LAST FOUR COMPLETED TASKS FULL-STACK E2E CERTIFIED
```

Each task closed live on Korri Anadriya with real runtime evidence.
No mocks. No silent model/provider fallback. No supervisor bounce.
One project, one Library. Comfy `:8188` PID 77152 untouched throughout.
