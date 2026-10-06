# Timeline Selected-Scene Persistence + Comfy Single-Owner Runtime Journey

Governing report for selected-scene persistence and Comfy single-owner. The prior Venture Corridor audio/timeline journey remains GO and is not reopened. Five-control transport + scene-switch timing is governed by `KORRI_ANADRIYA_TIMELINE_FIVE_CONTROL_TRANSPORT_SCENE_SWITCH_JOURNEY.md`.

**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `b6156455e643d5fa430784b3130756f2d8038651`  
**Review URL:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline`  
**Shareable Walk URL:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline&sceneId=b5282a4c-07eb-40db-9d5b-1512eac74dca`  
**Studio API:** `http://127.0.0.1:8758/`

## Verdict

**GO — TIMELINE SELECTED-SCENE PERSISTENCE + COMFY SINGLE-OWNER RUNTIME JOURNEY E2E CERTIFIED**

## Live IDs

| Field | Value |
|---|---|
| PROJECT ID | `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` (Korri Anadriya) |
| VENTURE CORRIDOR WALK SCENE ID | `b5282a4c-07eb-40db-9d5b-1512eac74dca` |
| SCENE 1 (first-scene fallback) | `1f46b621-46f9-4b7e-8273-202a49e1ca7c` |
| CORRIDOR ASSET | `2b1f1901-af59-4368-b1ef-64175a8d1a23` |
| DIRECTOR AUDIO | 30 `sfx_clips` + 2 lip-sync tracks (unchanged) |

No new project. No director overwrite. No Comfy workflow change. No Comfy restart.

## SCENE SELECTION ROOT CAUSE

Timeline fell back to Scene 1 after refresh because selection lived only in React `useState`. Reload started `undefined`, and `refresh()` then chose `scenes[0]`.

That first-scene choice was then **written into the shareable URL** (`?sceneId=<Scene 1>`). A later click on Venture Corridor Walk updated React state and persist, but a URL→selection effect re-ran on the **stale Scene 1 `sceneId`** and treated it as an explicit navigation. URL precedence then overwrote the click. The address bar snapped back to Scene 1, persist followed, and reload opened Scene 1.

Classification of the defect: **DISCONNECTED** (selection authority existed; the wrong trigger applied URL precedence). Not missing persistence, and not a director-data loss.

## CANONICAL SELECTION AUTHORITY

Precedence for an explicit Timeline route:

1. **CANONICAL** — URL `sceneId` / `scene_id` / `scene` when the URL itself changes (shareable link, back/forward, typed query)
2. **CANONICAL** — project-scoped persisted `{ projectId → workspace → sceneId }` when the URL has no scene
3. **SESSION** — current in-memory `selectedScene`
4. **FALLBACK** — first valid scene only when nothing else is valid

Retired / do not use as authority:

- **LEGACY** — in-memory-only `useState` with `scenes[0]` on every refresh
- **DUPLICATED** — applying URL precedence again when the creator clicks a scene while the address bar still holds the previous canonicalize

Timeline aliases (`director` / `one` / `three`) persist under `timeline`. Landing (`home`) and Setup do **not** write Timeline memory.

Browser storage holds only `{ projectId, workspace, sceneId }`. Director / database remain authoritative for Timeline contents.

## URL / PERSISTENCE BEHAVIOR

Selecting Venture Corridor Walk writes:

`?workspace=timeline&sceneId=b5282a4c-07eb-40db-9d5b-1512eac74dca`

and `localStorage.adept_ui_last_selected_scene[projectId].timeline = <Walk id>`.

A Timeline open with no `sceneId` restores the remembered scene and re-canonicalizes the URL. An explicit `sceneId` in the URL wins over a remembered Scene 1. An invalid remembered UUID is discarded and a valid scene is selected; Timeline does not loop.

Cross-project: persist keys are project-scoped. Project A’s Walk cannot become Project B’s selected scene.

New-scene creation still calls `onSelect(created.id)` and then persists naturally.

## REFRESH RESULT

Observed after select → persist-only `?workspace=timeline` → full document load:

- Heading **Venture Corridor Walk**
- URL re-canonicalized to Walk `sceneId`
- Active scene block = Walk
- Inspector name = Venture Corridor Walk, duration 8, MiniMax H3
- Corridor still present (`#VentureCorridorScene` / asset `2b1f1901-…`)
- Both dialogue chips present
- Footstep SFX clip chrome still on the tracks
- Batch 1 `0.00s–8.00s`
- No manual re-selection required

## CROSS-PROJECT TEST

Unit: `saveLastSelectedScene("proj-a")` does not read as `proj-b`. Prune of deleted projects drops only the missing project. Playwright uses the existing Korri Anadriya project only (no `POST /api/projects`).

## INVALID-SCENE TEST

Playwright: remembered `00000000-0000-0000-0000-000000000000` + `?workspace=timeline` → one valid active scene, heading present, no reload loop.

## COMFY PROCESS INVENTORY

Read-only. Nothing was killed or restarted for this journey.

| PID | Parent | Role | Class |
|---|---|---|---|
| 36008 | — | Adept `studio-api\.venv` wrapper | Manager wrapper |
| **62224** | 36008 | `-m runtime_supervisor serve` | **CANONICAL MANAGER** |
| 32824 | 62224 | Comfy Desktop-install Python launching `main.py --port 8188` with Adept `extra_model_paths.yaml` | **CANONICAL COMFY PARENT / HELPER** — do not kill |
| **77152** | 32824 | Same command line; **TCP :8188 Listen**; `owned:true` | **CANONICAL :8188 LISTENER** |

## ACTUAL :8188 LISTENER PID

**77152** (`Get-NetTCPConnection -LocalPort 8188 -State Listen`). `GET :8188/system_stats` = 200.

## CANONICAL COMFY OWNER

Adept Background Services Manager PID **62224** owns one Comfy service. Runtime-manager status:

- `adeptRuntime.managerPid` = 62224
- `adeptRuntime.comfyPid` = 77152
- `owned` = true
- `comfyChild.port` = 8188
- `comfyChild.health` = ready

Acceptance is one service authority + one :8188 listener, not literally one Python process. PID 32824 is the legitimate parent of the listener.

## LEGACY / EXTRA PROCESS EXPLANATION

The second `main.py --port 8188` Python (32824) is **not** a second owner. It is the supervisor-spawned Comfy parent. Only 77152 listens. No Desktop Comfy, no Cursor Comfy, no second supervisor listener.

## COMPETING START PATH AUDIT

Production start/stop goes through Background Services Manager / `runtime_supervisor`. Existing tests already require:

- `start_all` must not spawn Comfy when the manager is down
- foreign `:8188` is `PORT_CONFLICT`, not silent adopt (`test_dual_background_services.py`, `test_runtime_supervisor_lifecycle.py`)
- `watch.py` `start_comfy` is the canonical watchdog, not a second owner

No Comfy lifecycle, supervisor, or workflow files were modified. No Comfy MCP required.

## API RESTART ISOLATION

Prior live proof this journey (manager `POST /api/runtime-manager/restart-api`):

- Manager 62224 unchanged
- Comfy listener **77152 unchanged**, `owned:true`
- Studio API 35004 → **44680**
- Director still 30 SFX + 2 lipsync + corridor `2b1f1901-…`

This session did not recycle API again. Current API PID remains **44680**. Comfy listener remains **77152**.

Disclosure: during the ~18s API gap the open Timeline can show `STUDIO_API_OFFLINE` and a messy inspector. After API is healthy, persist-only / full reload restores Walk. That overlay is not treated as a second scene-selection authority.

## FRONTEND BUILD / REFRESH ISOLATION

Vite HMR + browser refresh only. Studio API not recycled this session. Comfy not restarted.

`COMFY BEFORE:` PID 77152 / `:8188/system_stats` 200  
`COMFY AFTER:` PID 77152 / `:8188/system_stats` 200  
`COMFY RESTARTED?:` **NO**  
`WHY?:` Persistence and selection wiring only. No runtime lifecycle scope.

## TIMELINE AUDIO PLAYBACK RESULT

After reload into Walk:

- Playwright: Korri dialogue, Anadriya dialogue, Korri footsteps, Anadriya footsteps all reached `paused: false`; Go to Out ≥ 7.9s
- Live Vite: Play became Pause; Batch 1 `0.00s–8.00s`; both dialogue chips visible; Go to Out = 8s; heading stayed Walk

Audio architecture was not changed in this journey.

## PLAYWRIGHT

`tests/e2e/timeline/venture-corridor-walk-selected-scene-persistence.spec.ts` against live Vite `:5173` + Studio API `:8758`:

**4 passed** (18.5s, chromium, retries 0)

- reload keeps Walk selected, director audio intact, and Play activates lanes
- remembered Walk restores when the URL has no sceneId
- explicit scene URL wins over a remembered Scene 1
- invalid remembered scene fails safe to a valid scene

## TESTS

- `studio-web/src/sceneSelection.test.ts` + `workspacePrefs.test.ts`: **26 passed**
- Playwright: **4 passed**
- Background Services ownership tests: not re-run; no lifecycle code changes
- Comfy MCP: N/A (no workflow change)

## PEER REVIEW

Primary challenge of the required questions:

| Question | Result |
|---|---|
| Does refresh restore the same selected Timeline scene? | **Yes.** Persist-only `?workspace=timeline` and shareable `sceneId` both restore Walk. |
| Is selection project-scoped? | **Yes.** Persist map is `{ [projectId]: { timeline: sceneId } }`. |
| Does explicit scene URL override remembered selection? | **Yes.** Playwright seeds Scene 1, opens Walk `sceneId`, Walk wins. |
| Does invalid remembered scene fail safely? | **Yes.** Discard + one valid scene. |
| Exactly one canonical Comfy :8188 service owner? | **Yes.** Manager 62224, listener 77152, `owned:true`. |
| Can legacy paths still create a competing Comfy? | Production paths delegate to the manager or fail closed. No second listener observed. |
| Does API restart leave Comfy untouched? | **Yes** (prior manager `restart-api` this journey). |
| Does browser/build activity leave both services alone? | **Yes.** HMR/refresh only. |
| Does Timeline playback survive reload? | **Yes.** Playwright 4-lane + Go to Out. |
| Were any unrelated systems changed? | Scene-selection + scene-strip scroll + Playwright only. No audio retiming, no Comfy graphs, no Character Creator, no new project. |

No remaining blocking findings.

## FILES CHANGED

- `studio-web/src/sceneSelection.ts` (new) — precedence, persist, shareable search
- `studio-web/src/sceneSelection.test.ts` (new)
- `studio-web/src/pages/ProjectEditor.tsx` — resolve on refresh, commit-on-select, URL canonicalize, URL→selection only on URL change
- `studio-web/src/components/Timeline.tsx` — `data-testid` / `data-scene-id`, scroll active scene into view, Add Scene selects the new scene
- `studio-web/src/workspacePrefs.ts` — prune selected-scene memory with deleted projects
- `tests/e2e/timeline/venture-corridor-walk-selected-scene-persistence.spec.ts` (new)

## UNRELATED SYSTEMS UNTOUCHED

Director audio, footstep timing, CRS, corridor asset, Character Creator, Co-Director place path, Comfy workflows, runtime supervisor, MiniMax `:8192`.

## HARD NO-GO CONDITIONS

| Condition | Status |
|---|---|
| Timeline still falls back to Scene 1 after reload | **CLEARED** |
| Selected-scene persistence leaks across projects | **CLEARED** |
| URL names a scene but another scene opens | **CLEARED** |
| Invalid stored scene breaks Timeline | **CLEARED** |
| More than one production authority can own Comfy | **CLEARED** |
| Manager silently adopts a foreign Comfy | **CLEARED** (existing PORT_CONFLICT law; no adopt this journey) |
| API restart changes Comfy unexpectedly | **CLEARED** |
| Frontend build restarts API/Comfy | **CLEARED** |
| Walk audio state disappears after refresh | **CLEARED** |
| Playback no longer activates dialogue/SFX | **CLEARED** |

## E2E TRACE

| Step | Result |
|---|---|
| User action — open Timeline, select Venture Corridor Walk | PASS |
| Frontend — heading, URL `sceneId`, persist | PASS |
| API — director GET Walk | PASS (30 SFX, 2 lipsync, corridor asset) |
| Backend — no director mutation | N/A |
| Persistence — project-scoped scene memory + director DB | PASS |
| Runtime — one manager-owned :8188 listener | PASS |
| Result — Walk remains selected | PASS |
| Reload — persist-only and shareable URL | PASS |
| Downstream — Play / Pause / Go to Out, four audio lanes | PASS |

## Manual review

1. Open `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline`
2. Confirm Venture Corridor Walk is selected (or open Library & References and select it once)
3. Full browser refresh — Walk must remain selected with no manual re-pick
4. Play — both dialogue lines and both footstep lanes should sound
5. Settings / Background Services — one Comfy on `:8188`, owned

Not committed. Worktree was already dirty on this branch.
