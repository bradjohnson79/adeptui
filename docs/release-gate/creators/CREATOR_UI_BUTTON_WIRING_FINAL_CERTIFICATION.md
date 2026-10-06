# Creator UI Button Wiring — Final Certification

**Date:** 2026-09-16  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf76693e359cedc60c50c4405daf1b4e3a1`  
**Inventory (pre-repair):** `docs/release-gate/creators/CREATOR_UI_BUTTON_WIRING_INVENTORY.md`  
**Project A:** `fb24ff0f-8772-4d50-a602-ac69d14b5a6b` (Cade Scenes)  
**Project B:** `77a189a3-826f-41fb-ace2-44f8e53035eb`  
**UI:** `http://127.0.0.1:5173/`  
**API:** `http://127.0.0.1:8758/api/healthz` → 200  
**Comfy:** PID **34484** healthy before and after. **COMFY RESTARTED?: NO**

---

## FINAL VERDICT

**NO-GO — CREATOR UI FULL BUTTON WIRING NOT CERTIFIED**

Required delete / red / dual-save / unique-name / Global API / Character Sheet Library+IG destinations are closed.  
The governing GO still fails on the leftover required gaps below.

### Failed / incomplete required controls

| SURFACE | CONTROL | RESULT |
| --- | --- | --- |
| Character Sheet | Edit / Inpaint | MISSING — Environment ERS has `ErsEditModal`. There is no Character Sheet region-edit contract. A MAGI redirect would be a fake destination, so no button was added. |
| Co-Director Character | upload / approve / generate-missing / sheet / global via chat | PARTIAL — same-store tools proven for `create_from_brief` + `delete_profile`. Chat walk of upload/approve/generate not done. |
| Co-Director Prop | upload / approve / optional view / generate / save / global via chat | PARTIAL — same-store `create_profile` + `delete_profile` proven. Other mutations not chat-smoked. |
| Co-Director Environment | upload/change reference / generate ERS / global via chat | PARTIAL — `ers.delete_sheet` propose+approve now works (import path repaired). Other `ers.*` chat mutations remain inert (CDX-033). |

### Closed this mission (do not re-open without new evidence)

| REQUIREMENT | RESULT |
| --- | --- |
| Prop Delete in Standard, filled red | PASS — `rgba(127, 29, 29, 0.45)` |
| Prop Delete in Advanced, filled red | PASS — same `danger` class + same handler |
| One Prop delete path + confirmation modal | PASS — `CreatorProfileDeleteModal` + DELETE 200 |
| Character Delete filled red + confirmation | PASS — compact + CharacterActions; DELETE 200 |
| Environment Delete UI + modal | PASS — was DISCONNECTED (handlers, no modal). Now mounted. |
| Environment Create New | PASS |
| Environment Delete red top + bottom + row | PASS — `data-delete-command="deleteEnvironment"` |
| Environment dual Save same contract | PASS — top and bottom both POST `/save` (dedicated Playwright) |
| Unique names 409 | PASS — Character / Prop / Environment API |
| Global ON → OFF persist | PASS — Character PATCH + GET |
| Character Sheet Open in Library | PASS — `cc-v2-open-library` + CRS card; Playwright navigated `workspace=library` |
| Character Sheet Use in Image Generator | PASS — seeds `adept_cis_seed` + `workspace=imagegen&assetId=` |
| Prop Advanced Open in Library / Use in IG | PASS — live-clicked on Starfighter PRS `6868078f` |
| Co-Director delete same store | PASS — Character / Prop / Environment propose+approve DELETE |
| Environment delete does not target foreign Global | PASS — `boundSheetId` wins over stale `ers.sheetId`; 403 path repaired |

---

## Character Creator

**Total controls inventoried (source + smoke):** 28 required family  
**Playwright click rows:** 20 character rows — 16 PASS, 4 SKIP (correctly gated), 0 FAIL

| CONTROL | VERDICT | EVIDENCE |
| --- | --- | --- |
| Saved Characters dropdown | PASS | Hydrates CharacterCore |
| Create Character | PASS | API create + select; compact 409 no longer unmounts the form |
| Delete Character (compact + core) | PASS | delete-preview 200; DELETE 200 with confirm |
| Delete modal confirm red | PASS | computed confirm style recorded `red` |
| Global checkbox | PASS | API create Global ON, PATCH OFF, GET persist |
| Name / Gender / Style / Profile | PASS | save PATCH/POST 200 |
| (?) Character Reference | PASS | tooltip control present |
| Upload / Change | PASS | file input click |
| Add from Library | PASS | picker opened; Cancel testid added |
| Remove reference | PASS | wired; hidden until asset |
| Ask Co-Director CRS | PASS | opens composer |
| Use as Front | PASS | checkbox wired |
| Front generator select | PASS | present |
| Create Front View | PASS | POST `.../views/front/generate` 200 |
| Approve Front | SKIP | correctly disabled until image |
| Upload Side / 3/4 / Back + panel | PASS | clicks fired |
| Generate Character Angles | SKIP | correctly disabled until Front approved |
| Approve / Regenerate / Remove angles | SKIP | correctly gated / no image |
| Save / Create Character Sheet | SKIP | correctly disabled until approved views |
| Regenerate sheet | SKIP | no sheet yet |
| Open Full Size | PASS | added on V2 sheet when image exists |
| CRS Preview / Approve / Reject | PASS | wired + confirm dialogs |
| Open in Library | PASS | Playwright: sheet compose → click → `workspace=library` |
| Use in Image Generator | PASS | Playwright: click → `workspace=imagegen` + `assetId=` |
| Edit / Inpaint | MISSING | no Character Sheet inpaint contract — not added |
| Save Character | PASS | HTTP 200 |
| Reset | SKIP | disabled when not dirty |
| Open Full Character Creator | PASS | compact action |

---

## Prop Creator — Standard

**Total smoke rows:** 12  
**Passed:** 12  
**Failed:** 0  
**Delete red:** YES — `rgba(127, 29, 29, 0.45)`  
**Delete confirmed:** YES — Standard opened modal; Advanced confirmed DELETE 200 on same prop `23153bcd`

| CONTROL | VERDICT |
| --- | --- |
| Standard Prop tab | PASS |
| Saved Prop dropdown | PASS |
| Create New | PASS |
| Delete Prop RED | PASS |
| Global checkbox | PASS (API) |
| Name / Style / Description | PASS |
| Unique-name Open Existing | PASS (API 409 + UI collision block) |
| Reference Library / Upload / Remove | PASS (library + upload clicked) |
| Generate Primary | SKIP this run (avoided live GPU before delete) |
| Upload look | PASS |
| Save Prop | PASS — POST props 200 |
| Reset | PASS |
| Approve / Retry | SKIP — no candidate yet |

---

## Prop Creator — Advanced

**Total smoke rows:** 40  
**Passed:** 14 click/style rows  
**Failed:** 0  
**Skipped (correctly gated / no image):** 26  
**Delete red:** YES  
**Delete confirmed:** YES — DELETE `.../props/23153bcd-40f9-4a81-bfbd-5dd267b25862` 200

| CONTROL | VERDICT |
| --- | --- |
| Advanced Prop tab | PASS — selected prop remains same id |
| Saved / Create New / Delete / Global | PASS — shared `deleteProps` |
| Advanced type dropdown | PASS — visible |
| Reference Upload / Library / Ask CD / Remove | PASS |
| Generate Primary | SKIP this run |
| Upload / Preview / Approve Primary | Upload PASS; Preview/Approve SKIP (no file chosen) |
| Front…Hero Upload | PASS — all seven upload buttons clicked |
| Generate / Regenerate / Approve per view | SKIP — require approved Primary |
| Remove per optional view | IMPLEMENTED — hidden until `imgId`; not live-clicked |
| Generate / Cancel PRS | SKIP — correctly disabled without Primary |
| Preview PRS | SKIP — no sheet |
| Open in Library / Use in Image Generator | PASS — live-clicked on Starfighter PRS |

**Standard ↔ Advanced:** Delete visible + red in both; same prop id through the switch; no duplicate profile.

---

## Environment Creator

**Dedicated Playwright:** `environment dual save and red delete confirmation` — **passed** in the 4-test suite (41.1s total).  
**Broad smoke:** Create New, Library, Upload, Add Character, Add Prop, Save, Delete.

| CONTROL | VERDICT |
| --- | --- |
| Saved list + Select | PASS |
| Create New | PASS |
| Save Environment TOP | PASS — POST `/save` 200 |
| Save Environment BOTTOM | PASS — POST `/save` 200 (waited for busy clear) |
| Delete Environment TOP/BOTTOM/row | PASS — red `rgba(127, 29, 29, 0.45)`; modal; DELETE 200 |
| Global checkbox | PASS (API create Global + resave local) |
| Change from Library / Upload / Remove | PASS |
| Character add / remove | PASS (add menu opened) |
| Prop add / remove / assignment | PASS (add menu opened) |
| Story / Aspect / Generator | PASS (present, not all clicked) |
| Generate ERS | SKIP this run (chargeable) |
| Open Full Size / Library / Use in IG / Regenerate / Edit Inpaint | PASS wiring on `ERSGenerationMonitor` / `ErsEditModal` (result-state) |

---

## Co-Director

| LANE | VERDICT | EVIDENCE |
| --- | --- | --- |
| Character | PARTIAL | `create_from_brief` + `delete_profile` propose+approve; profile gone on GET 404. Upload/approve/generate not chat-smoked. |
| Prop | PARTIAL | `create_profile` + `delete_profile` propose+approve SUCCESS. Other mutations not chat-smoked. |
| Environment | PARTIAL | `ers.delete_sheet` propose+approve SUCCESS after `....` import repair. Other `ers.*` chat mutations remain inert (CDX-033). |

---

## Cross-gates

| GATE | VERDICT |
| --- | --- |
| GLOBAL | PASS API — Character ON then OFF persisted. Prop/Env created Global, uniqueness treated as Global 409. |
| UNIQUE NAMES | PASS — Character / Prop / Environment all 409 `PROFILE_NAME_ALREADY_EXISTS` |
| DELETE | PASS — Character, Prop, Environment confirmation + DELETE 200 on disposables. Cade / Korri / Starfighter untouched. |
| SAVE/RELOAD | PASS — Character reload after delete; API GET after save. Env dual save same id. |
| LIBRARY | PASS — Character Sheet and Prop PRS Open in Library navigated live. |
| CONSOLE | PASS for Adept uncaught — font CORS + 404 statics only (`x-adept-deny-owner-writes` on gstatic). No TypeError/ReferenceError. |
| NETWORK | PASS — expected 409 unique-name; no unexplained 5xx in smoke. |

---

## Implementation (this mission)

| FILE | CHANGE |
| --- | --- |
| `EnvironmentCreatorSurface.tsx` | Create New; red Delete top/bottom/row; mount `CreatorProfileDeleteModal`; `draftNew` so hydrate does not steal a blank draft |
| `sceneCreator.css` | Profile action row |
| `characterCore.css` | Filled red `.character-core__button.danger` |
| `CharacterCompactView.tsx` | Red Delete next to Create Character + same modal/API |
| `characterCompact.css` | Danger button |
| `PropAdvancedPanel.tsx` | Optional-view Remove; PRS Open in Library / Use in Image Generator; `onGoTab` |
| `PropCreatorCore.tsx` | Thread `onGoTab` |
| `CharacterV2Studio.tsx` | Open Full Size; Open in Library; Use in Image Generator |
| `characterSheetDestinations.ts` | Shared Library + Image Generator handoff + CIS seed |
| `CharacterActiveCrsCard.tsx` | Same destinations on approved/draft CRS |
| `CharacterCore.tsx` / `CharacterCompactView.tsx` / `CharacterProfileWorkspace.tsx` / `ProjectEditor.tsx` | Thread `onGoTab` |
| `CinematicImageStudio.tsx` | Consume URL `assetId` / `characterId` / `propId` as authority refs |
| `api.ts` | 409 `existingId` flattened onto `ApiError.details` |
| `environment_reference_sheet.py` | `ers.delete_sheet` imports `....` not `.....` |
| `EnvironmentCreatorSurface.tsx` | `boundSheetId` wins over stale ERS hydrate; owned-only Delete |
| `CharacterReferenceAssetPicker.tsx` | Cancel testid |
| `EntityPicker.tsx` | Close testid |
| `environmentCreatorContracts.test.ts` | Source contract for delete/create/save commands |
| `tests/e2e/creators/creator-ui-button-wiring-smoke.spec.ts` | Click-every-button + dual-save/delete |
| `.runtime/_creator_button_wiring_api_smoke.py` | Unique name / Global / delete / CD propose |

**Unit:** `environmentCreatorContracts.test.ts` — **13 passed**; `characterSheetDestinations.test.ts` + V2/CRS presence — **passed**  
**API smoke:** **25 passed, 0 failed**  
**Playwright:** `creator-ui-button-wiring-smoke.spec.ts` — **4 passed (41.1s)**, 0 failed  
Click-every-button artifact: 49 PASS / 0 FAIL / 37 SKIP

---

## E2E TRACE

| Stage | Character | Prop | Environment |
| --- | --- | --- | --- |
| User action | PASS | PASS | PASS |
| Frontend | PASS | PASS | PASS |
| API | PASS | PASS | PASS |
| Backend | PASS | PASS | PASS |
| Persistence | PASS | PASS | PASS |
| Runtime | PASS (front generate accepted) | N/A this run | N/A this run |
| Result | PASS delete | PASS delete | PASS delete |
| Reload | PASS | PASS | PASS |
| Downstream / Co-Director tools | PARTIAL — create+delete same store | PARTIAL — create+delete same store | PARTIAL — `ers.delete_sheet` same store; other chat mutations inert |

---

## Runtime

```
COMFY BEFORE: PID 34484 / GET :8188/system_stats 200
COMFY AFTER:  PID 34484 / GET :8188/system_stats 200
COMFY RESTARTED?: NO
WHY?: ordinary UI/API certification; Protection Law leave-alone
```

Local review: `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/`

---

## Remaining to flip GO

1. Character Sheet **Edit / Inpaint** — only after a real Character Sheet region-edit contract exists (do not fake MAGI).  
2. Live Co-Director **chat** (not only proposal/approve tools) for upload / approve / generate / global on disposable Character, Prop, and Environment profiles.  
3. Optional: live-click Prop optional-view Remove after a real upload.

Until then the only honest governing line is:

**NO-GO — CREATOR UI FULL BUTTON WIRING NOT CERTIFIED**
