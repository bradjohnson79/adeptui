# Prop Creator User-Upload Views + Creator / Co-Director Addendum

> **ADDENDUM SUPERSEDED (2026-09-16).** The Creator + Co-Director E2E smoke gate is now governed by `docs/release-gate/prop-creator/CREATOR_CODIRECTOR_E2E_SMOKE_CERTIFICATION.md`. Do not cite the addendum NO-GO reasons below as current truth (Voice clone / Timeline / IG were closed later). The **PROP USER-UPLOAD VIEWS** GO on this page remains historical for that upload gate only. Optional-views contract: `PROP_OPTIONAL_VIEW_GATING_CERTIFICATION.md`.

**Date:** 2026-09-16  
**Branch:** `feat/character-creator-final-closure` @ `99665cf7` plus this working tree  
**Project A:** Cade Scenes `fb24ff0f-8772-4d50-a602-ac69d14b5a6b`  
**Project B:** `77a189a3-826f-41fb-ace2-44f8e53035eb`  
**Local UI:** http://127.0.0.1:5173/  
**Studio API:** http://127.0.0.1:8758/  

## Verdicts

**PROP USER-UPLOAD VIEWS:** **GO — BASIC + ADVANCED PROP USER-UPLOAD VIEWS CERTIFIED**

**CREATOR + CO-DIRECTOR ADDENDUM:** **HISTORICAL — superseded.** See `CREATOR_CODIRECTOR_E2E_SMOKE_CERTIFICATION.md`. The line below is the stale 2026-09-16 upload-pass remainder, not current gate truth: Voice Clone-from-Recording generate/progress not re-run this pass; Timeline and Image Generator surfaces not opened this pass; Co-Director spoken adopt/generate mutations were not executed (those tools require an approved proposal).

---

## What shipped

Upload is an alternative to generation on Basic identity and Advanced Primary + Front/Back/Left/Right/Top/Bottom/Hero.

- Upload auto-saves to Library, binds the same Prop, stays a candidate until Approve
- Generated + uploaded share `propId` + view role + approval
- Mixed sources are valid
- PRS readiness is required approved views, not “all generated”
- Co-Director `prop_creator.get_views` / `adopt_view` / `approve_view` / `generate_view` call the same store
- Co-Director spoken “which views / which voice / which globals” answers come from project grounding on that same store
- Advanced PRS assets now stamp `prompt_meta.propId` so Global projects can read the sheet file

---

## Prop upload report

| Item | Result |
| --- | --- |
| BASIC UPLOAD | PASS — Upload Smoke Basic Cup `f04cfdb6-…`, identity `888c465f-…`, origin uploaded, Library PNG 200 |
| ADVANCED UPLOAD | PASS — Upload Smoke Advanced Ship `a0dae8b5-…` `%upload-smoke-advanced-ship` |
| PRIMARY | PASS — identity authority `940be337-…`, phase approved |
| FRONT | PASS — uploaded `d3a43c47-…` approved |
| BACK | PASS — uploaded `1fb059eb-…` approved |
| LEFT | PASS — generated `3d1e3d61-…` approved (Qwen job `30f482e5-…`) |
| RIGHT | PASS — uploaded `8c07e542-…` approved |
| TOP | PASS — uploaded `bf410c4a-…` approved (generate 409 session-busy; upload fallback) |
| BOTTOM | PASS — uploaded `8d4654fa-…` approved |
| HERO | PASS — uploaded `e628f67d-…` approved (optional) |
| AUTO LIBRARY SAVE | PASS — no separate Save-to-Library step |
| SOURCE METADATA | PASS — slot `source=uploaded\|generated` |
| APPROVAL | PASS — upload is candidate; Approve moves pointer |
| MIXED SOURCE | PASS — left generated, remaining uploaded |
| REFERENCE SHEET | PASS — PRS `579355ac-…` complete, PNG 222227 bytes |
| BUTTON ENABLEMENT | PASS — `canComposeAdvancedSheet` requires Primary + six required views; hero optional |
| GLOBAL | PASS — same ship id visible in Project B; left PNG 200 from B; PRS 200 from B after `propId` stamp; mutate 403 OWNER_REQUIRED |
| LIBRARY | PASS — titles like view role; files HTTP 200 |
| DOWNSTREAM | PASS for Library + PRS resolve; Timeline / Image Generator not opened this pass |
| CO-DIRECTOR | PASS read parity via `get_views` + spoken grounding |
| SAVE/RELOAD | PASS — GET after upload/approve retains assetId / role / source / approved |
| SMOKE | PASS Basic + Advanced API; Playwright Advanced cards passed on retry |
| CONSOLE | Not a full browser console harvest this pass (Playwright retry passed; MCP tab dropped) |

Playwright: `tests/e2e/prop-creator/prop-advanced-upload-cards.spec.ts` — 1 flaky then **passed** (retry).  
API: `tests/test_prop_creator_view_upload.py` + grounding tests **20 passed**.  
Frontend: `propApproval.test.ts` + `propCreatorContracts.test.ts` **21 passed**.

Basic required contract remains **identity / Primary only**. Mixed generate+upload on Basic was not a second required view; Advanced proved mixed source.

---

## Addendum report

### Character Creator

| Item | Result |
| --- | --- |
| Upload Side | PASS — `cdb70dcc-…` candidate then approved, same `characterId` `85e37d4b-…` |
| Upload 3/4 | PASS — `05939962-…` |
| Upload Back | PASS — `bf7ab8d4-…` |
| Approve | PASS — not auto-approved on upload |
| Character Sheet enablement | PASS — `sheetGate.ready=true` after required views approved |
| Character Sheet creation | PASS — composed `a35ea523-…` |
| Library | PASS — Front 1.8MB PNG 200; Side PNG 200 |
| Reload | PASS — GET cc-v2 same character, approved pointers persist |

This pass replaced supporting angles with upload proofs. Historical generated 3/4 remains in Library from the earlier angle-upload cert.

### Character + Co-Director

| Item | Result |
| --- | --- |
| Use uploaded angle | Tool `character_creator.adopt_angle` wired to `cc_v3_multiview.adopt_angle_from_asset`. Spoken adopt not executed (proposal required). |
| Approve | Same store via `approve_angle`; spoken mutation not executed |
| Generate missing angle | Tool registered; not live-run this pass |
| Create sheet | Sheet composed through canonical Character Creator API |
| State parity | PASS — “Which character views are approved for Cade?” → Front (upload), Side/3/4/Back (uploaded) |

### Voice Creator

| Item | Result |
| --- | --- |
| Progress | NOT RE-RUN this pass |
| Clone | NOT RE-RUN this pass |
| Approve new current voice | PASS — pointer `0c890a32-…` → `8ab53b2c-…` → restored `0c890a32-…` via `/voice-profiles/{id}/approve` |
| Version history | PASS — previous profile remained |
| Use Existing | Covered by pointer restore |
| Reload | PASS — approved-status GET after swap |

### Voice + Co-Director

| Item | Result |
| --- | --- |
| Current voice awareness | PASS — “Cade O'Connor Clone v2 Pointer (qwen3-tts, approved)” |
| Version awareness | PASS via `get_voice_status` v6 + versions list |
| Pointer change | PASS through canonical Voice Creator approve |
| State parity | PASS |

### Prop Creator Basic / Advanced / Co-Director

Covered in the Prop table. Spoken: “Which prop views are approved for Upload Smoke Advanced Ship?” matches store (Primary uploaded, Left generated, remaining uploaded).

### Global

| Item | Result |
| --- | --- |
| Character | PASS — Cade `85e37d4b-…` visible in B, same id, `isGlobal=true` |
| Prop | PASS — ship same id in B |
| Environment | PASS — Anadriya's Quarters + other globals listed in A and B |
| Local negative test | NOT CLOSED — create local-only prop returned 400 in the first script |
| Backing media | PASS — Cade Front, ship left, PRS resolve from home; left + PRS resolve from B |
| Cross-project | PASS — no copy; 403 on foreign mutate |

### Global + Co-Director

| Item | Result |
| --- | --- |
| Discovery | PASS — Project B lists the same global characters / props / environments |
| Selection | Not a UI bind click this pass |
| Canonical IDs | PASS — list ids match creator stores |

### Downstream / Console

| Item | Result |
| --- | --- |
| Timeline | NOT OPENED this pass |
| Image Generator | NOT OPENED this pass |
| Library | PASS |
| CONSOLE | Incomplete harvest |
| NETWORK | Observed creator APIs 200; PRS-from-B was 403 until `propId` stamp, then 200 |

---

## Runtime

- API recycled only (last: `oldPid=43660` → `newPid=39016`)
- `COMFY BEFORE:` PID **34484** healthy (`GET :8188/system_stats` 200)
- `COMFY AFTER:` PID **34484** healthy
- `COMFY RESTARTED?:` **NO**
- `WHY?:` ordinary API + UI; `:8188` left untouched

---

## Limitations

- Live upload proofs include solid-color PNGs. Validation allows creator artwork.
- Selecting an Advanced prop now switches the Express tab to Advanced so view cards are reachable.
- Advanced Description currently shows internal `prsAssetId=` notes on the Standard tab. That is leftover marker text, not a second Prop.
- Co-Director approve/adopt/generate mutations require an approved proposal (`tools/audited` returns 502). Read tools and grounding answers do not.
- Playwright Advanced card spec was flaky on the first attempt (tab still Standard), then passed after auto-switch + retry.

---

## Remaining for addendum GO

> **HISTORICAL.** Current remaining / failed paths live in `CREATOR_CODIRECTOR_E2E_SMOKE_CERTIFICATION.md`.

1. Live Voice Creator Clone-from-Recording: upload recording → sample text → generate → progress reaches 100% only after audio exists → play → approve → reload.
2. Open Timeline and Image Generator and confirm approved character angles, current voice, uploaded prop views / PRS, and Global ERS resolve with no broken asset URLs.
3. Spoken Co-Director adopt/approve/generate turns through the proposal path (or an authorized audited path) proving the same pointers as the creator UIs.

---

## E2E TRACE (Prop upload)

| Stage | Verdict |
| --- | --- |
| User action | PASS |
| Frontend | PASS (Upload + Approve + Regenerate on Advanced cards; Playwright retry) |
| API | PASS |
| Backend | PASS |
| Persistence | PASS |
| Runtime | PASS (generated Left) |
| Result | PASS |
| Reload | PASS |
| Downstream | PARTIAL (Library + Global file resolve PASS; Timeline / IG not opened) |
