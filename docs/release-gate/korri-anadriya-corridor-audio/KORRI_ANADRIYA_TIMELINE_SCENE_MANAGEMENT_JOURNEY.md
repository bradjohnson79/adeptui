# Timeline Scene Card ⋯ Menu: Rename + Remove

Addendum to the Korri Anadriya Timeline mission. Does not replace Journey 1 (selected-scene persistence) or Journey 2 (five-control transport). Scene UUID remains identity. Name is editable metadata.  
Amalgamated with the last three completed builds in [`ADEPT_UI_KORRI_ANADRIYA_LAST_THREE_BUILDS_UNIFIED_REPORT.md`](ADEPT_UI_KORRI_ANADRIYA_LAST_THREE_BUILDS_UNIFIED_REPORT.md).

Project: **Korri Anadriya** `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
Branch: `feat/character-creator-final-closure`  
HEAD: `b6156455e643d5fa430784b3130756f2d8038651` (this work is uncommitted)  
Review: `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline&sceneId=b5282a4c-07eb-40db-9d5b-1512eac74dca`  
Studio API: `http://127.0.0.1:8758/`

Protected scenes (never deleted in certification):

| Scene | ID |
|---|---|
| Scene 1 | `1f46b621-46f9-4b7e-8273-202a49e1ca7c` |
| Venture Corridor Dialogue | `ae8e5699-a5d8-4b9b-ad8e-0003d81d3639` |
| Venture Corridor Walk | `b5282a4c-07eb-40db-9d5b-1512eac74dca` |

No new project was created. Timeline audio architecture was not modified. Comfy was not restarted.

---

## Classification

| Capability | Class | Repair |
|---|---|---|
| PATCH scene name | **EXISTS** (`SceneService.update` + `api.updateScene`) | Wired from the scene-card menu. PATCH body is `{ name }` only. |
| DELETE scene | **EXISTS** (`SceneService.delete` + `api.deleteScene`) | Wired from the scene-card menu with a real confirmation dialog. |
| Scene-card overflow | **MISSING** | Added `⋯` using the shared `Menu` primitive. |
| Empty-name validation | **WEAK CONTRACT** | Service now trims and rejects blank names. DB limit remains 200. |
| In-flight jobs on delete | **WEAK CONTRACT** | Delete now calls existing `stop_remaining_scene_jobs` plus `Job` cancel. |
| Neighbor selection after active delete | **MISSING** | Next in order, else previous, else empty-state. |
| URL / persist after delete | **WEAK CONTRACT** | Invalid remembered/URL scene ids are cleared after project is loaded. Never strip `sceneId` while project is still loading. |

Last-scene law: **zero scenes are allowed**. Add Scene remains. Empty Timeline still shows the Scenes list.

Shared Library assets are project-scoped. Scene delete does not delete asset files.

---

## API

- Rename: `PATCH /api/projects/{projectId}/scenes/{sceneId}` `{ "name": "..." }`
- Remove: `DELETE /api/projects/{projectId}/scenes/{sceneId}`
- Second delete of the same id: `404 SCENE_NOT_FOUND` — UI treats that as already gone and refreshes.

---

## UX

- Card click still selects the scene.
- `⋯` is top-right on each card. `aria-label="Scene options for <scene name>"`.
- Clicking `⋯` does not change the selected scene (`stopPropagation` + Menu root isolation).
- Menu: Rename scene / Remove scene. Outside click and Escape dismiss. Viewport-clamped. Does not resize the card list.
- Rename: Adept modal, current name prefilled, Enter confirms, Escape cancels. Portaled to `document.body` so the left-drawer `transform` cannot trap it.
- Remove: confirmation is mandatory. Destructive red **Remove Scene**. Cancel is the initial safe focus.

---

## Persistence proof

Playwright on Korri (`ADEPT_ALLOW_KORRI_MUTATION=1`), temps only:

1. Created `Scene Menu Cert A` + `Scene Menu Cert B` in the existing project.
2. Renamed A → `Scene Menu Cert A Renamed`. Card updated. API GET returned the new name with the same UUID. Reload kept the name.
3. Remove B: Cancel left the card. Confirm removed it. Reload did not restore it.
4. Remove active A: selected a neighboring valid scene. URL no longer pointed at the deleted UUID. Reload did not resurrect A or B.
5. Scene 1, Dialogue, and Walk remained. Library asset count did not drop.

Five-control transport spec: **1 passed**, including `⋯` on Walk while Scene 1 is selected does not change `data-scene-id`.

---

## Co-Director / transport

- `CoDirectorProvider` already receives `sceneId` + `sceneName` from the selected scene. Rename updates the name without a new conversation (conversation is project-scoped). Active-scene delete moves context to the neighbor.
- Rename does not change `sceneId`, so transport / playhead are untouched.
- Active delete hydrates the replacement scene through the existing switch path.
- Non-active delete leaves the current Timeline mounted (`data-stability-marker=keep` in Playwright).

---

## Tests

| Suite | Result |
|---|---|
| `studio-web` `sceneLifecycle.test.ts` + `sceneSelection.test.ts` | **23 passed** |
| `studio-api` `test_scene_service.py` | **16 passed** |
| `tests/e2e/timeline/timeline-scene-rename-remove.spec.ts` | **1 passed** (7.6s) |
| `tests/e2e/timeline/timeline-five-control-transport.spec.ts` | **1 passed** (17.7s) |

---

## Primary live review

Vite Timeline, Walk selected:

- Three production scene cards with `⋯`
- Opening Walk `⋯` shows Rename / Remove and does not change the header or `sceneId`
- Rename Scene modal is a centered dark Adept dialog, prefilled **Venture Corridor Walk**, Cancel / Rename
- Cancel left Walk named Walk
- Inspector Name still **Venture Corridor Walk**
- Five-control transport visible and unchanged

---

## COMFY

- **COMFY BEFORE:** PID 77152, HTTP 200 `/system_stats`
- **COMFY AFTER:** PID 77152, HTTP 200
- **COMFY RESTARTED?:** **NO**
- **WHY?:** Scene menu only. Studio API recycled via `restart_studio_api_only.py` (`comfyPid=77152 unchanged=True`).

---

## FILES CHANGED

- `studio-web/src/components/Timeline.tsx`
- `studio-web/src/components/timeline-master/SceneCardDialogs.tsx` **new**
- `studio-web/src/components/timeline-master/TimelineEditorShell.tsx`
- `studio-web/src/components/timeline-master/TimelineInspector.tsx`
- `studio-web/src/components/ui/Menu.tsx`
- `studio-web/src/components/ui/menu.css`
- `studio-web/src/sceneLifecycle.ts` **new**
- `studio-web/src/sceneLifecycle.test.ts` **new**
- `studio-web/src/sceneSelection.test.ts`
- `studio-web/src/pages/ProjectEditor.tsx`
- `studio-web/src/styles.css`
- `studio-web/src/styles/timeline-master/timeline-editor-shell.css`
- `studio-api/app/services/scene_service.py`
- `studio-api/app/schemas.py`
- `studio-api/app/routers/api.py`
- `studio-api/tests/test_scene_service.py`
- `tests/e2e/timeline/timeline-scene-rename-remove.spec.ts` **new**
- `tests/e2e/timeline/timeline-five-control-transport.spec.ts`

## UNRELATED SYSTEMS UNTOUCHED

Comfy `:8188`, MiniMax `:8192`, Audio Studio, Walk footstep timing, Timeline transport architecture, Character Creator, AssetTray’s older unconfirmed Delete (not this surface).

---

## E2E TRACE

| stage | verdict |
|---|---|
| User action | PASS — ⋯, Rename, Remove, Cancel, Confirm |
| Frontend | PASS — menu does not select; dialogs portaled |
| API | PASS — PATCH name; DELETE scene |
| Backend | PASS — trim/blank reject; job stop via existing cancel; index repack |
| Persistence | PASS — rename and delete survive reload |
| Runtime | N/A — no GPU generation in this addendum |
| Result | PASS — temps gone; protected scenes remain; assets kept |
| Reload | PASS — no resurrected temps; URL not a deleted UUID |
| Downstream | PASS — header, inspector, Co-Director bindings, transport |

---

## FINAL VERDICT

**GO — TIMELINE FULL SYSTEM SCENE-SWITCH STABILITY + SCENE MANAGEMENT + FIVE-CONTROL TRANSPORT + PLAYBACK JOURNEY E2E CERTIFIED**
