> **HISTORICAL.** Lifecycle save/reset/delete still apply; generation contract is SUPERSEDED BY CHARACTER CREATOR V2.

# Character Creator Save / Reset / Delete — Certification

## CURRENT

```text
GO — CHARACTER CREATOR SAVE / RESET / DELETE CERTIFIED
```

Governing document for this workstream only. Do not mix into Co-Director production-loop or single-CRS verdicts.

Live target: `http://127.0.0.1:8760/` + `http://127.0.0.1:8758/`.
Project: Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` (no new projects).
Korri is protected and was not deleted.

Branch: `feat/voice-studio-identity-and-global-ux`
HEAD: `959be5ad4196b55f5c9a3fd87c5a7fe9516deaaf`

---

## Verdict

**GO — CHARACTER CREATOR SAVE / RESET / DELETE CERTIFIED**

---

## Contract

| Control | Behavior | Evidence |
| --- | --- | --- |
| Save | Only persist path; reload keeps edits | Live smoke PATCH + GET; Playwright save + reload |
| Reset | Restores last persisted snapshot; no PATCH; disabled when not dirty | `snapshotRef` + `replaceCharacterProfile`; Playwright asserts no PATCH then original description |
| Delete | Confirm with name; disposable only; Korri 409 | `delete_profile` name/slug guard; smoke `korri_delete_status=409`; Playwright 404 after delete |

Autosave-on-debounce (`patchDebounced` from the profile form) is no longer the editor path. Edits use `setLocal` + `profileDirty`.

---

## Tests

- `test_character_lifecycle_controls.py`: **5 passed** (save persist, validation, reset no mutation, delete leaves shared Asset, Korri protected)
- Frontend: Reset snapshot unit in `useCharacterProfile.test.ts`
- Smoke (live Schnick Coffee disposable `5fdef2a6-…`): **PASS — CHARACTER CREATOR SAVE/RESET/DELETE SMOKE**
- Playwright `character-lifecycle-controls.spec.ts` A–E: **passed** (5.8s then 2.4s re-run)

---

## Addendum matrix

| Item | Result |
| --- | --- |
| Save persist | PASS |
| Save validation | PASS |
| Reset no PATCH | PASS |
| Reset disabled when clean | PASS |
| Delete confirm + cascade profile | PASS |
| Shared Library assets survive | PASS (unit) |
| Korri protected | PASS |
| Disposable only for delete E2E | PASS |

Final language: **GO — CHARACTER CREATOR SAVE / RESET / DELETE CERTIFIED**
