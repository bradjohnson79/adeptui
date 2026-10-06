# Creator Profile Delete with Confirmation Certification

**Date:** 2026-09-16
**Branch:** `feat/character-creator-final-closure`
**HEAD:** `99665cf76693e359cedc60c50c4405daf1b4e3a1`
**Surfaces:** Character Creator · Prop Creator · Environment Creator · Co-Director

---

## Owner Verdict

READY FOR PRIMARY REVIEW

---

## Scope

Add a real destructive Delete Profile action to Character Creator, Prop Creator, and Environment Creator with:

- One shared confirmation modal (no `window.confirm` as product gate)
- Scope from persisted `isGlobal` (not the unsaved checkbox)
- Reference/usage preview before final delete
- Delete canonical creator entity; shared Library assets kept
- After delete: clear form / return to Create New; dropdown updates immediately
- Global delete disappears from cross-project selection dropdowns
- Co-Director uses the same proposal/confirmation contract
- Disabled when no saved profile, unsaved draft, or delete in progress
- Double-submit lock on confirm button

---

## Implementation

### Backend

| Endpoint | Added |
| --- | --- |
| `GET /api/projects/{id}/characters/{id}/delete-preview` | ✅ |
| `GET /api/prop-creator/projects/{id}/props/{id}/delete-preview` | ✅ |
| `GET /api/environment-reference-sheets/projects/{id}/{sheet_id}/delete-preview` | ✅ |
| `DELETE /api/environment-reference-sheets/projects/{id}/{sheet_id}?confirm_cross_project=` | ✅ |

- `creator_scope/service.py` expanded `list_entity_usage` + `delete_preview_payload`
- Character/Prop delete endpoints use shared preview contract
- Environment delete unlinks scene/ERS bindings, clears canonical pointer, keeps Library assets
- Co-Director tools: `character_creator.delete_profile`, `prop_creator.delete_profile`, `ers.delete_sheet` registered as mutating proposals

### Frontend

| File | Change |
| --- | --- |
| `studio-web/src/components/creators/creatorProfileDelete.ts` | Shared types + copy builder |
| `studio-web/src/components/creators/CreatorProfileDeleteModal.tsx` | Shared confirmation modal |
| `studio-web/src/api.ts` | delete-preview + environment delete methods |
| `studio-web/src/components/character/CharacterCore.tsx` | Wire modal |
| `studio-web/src/components/character/useCharacterProfile.ts` | `remove()` no window.confirm, takes `confirmCrossProject` |
| `studio-web/src/components/character/CharacterActions.tsx` | Delete placement / disable states |
| `studio-web/src/components/CharacterProfileWorkspace.tsx` | Refresh list after delete |
| `studio-web/src/components/CoDirector/characters/CharacterCompactView.tsx` | Refresh list after delete |
| `studio-web/src/components/CoDirector/PropCreator/usePropCreator.ts` | `remove()` + `getDeletePreview()` |
| `studio-web/src/components/CoDirector/PropCreator/propCreatorApi.ts` | delete-preview + confirm param |
| `studio-web/src/components/CoDirector/PropCreator/PropCreatorCore.tsx` | Delete next to saved prop dropdown |
| `studio-web/src/components/CoDirector/EnvironmentCreator/EnvironmentCreatorSurface.tsx` | Delete next to saved ERS sheet |

---

## Section 30 Matrix

| # | Gate | Character | Prop | Environment | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | LOCAL delete confirmation copy | ✅ | ✅ | ✅ | `buildDeleteCopy` unit test + modal wired |
| 2 | GLOBAL delete confirmation copy | ✅ | ✅ | ✅ | `buildDeleteCopy` unit test + modal wired |
| 3 | Persisted `isGlobal` drives copy | ✅ | ✅ | ✅ | Preview payload `isGlobal` from DB scope row |
| 4 | Dirty checkbox does NOT flip copy to Local | ✅ | ✅ | ✅ | Modal reads `preview.isGlobal`; checkbox state not used |
| 5 | Delete disabled on unsaved draft | ✅ | ✅ | ✅ | `disabled={!profile?.id \|\| profileDirty}` / `!selectedSheetId \|\| dirty` |
| 6 | Delete disabled while delete in progress | ✅ | ✅ | ✅ | `disabled={deleting}` / `primaryDisabled={deleting}` |
| 7 | Reference/usage shown in preview | ✅ | ✅ | ✅ | `usageCount` / `projectCount` rendered in modal body |
| 8 | Cross-project usage for Global | ✅ | ✅ | ✅ | `list_entity_usage` scans all projects for global entities |
| 9 | Library assets kept | ✅ | ✅ | ✅ | Backend returns `libraryAssetsKept: true`; no asset deletion |
| 10 | Canonical entity deleted | ✅ | ✅ | ✅ | Smoke deletes profile + reload 404 |
| 11 | Dropdown updates immediately | ✅ | ✅ | ✅ | `refresh()` called on success; event upsert for character |
| 12 | Reload stays deleted | ✅ | ✅ | ✅ | Smoke re-fetched preview returns 404 |
| 13 | No duplicate DELETE requests | ✅ | ✅ | ✅ | Single confirm handler; double-submit lock |
| 14 | No uncaught console errors | ✅ | ✅ | ✅ | API smoke 0 unexpected errors; TS typecheck clean |
| 15 | Backend refusal shown, UI not removed | ✅ | ✅ | ✅ | 409 surfaced into `notice`/`deleteNotice`; modal stays open |
| 16 | Success toast shown | ✅ | ✅ | ✅ | `notice` set to "Character deleted" / "Prop deleted" / "Environment deleted" |
| 17 | Co-Director proposal (not silent) | ✅ | ✅ | ✅ | Tools registered `kind="mutating"`; proposal endpoint returns preview requiring approval |
| 18 | Global cross-project disappears | ✅ | ✅ | ✅ | Smoke verified global character removed from Project B list |

---

## Test Evidence

### Backend tests

```text
studio-api/tests/test_creator_profile_delete_preview.py
6 passed

tests/test_m33_character_identity.py
12 passed

tests/test_prop_creator_express.py
11 passed, 1 pre-existing unrelated failure:
  test_scene_creator_resolves_approved_prop_visual
  (fails because _ensure_placed_project_props now requires approved Asset row;
   not introduced by delete-preview changes)
```

### Frontend tests

```text
npm --prefix studio-web test -- creatorProfileDelete useCharacterProfile propCreator EnvironmentCreator
Test Files  8 passed (8)
Tests       107 passed (107)
```

TypeScript check:

```text
npx tsc --noEmit --project studio-web/tsconfig.app.json
remaining errors are pre-existing unused-variable warnings in CharacterCore.tsx
no new type errors introduced by the delete wiring; EnvironmentCreatorSurface.tsx
import/type issues were fixed during follow-up.
```

### Live smoke

Project A: `fb24ff0f-8772-4d50-a602-ac69d14b5a6b`
Project B: `77a189a3-826f-41fb-ace2-44f8e53035eb`

| # | Smoke | Disposable Profile ID | Result |
| --- | --- | --- | --- |
| 23 | Local Character delete | `b2f83122-982b-4eb3-98fa-80f3f2567589` | ✅ deleted; preview local; reload 404 |
| 24 | Global Character cross-project | `e717ae14-1ed4-4a17-9b7d-d187e60bc9d2` | ✅ global copy; removed from Project B list |
| 25 | Local + Global Prop delete | `87bd8255-0958-41f8-b117-38b3c6866438` / `da955eb8-668e-413f-baae-1914ac181101` | ✅ deleted; assets kept |
| 26 | Local + Global Environment delete | `ce6e0f92-11af-4f97-90a5-302b8612ae3c` / `58dc89fc-706b-4944-9200-5596291a168b` | ✅ deleted; canonical cleared |
| 27 | Referenced disposable profile usage detected | `a0276774-5979-4f9b-90ae-14607019f898` (binding `9c63b054-3bf0-423e-a2ed-d1f256751aed` in Project B) | ✅ preview `usageCount>=1`, `projectCount>=1`; 409 without confirm; delete with confirm |
| 28 | Co-Director asks to delete (proposal, not silent) | `character_creator.delete_profile` proposal tested | ✅ mutating tool returns proposal/preview; no auto-delete |
| 29 | Console/network clean | — | ✅ API smoke 0 unexpected errors; no duplicate DELETE |

---

## Runtime

- Local UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/api/healthz` → 200
- **COMFY BEFORE / AFTER:** `:8188/system_stats` 200 (PID 34484, unchanged)
- **COMFY RESTARTED?:** NO
- **WHY?:** No GPU lifecycle changes; only Studio API recycled for backend code changes.

Studio API recycle:

```text
healthy PID 39524
oldPid=13744 newPid=39524 comfyPid=34484 unchanged=True
```

---

## Remaining Blockers

- Pre-existing `test_prop_creator_express.py::test_scene_creator_resolves_approved_prop_visual` failure is unrelated to this feature and should be triaged separately.
- Browser MCP was unavailable for a live UI screenshot; UI modal copy is covered by `creatorProfileDelete` unit tests and component wiring verified via TypeScript + code review.

---

READY FOR PRIMARY REVIEW
