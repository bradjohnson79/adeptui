# Co-Director Project Grounding + Active Scene + Character/Voice + @Entity Resolution

Governing document for this surgical mission. AUTO image routing, retry memory, capability handlers, Comfy health, confirmation policy, Audio Studio, Timeline rendering, Character Creator, and runtime services were not repaired here.

This mission closed audit IDs **H-P1-01**, **H-P1-02**, and **H-P1-03**. Remaining audit-cell missions live in [`../audit-handoff/ADEPT_UI_AUDIT_HANDOFF_TO_CURSOR.md`](../audit-handoff/ADEPT_UI_AUDIT_HANDOFF_TO_CURSOR.md).

- Branch: `feat/character-creator-final-closure`
- Starting SHA: `b6156455e643d5fa430784b3130756f2d8038651`
- Project: Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`
- Walk scene: `b5282a4c-07eb-40db-9d5b-1512eac74dca`
- Dialogue scene: `ae8e5699-a5d8-4b9b-ad8e-0003d81d3639`
- Scene 1: `1f46b621-46f9-4b7e-8273-202a49e1ca7c`

## Verdict

**GO — CODIRECTOR PROJECT GROUNDING + ACTIVE SCENE + CHARACTER/VOICE + @ENTITY RESOLUTION E2E CERTIFIED**

A project-bound Co-Director now carries canonical project identity, the selected Timeline scene, live characters, and assigned voices. `@Korri` and `@Anadriya` resolve to CRS IDs before generation/model route planning. Entity names cannot become generator IDs. Global `/co-director` without a project remains legitimately unbound.

## SPLIT-BRAIN ROOT CAUSE

Observed, not inferred:

1. **Timeline bind used raw `selectedScene`, which can be `undefined`.** Timeline UI already fell back to `project.scenes.find(...) || project.scenes[0]`, so the shell could show a scene while the stream sent `scene_id: null`.
2. **Fullscreen expand dropped scene and workspace.** `expandToFullScreen` navigated to `/co-director?projectId=...` only. `CoDirectorPage` rebound project name and never rebound `sceneId`.
3. **`useBindCoDirectorWorkspace` cleanup always `unbindWorkspace()` on unmount.** ProjectEditor → fullscreen unmounted the project bind and briefly cleared the session to empty before the next bind.
4. **`GET /api/codirector/session-context` without `project_id` is correctly `no_project`.** The audit’s `no_project` was that unbound GET and/or the bind-clear race, not a missing Korri Anadriya project. The browser project shell was bound; Co-Director execution context was not reliably bound.
5. **Production snapshot had no characters and no voice assignments.** “Who are the characters / what voices” fell through to LLM recollection.
6. **Scene question regex missed “What scene are we working on?”** and `_active_scene` invented the first scene when `scene_id` was missing.
7. **`@` tokens survived into `parse_route_lock` / `_extract_explicit_generator_name`.** `with Korri and Anadriya` concatenated to a fake model id (`korriandanadriya`) because `and` was not a stop word and entity resolution ran beside routing, not before it. `_enrich_execution_context` also captured only the first capitalized name.

## FRONTEND PROJECT ID

`ProjectEditor` → `CoDirectorProvider` / `ProjectCoDirectorBridge` / `useBindCoDirectorWorkspace` now bind `project.id` plus the Timeline-selected scene (`selectedSceneObj.id`), not an empty `selectedScene`.

Fullscreen and chrome navigation use `buildCoDirectorSearch({ projectId, sceneId, workspace })`. Global `/co-director` without `projectId` still unbinds.

Inspectable shell: `data-project-id`, `data-scene-id`, `data-workspace`, `data-session-status`.

## STREAM PROJECT ID

`performSend` already posted `project_id: b.projectId` and `scene_id: b.sceneId` from `bindingsRef`. After the bind fix, Playwright intercepted every `POST /api/codirector/chat/stream` on Korri Anadriya as:

- `project_id = beffd3d8-791d-4adf-9c4d-681ec9d4efb0`
- `scene_id =` the UI-selected scene

Unbind now uses bind-generation tokens so ProjectEditor unmount cannot wipe a newer same-project fullscreen bind.

## SESSION-CONTEXT PROJECT ID

`GET /api/codirector/session-context` without `project_id` remains `sessionStatus=no_project` (intentional global mode).

With `project_id` + `scene_id` + `workspace=timeline` on the live project:

- `projectId = beffd3d8-791d-4adf-9c4d-681ec9d4efb0`
- `projectName = Korri Anadriya`
- `sessionStatus = bound`
- `activeSceneId = b5282a4c-07eb-40db-9d5b-1512eac74dca`
- `projectSnapshot.bound = true`

A bound stream never emits `no_project`. An unbound stream still does.

## ACTIVE SCENE AUTHORITY

Authority is the current Timeline selection (URL / persisted last selected / session), not chat history.

- Bind: `selectedSceneObj.id` + `selectedSceneObj.name`, workspace canonicalized to `timeline`.
- Snapshot `_active_scene` uses the request `scene_id` only. It does not invent the first scene.
- Scene switch updates bind + URL + shell `data-scene-id` + grounding reply.

## PROJECT SNAPSHOT AUTHORITY

`build_project_grounding_snapshot` reads existing Project / Scene / CharacterProfile / VoiceProfile / CRS stores. No second project database.

Minimum payload:

- `project { id, name }`
- `activeScene { id, name, index }` or `null`
- `characters { id, name, status, crsAssetId }`
- `voiceAssignments { characterId, voiceProfileId, engine, approval, readiness }`

Injected as `PROJECT GROUNDING` before the conversational LLM, and as SSE `project_grounding` before any answer. Grounding questions short-circuit with `grounding_reply` (no recollection).

Read-only inspect: `POST /api/codirector/projects/{project_id}/turn-grounding`.

## CHARACTER GROUNDING

Live Korri Anadriya snapshot:

| Name | characterId | status | CRS assetId |
|---|---|---|---|
| Korri | `4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed` | approved | `a97963c4-09b3-402b-8341-8f0539b4bc0b` |
| Anadriya | `4c1c0bc8-a771-4998-b652-5d549b2a2b8d` | approved | `7e5a01f4-19cc-4b6b-b323-1b2e01bbf4ad` |

Prompt: “Who are the active characters in this project?”

Live stream reply: `The active characters in this project are Anadriya and Korri.`

## VOICE GROUNDING

| Character | voiceProfileId | voiceName | engine | approval |
|---|---|---|---|---|
| Korri | `283e8cf8-3c59-4a9e-8ba9-2f7ba1535ad2` | Korri Clone | qwen3-tts | approved |
| Anadriya | `5c221441-44ae-4cae-b738-e461558b771e` | Anadriya Clone | qwen3-tts | approved |

Prompt: “What voices are assigned to Korri and Anadriya?”

Live stream reply: `Anadriya is assigned Anadriya Clone (qwen3-tts, approved) Korri is assigned Korri Clone (qwen3-tts, approved).`

## @KORRI RESOLUTION

`@Korri` → characterId `4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed`, CRS `a97963c4-09b3-402b-8341-8f0539b4bc0b`.

## @ANADRIYA RESOLUTION

`@Anadriya` → characterId `4c1c0bc8-a771-4998-b652-5d549b2a2b8d`, CRS `7e5a01f4-19cc-4b6b-b323-1b2e01bbf4ad`.

## TWO-ENTITY RESOLUTION

Prompt: `Create a shot with @Korri and @Anadriya walking through the Venture corridor.`

Live `turn-grounding` (no generation, no spend):

- tokens: `@Korri`, `@Anadriya`
- both characters present with CRS
- `unresolved: []`
- `routeLock.requestedModelId = ""`
- `routeParseSurface = "Create a shot with and walking through the Venture corridor."`

Order: parse entities → resolve both → bind CRS IDs → strip entity tokens from the model parse surface → then route planning.

## MODEL-PARSER ISOLATION

Generic classification boundary, not name special-cases:

- `route_parse_surface` strips `@Character`, `#tag`, `%PRS`
- `forbidden_model_tokens` bans resolved names and pairwise `and`/`or` concatenations
- `_NAME_STOP` includes `and`, `or`, `plus`, `with`, `via`, `using`, `by`
- `parse_route_lock_excluding_entities` is the generation-path parser
- `use Flux with @Korri and @Anadriya` still locks Flux
- `korriandanadriya` cannot be a model id

AUTO / fal / Kie selection policy was not changed.

## REFRESH

Open Korri Anadriya → select Venture Corridor Walk → refresh → ask “What scene are we working on?” / “Who is in this project?”

Playwright: Walk + Korri + Anadriya. No dependence on conversation history.

## SCENE SWITCH

Scene 1 → Venture Corridor Dialogue → Venture Corridor Walk.

After each selection, “What scene are we working on?” follows the UI `sceneId`. Live stream with Dialogue `scene_id` replied `We are working on Venture Corridor Dialogue.`

## CROSS-PROJECT ISOLATION

`resolve_turn_entities` is project-scoped and fail-closed. Project B cannot resolve Project A’s `@Korri` / `@Anadriya` or their CRS IDs. Covered by `test_cross_project_entity_resolution_fail_closed`.

## PLAYWRIGHT

`tests/e2e/codirector/codirector-project-grounding.spec.ts` on the real Korri Anadriya project. Never `POST /api/projects`.

```
npx playwright test tests/e2e/codirector/codirector-project-grounding.spec.ts --project=chromium --retries=0
1 passed (1.3m)
```

`ADEPT_BETA_TARGET=1` against `http://127.0.0.1:5173/` + `http://127.0.0.1:8758/`.

Unit:

- `studio-api/tests/test_codirector_project_grounding.py` + image-route fallback: **28 passed**
- `studio-web/src/sceneSelection.test.ts`: **18 passed**

## PEER REVIEW

| Question | Answer |
|---|---|
| Can a project-bound stream still report `no_project`? | **NO** |
| Can active Timeline scene still be null while UI has one selected? | **NO** |
| Can Co-Director deny characters that exist? | **NO** |
| Can it deny assigned voices that exist? | **NO** |
| Can one of two `@` characters disappear? | **NO** |
| Can entity names reach model/provider parsing? | **NO** |
| Is project isolation preserved? | **YES** |
| Did this repair alter image-provider policy? | **NO** |

Questions 1–6 are all NO (non-blocking). Isolation preserved. AUTO/fal/Kie policy untouched.

## FILES CHANGED

Backend:

- `studio-api/app/codirector/project_grounding.py` (new)
- `studio-api/app/codirector/service.py`
- `studio-api/app/codirector/session_context.py`
- `studio-api/app/routers/codirector.py`
- `studio-api/app/codirector/image_route/lock.py`
- `studio-api/app/codirector/conversation/foundation/image_generation_defaults.py`
- `studio-api/app/codirector/capabilities/handlers/image_generate.py`
- `studio-api/tests/test_codirector_project_grounding.py` (new)

Frontend:

- `studio-web/src/pages/ProjectEditor.tsx`
- `studio-web/src/pages/CoDirectorPage.tsx`
- `studio-web/src/components/CoDirector/CoDirectorSession.tsx`
- `studio-web/src/components/CoDirector/CoDirectorShell.tsx`
- `studio-web/src/components/CoDirector/CoDirectorComposer.tsx`
- `studio-web/src/components/dashboard/AppChrome.tsx`
- `studio-web/src/sceneSelection.ts`
- `studio-web/src/sceneSelection.test.ts`
- `studio-web/src/api.ts`

E2E:

- `tests/e2e/codirector/codirector-project-grounding.spec.ts` (new)
- `tests/e2e/codirector/helpers/audit.ts`

## DEFERRED GROK FINDINGS UNTOUCHED

1. AUTO local-first image authority (Issue 1)
2. Canonical retry / reference memory convergence (Issues 4 + 8)
3. Capability handler completeness (Issue 5)
4. Execution / status health convergence (Issues 6 + 9)
5. Action-policy consistency (Issue 7)
6. UX truth cleanup (Issues 10–12)

## E2E TRACE

| Stage | Result |
|---|---|
| User action | PASS — Timeline Walk selected; chrome Co-Director; grounding prompts; scene switch; refresh; global `/co-director` |
| Frontend | PASS — shell `data-project-id` / `data-scene-id` / `data-workspace=timeline` |
| API | PASS — stream `project_id` + `scene_id`; `turn-grounding` inspect |
| Backend | PASS — snapshot + `grounding_reply` + entity resolution before route lock |
| Persistence | PASS — selected scene survives refresh via URL + last-selected store; characters/voices from canonical rows |
| Runtime | N/A — no image job; inspect-only for `@` |
| Result | PASS — Korri + Anadriya, Korri Clone / Anadriya Clone (qwen3-tts), Venture Corridor Walk |
| Reload | PASS — scene and cast answers without chat-history dependence |
| Downstream | PASS — both CRS IDs present; `requestedModelId` empty |

## Runtime

- Local creator UI: `http://127.0.0.1:5173/` (HTTP 200)
- Studio API: `http://127.0.0.1:8758/api/healthz` (ok)
- API recycle only: PID `3400` → `25424`
- **COMFY BEFORE:** PID `77152` / health 0.32.0
- **COMFY AFTER:** PID `77152` / health unchanged
- **COMFY RESTARTED?:** NO
- **WHY?:** Ordinary API recycle. `:8188` left untouched.

## Limitations

- Grounding short-circuit covers the asked project-state questions. Other chat still uses the LLM with the injected snapshot.
- `@` inspect proved both CRS IDs and empty model id. No paid image job was started.
- Global Co-Director without `projectId` remains `no_project` by design.
