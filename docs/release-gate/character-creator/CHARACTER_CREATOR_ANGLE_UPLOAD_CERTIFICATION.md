# Character Creator — User-Uploaded Angles

**Date:** 2026-09-15  
**Branch:** `feat/character-creator-final-closure` @ `99665cf7` plus this working tree  
**Project:** Cade Scenes `fb24ff0f-8772-4d50-a602-ac69d14b5a6b`  
**Character:** Cade O'Connor `85e37d4b-a32e-4374-888b-1389fc0b3720`  
**Review:** http://127.0.0.1:5173/  
**Studio API:** http://127.0.0.1:8758/  
**Verdict:** **GO — CHARACTER CREATOR USER-UPLOADED ANGLES CERTIFIED**

## What shipped

Side / 3/4 / Back now accept a second creator path: **Upload**, alongside existing **Generate Character Angles** (Qwen Image Edit). Both coexist. Uploads auto-save to the project Library, bind to the same Character, and stay candidates until Approve.

## Contracts

- Canonical slots: Front (identity) · Side · 3/4 · Back
- Slot `source`: `uploaded` | `generated`
- Library metadata on uploaded assets: `assetId`, `projectId`, `characterId`, `characterName`, `assetType=image`, `role=character_angle`, `angle=side|three_quarter|back`, `source=uploaded`, `createdAt`, `updatedAt`
- Generated Qwen jobs stamp the same role/angle contract with `source=generated`
- Upload does **not** auto-approve
- Replace generated with upload (or upload with Regenerate) does **not** delete uploaded Library history
- `Generate Character Angles` skips uploaded candidates and already-approved slots
- Front remains primary identity; no new Character / `@CadeSide` tag
- Global characters: approved angle files stay on the home project; `resolve_readable_asset` can serve them via `prompt_meta.characterId` when the Character is visible

## Live Cade evidence

| Test | Result |
| --- | --- |
| A Upload Side | PASS — `source=uploaded`, candidate, Library asset, same `characterId` |
| B Approve Side + reload | PASS — approved Side persisted |
| C Generate 3/4 Qwen | PASS — job `e69f00ca-…` → asset `1aa75a76-…` `source=generated` |
| D Upload + approve Back | PASS — `08770b46-…` |
| E Character Sheet | PASS — composed `bebb1cbd-ec7d-4cda-b18b-4fee05774f75` from Front + uploaded Side + generated 3/4 + uploaded Back |
| F Library | PASS — tags `Cade O'Connor — Side` and `Cade O'Connor — Back`; file HTTP 200 |
| G Downstream / bind | PASS — still `@Cade` / same profile id; sheet + angle `assetId`s are ordinary Library images |

Playwright: `tests/e2e/character-creator/character-creator-angle-upload.spec.ts` **1 passed**.

API tests: `tests/test_cc_v3.py` **38 passed**. Frontend presence: **3 passed**.

Browser after reload: Side **Replace Upload** (blue upload), 3/4 **Upload** (Qwen figure), Back **Replace Upload** (red upload); all three **Approved**; **Generate Character Angles** still present; **Global** checkbox unchanged.

## Runtime

- API recycled only (`oldPid=38080` → `newPid=42740`)
- `COMFY BEFORE:` PID **34484** healthy  
- `COMFY AFTER:` PID **34484** healthy  
- `COMFY RESTARTED?:` **NO**  
- `WHY?:` ordinary API + UI work; `:8188` left untouched

## Limitations

- Live Side/Back uploads were solid-color proof images (validation allows creator artwork; it does not require photoreal style).
- Playwright re-uploaded Side after the first live Side; the current approved Side is `43c4e88c-…`. Historical Side `8d53762c-…` remains in Library.
- Co-Director tools (`get_angles`, `adopt_angle`, `approve_angle`, `generate_angles`) are registered against the same store. A full spoken Co-Director turn was not separately certified beyond tool wiring + specialist prompt.
- Cade is project-native (`is_global=false`). Global file reuse is implemented on the existing scope contract; it was not re-run against a foreign project in this pass.

## E2E TRACE

| Stage | Verdict |
| --- | --- |
| User action | PASS |
| Frontend | PASS |
| API | PASS |
| Backend | PASS |
| Persistence | PASS |
| Runtime | PASS (Qwen 3/4) |
| Result | PASS |
| Reload | PASS |
| Downstream | PASS (sheet + Library + same character) |
