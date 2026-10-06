# Creator UI Button Wiring — Pre-Repair Inventory

**Date:** 2026-09-16  
**Law:** Inventory every visible control before repair. Do not certify from presence.  
**Surfaces:** Character Creator (Express + shared CharacterCore) · Prop Creator Standard + Advanced · Environment Creator

Status key: **WORKING** | **PARTIAL** | **DISCONNECTED** | **MISSING** | **STALE** | **DEAD**

---

## Pre-repair blockers (must close)

| SURFACE | CONTROL | STATUS | NOTES |
| --- | --- | --- | --- |
| Prop Standard | Delete Prop | WORKING (presence) | `className="danger"` + `SavedPropBlock` + shared `CreatorProfileDeleteModal`. Must prove live click. |
| Prop Advanced | Delete Prop | WORKING (presence) | Same `SavedPropBlock` + same handler. Must prove live click. |
| Character | Delete Character | PARTIAL | Handler + modal exist. CSS is outline-only, not filled red. |
| Environment | Delete Environment | DISCONNECTED | Row button + `handleDeleteClick` exist; **`CreatorProfileDeleteModal` is never rendered**. Click cannot confirm. |
| Environment | Create New | MISSING | No clear-form / new-profile control. |
| Environment | Saved dropdown | PARTIAL | Sheet list + Select, not a `<select>`. Select is wired. |

---

## Character Creator

| CONTROL | EXPECTED | STATUS | HANDLER | BACKEND/TOOL | PERSISTENCE |
| --- | --- | --- | --- | --- | --- |
| Saved Characters dropdown | Select owned/global profile | WORKING | `setSelectedId` | `GET .../characters` | Hydrates CharacterCore |
| Create Character | New profile, unique name | WORKING | `handleCreate` | `POST` create profile; 409 reuse | List refresh |
| Delete Character | Confirm modal, red | PARTIAL | `handleDelete` / `cp.remove` | delete-preview + DELETE | List refresh |
| Global checkbox | Persist on Save | WORKING | `CharacterProfileForm` | profile `isGlobal` | Save + reload |
| Name / Gender / Style / Profile fields | Edit draft | WORKING | `cp.setLocal` | save profile | Save required |
| Help (?) Character Reference | Tooltip | WORKING | `title` + tabIndex | none | n/a |
| Upload / Change reference | File → asset | WORKING | `CharacterReferenceControl` | upload + bind | Yes |
| Add from Library | Picker | WORKING | Entity/library picker | asset id bind | Yes |
| Remove reference | Clear bind | WORKING | `handleRemove` | clear reference | Yes |
| Ask Co-Director CRS | Opens CD composer | WORKING | `useOpenCoDirector` | chat only | No mutation |
| Use as Front | Sets front identity | WORKING | `onUseAsIdentity` | adopt front | Yes |
| Front generator select | Family choice | WORKING | `setFamily` | used by generate | Prefs save |
| Create Front View | Generate front | WORKING | `generateCharacterViewV2` | job + asset | Yes |
| Approve Front | Lock front | WORKING | `approveCharacterViewV2` | approval pointer | Yes |
| Upload / Replace Upload Side/3/4/Back | File → angle | WORKING | `uploadCharacterAngle` | angle store | Yes |
| Upload Angles toggle + panel | Reveal upload targets | WORKING | `setUploadOpen` | n/a | n/a |
| Generate Character Angles | Qwen missing angles | WORKING | `generateCharacterAngles` | job (GPU-gated) | Yes |
| Approve Side/3/4/Back | Lock angle | WORKING | `approveCharacterAngle` | approval pointer | Yes |
| Regenerate Side/3/4/Back | New generated angle | WORKING | `regenerateCharacterAngle` | job | Yes |
| Remove angle | Unapprove/remove | WORKING | `approveCharacterAngle(..., false)` | pointer clear | Yes |
| Retry Co-Director Vision | Retry lock | WORKING | `retryCharacterVisionV2` | vision | Yes |
| Create / Save Character Sheet | Compose CRS | WORKING | `composeCharacterSheetV2` | sheet asset | Yes |
| Regenerate Character Sheet | Recompose | WORKING | compose `{ regenerate: true }` | sheet asset | Yes |
| CRS Preview | Library modal | WORKING | `openPreview` | asset URL | n/a |
| CRS Approve / Reject | Confirm dialogs | WORKING | approve/reject candidate | CRS pointer | Yes |
| CRS Regenerate | When wired | PARTIAL | optional `onRegenerate` | compose | Yes |
| Open Full Size (sheet) | Full image | PARTIAL | Preview on CRS card; V2 sheet img is display-only | asset URL | n/a |
| Open in Library | Library tab | MISSING | — | — | — |
| Edit / Inpaint (character sheet) | MAGI/inpaint | MISSING | not on CharacterCore | — | — |
| Use in Image Generator | Handoff | MISSING | Environment-only today | — | — |
| Save Character | Persist profile + global | WORKING | `handleSave` | upsert | Yes |
| Reset | Restore last saved | WORKING | `handleReset` | refresh | Local revert |
| Create a character in this project | Fork global | WORKING | `handleCreateLocal` | create | Yes |
| Open Full Character Creator | Standalone workspace | WORKING | `onOpenFull` | route | n/a |
| History revision buttons | Preview prior CRS | WORKING | `openPreview` | asset URL | n/a |
| Advanced Props / Variants (standalone) | Open panels | WORKING | CharacterProfileWorkspace | own APIs | Yes |

---

## Prop Creator — Standard

| CONTROL | EXPECTED | STATUS | HANDLER | BACKEND |
| --- | --- | --- | --- | --- |
| Standard Prop tab | Show standard stack | WORKING | `setExpressMode` | shared PropEntity |
| Saved Prop dropdown | Select profile | WORKING | `pc.selectProp` | GET prop |
| Create New | Empty draft | WORKING | `pc.newProp` | local + later save |
| Delete Prop RED | Shared modal | WORKING (presence) | `handleDeleteClick` / `pc.remove` | delete-preview + DELETE |
| Global checkbox | Persist on Save | WORKING | `pc.setIsGlobal` | upsert |
| Name / Style / Description | Edit | WORKING | local setters + save | upsert |
| Open Existing / Choose another name | Unique-name 409 | WORKING | `selectProp` / `setName` | uniqueness |
| Reference Upload / Library / Remove | Bind ref | WORKING | `pc.setReference` | upsert |
| Use as identity | Adopt ref | WORKING | checkbox + save path | adopt |
| Generator plan | Source select | WORKING | `GeneratorPlanPanel` | prefs |
| Generate Primary | Candidates | WORKING | `pc.generate` | job |
| Upload look / Primary | Candidate | WORKING | `pc.uploadLook` | asset |
| Save Prop | Persist | WORKING | `pc.save` | upsert + unique name |
| Reset | Restore | WORKING | `pc.reset` | local |
| Approve Primary | Lock identity | WORKING | `pc.approve` | approval pointer |
| Retry failed candidate | Re-run | WORKING | `pc.retry` | job |

---

## Prop Creator — Advanced

| CONTROL | EXPECTED | STATUS | HANDLER | BACKEND |
| --- | --- | --- | --- | --- |
| Advanced Prop tab | Advanced stack | WORKING | `setExpressMode` | mode on PropEntity |
| Saved / Create New / Delete / Global | Same as Standard | WORKING (presence) | same `deleteProps` | same DELETE |
| Advanced type dropdown | spacecraft/… | WORKING | panel local + persist | prop type |
| Reference Upload / Library / CD / Remove | Bind ref | WORKING | panel + `useOpenCoDirector` | upsert |
| Generate / Upload / Preview / Approve Primary | Identity | WORKING | advanced APIs | Primary pointer |
| Front/Back/Left/Right/Top/Bottom/Hero Upload | Optional | WORKING | `advancedAngleUpload` | angle slot |
| Generate / Regenerate / Approve per view | Optional | WORKING | generate/approve angle | independent slots |
| Remove per optional view | Unapprove/clear | MISSING | `advancedAngleApprove(false)` exists, no button | API ready |
| Generate Advanced PRS | Compose | WORKING | `generate_advanced_reference_sheet` | Primary-only OK |
| Cancel sheet | Abort compose | WORKING | cancel API | job |
| Preview PRS | Full-size modal | WORKING | `LibraryQuickPreviewModal` | asset URL |
| Open in Library / Use in Image Generator | Navigate | MISSING | `onGoTab` unused on PropCreatorCore | — |

---

## Environment Creator

| CONTROL | EXPECTED | STATUS | HANDLER | BACKEND |
| --- | --- | --- | --- | --- |
| Saved Environment list + Select | Load sheet | WORKING | `selectHydratedSheet` | GET sheet |
| Create New | Clear to new draft | MISSING | — | — |
| Save Environment TOP | Canonical save | WORKING | `saveEnvironment` | upsert + unique name |
| Save Environment BOTTOM | Same save | WORKING | same `saveEnvironment` | same |
| Delete Environment | Red + modal | DISCONNECTED | handlers exist; modal not mounted | delete-preview + DELETE |
| Global checkbox | Persist | WORKING | `patchIdentity` when sheet id | identity + save |
| Change from Library / Upload / Remove | Reference image | WORKING | picker + `uploadAsset` | planning + save |
| Character add / remove | Plan entities | WORKING | local planning | persist on save/generate |
| Prop add / remove / assignment | Plan entities | WORKING | local planning | persist on save/generate |
| Story theme override | Optional | WORKING | local | persist |
| Aspect radios | Plan | WORKING | local | persist |
| Generator radios | GPT Image 2 / 2.5 | WORKING | local; 2.5 may disable | catalog |
| Generate Environment Reference Sheet | ERS job | WORKING | `ers.start` | Image Core |
| Select sheet / Edit Inpaint | Hydrate / MAGI | WORKING | `ErsEditModal` | versions |
| Open Full Size / Library / Use in IG / Regenerate | Result actions | WORKING | `ERSGenerationMonitor` | handoff + `onGoTab` |
| ERS edit modes / mask / versions | Inpaint chrome | WORKING | `ErsEditModal` | edit APIs |

---

## Co-Director tools (same store)

| TOOL | SURFACE | STATUS |
| --- | --- | --- |
| `character_creator.adopt_angle` / `approve_angle` / `generate_angles` / `delete_profile` | Character | WORKING (registered mutations) |
| `prop_creator.adopt_view` / `approve_view` / `generate_view` / `create_profile` / `generate_reference_sheet` / `delete_profile` | Prop | WORKING (registered mutations) |
| `ers.*` create/generate/delete | Environment | PARTIAL — chat mutations marked inert; capability `ers.generate` + `ers.delete_sheet` remain |

---

## Repair order (this mission)

1. Environment: mount `CreatorProfileDeleteModal`; add Create New; add filled-red Delete Environment at TOP + BOTTOM + row (one handler).
2. Character: filled-red Delete (`.character-core__button.danger`).
3. Prop: keep single delete handler; add optional-view Remove.
4. Click-every-button smoke + cert.
