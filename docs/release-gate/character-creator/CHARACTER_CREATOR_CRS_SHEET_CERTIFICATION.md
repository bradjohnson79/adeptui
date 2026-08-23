> **HISTORICAL — SUPERSEDED BY CHARACTER CREATOR V2.**

# Character Creator CRS Sheet Certification

**Governing report for Character Creator CRS Sheet Closure (Law 30).**  
Audit baseline remains historical: `docs/release-gate/character-creator/crs-sheet-audit.md` (not overwritten).

**Verdict:** `GO — CHARACTER CREATOR → 2K CRS SHEET → APPROVED CANON → UNIVERSAL @CHARACTER CERTIFIED`

Subagent D ([CRS gap score](bf64135a-9c7b-4b50-84ca-929dc8050e7c)): `READY FOR PRIMARY REVIEW`. Primary owns this GO.

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/voice-studio-identity-and-global-ux` |
| HEAD SHA | `8dcc17bc15c6ac83f6243040dab94b6044e71637` |
| Live `apiRevision` | `8dcc17b` |
| Live `apiStartedAt` | `2026-08-19T07:59:27Z` (Studio API reloaded onto this working tree) |
| Served `studio-web` bundle | `index-PjkAy2aM.js` |
| Creator UI | http://127.0.0.1:8760/ |
| Studio API | http://127.0.0.1:8758/ |
| Comfy | http://127.0.0.1:8188/ — PID **39708** reused (not recycled) |
| Project | Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` |
| Character | Korri `c49371ed-ba6b-4c16-ba98-a8b28b72118b` |
| Approved CRS asset | `067453ce-6204-434a-bfed-e6d0333e0e67` |
| Job | `cd874bb0-93e9-4b1e-8ac9-0a534b152bab` — `qwen2512.ref` — `REFERENCE_CONDITIONED` — `2K` — `native` |
| Measured file pixels | **2560×2560 RGB** (PIL on `docs/release-gate/character-creator/evidence/J-korri-crs-2k.png`) |
| Persisted CRS | `crs_revision=2`, `tag=@Korri`, `has_approved_reference=true` |

No `POST /api/projects`. Korri was not deleted.

---

## Scope

Close the 10 CRS audit gaps by **reusing** CharacterCore / sheet / CRS / ERS contracts. Character Creator was not rebuilt.

Creator path: Character Profile → reference → Qwen Image 2512 default → Generate 2K CRS → preview → Approve exact sheet → persisted CRS JSON → `@Korri` resolves.

---

## Gap matrix

| Gap | Verdict | Evidence |
| --- | --- | --- |
| 1 Qwen default | PASS | `defaultGenerator=qwen2512`, Auto Select off; idle/Auto-only prefs migrate to Qwen; saved Illustrious still wins; no silent substitute |
| 2 Simplified UX | PASS | Compact Generator + Batches + Generate; Auto Select / multi-gen / cloud under collapsed More Generators |
| 3 Tooltip + Co-Director | PASS | Required single-view **or** multi-view copy; `character-reference-tip`; Ask Co-Director opens existing Co-Director |
| 4 Active CRS card | PASS | `CharacterActiveCrsCard` above Previous Generations / Candidates |
| 5 Preview modal | PASS | `LibraryQuickPreviewModal` + `/api/assets/{id}/file`; no `window.open` |
| 6 Regen preserve hero | PASS | Approved `hero_identity` stays Active until a new Approve; new run is CRS vN+1 candidates |
| 7 Native 2K | PASS | `crs_2k_pixels()` 2560×2560; tile 1280; live file 2560×2560; not ERS 2560×1440; not an upscaler |
| 8 Approve → CRS | PASS | One transaction: exact sheet → canonical hero → persist CRS + increment revision → `approval_status=approved` |
| 9 `@Character` | PASS | `entity_resolver.resolve_character` reads persisted CRS; `reference_parser.py` not wired |
| 10 Delete | PASS | Korri 409 `PROTECTED_CHARACTER`; disposable fixture deleted; cache invalidate; VisualIdentity detach; Library kept |

Qwen + attached reference pins `qwen2512.ref`. If I2I is not ready the path raises; it does not silent-fall to T2I.

---

## Tests

| Suite | Result |
| --- | --- |
| `studio-web` character unit (vitest) | **75 passed** |
| `studio-web` `tsc -p tsconfig.app.json` | PASS |
| `studio-api` CRS / sheet / routing / composition / approval | **92 passed** including `PASS — CHARACTER CREATOR CRS SMOKE` |
| Playwright `tests/e2e/character-creator/character-crs-sheet.spec.ts` chromium | **12 passed** (A–N), `--retries=0`, `ADEPT_BETA_TARGET=1` |

Out of scope: `test_m33_character_creator.py::test_create_character_intent_routes_character_creator` (`IntentClassification.route_decision`) — unrelated to CRS.

---

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — Character Creator on Schnick / Korri; compact Generate / Approve / Preview |
| Frontend | PASS — Qwen default, Active CRS, modal preview, progress honesty |
| API | PASS — visual-sheet start/advance, `GET .../crs`, `POST .../approve-candidate`, disposable `DELETE` |
| Backend | PASS — Qwen `qwen2512.ref`, CRS persist, entity_resolver, Korri delete guard |
| Persistence | PASS — `crs_canon` trait, `crs_revision=2`, `approval_status=approved` after reload |
| Runtime | PASS — local Qwen I2I on Comfy PID 39708; provenance REFERENCE_CONDITIONED 2K native |
| Result | PASS — composed sheet asset `067453ce-…` measured 2560×2560 |
| Reload | PASS — Playwright M: Active CRS + Character Approved banner after reload |
| Downstream | PASS — `@Korri` CRS summary; disposable fixture unregister; Korri remains |

Independent verifier language: **VERIFIED — FULL-STACK E2E PASSED** for this Character Creator CRS slice.

---

## Beta

Canonical refresh: rebuilt `studio-web`, restarted Studio API onto this tree, started Beta web, **left Comfy 39708 running**.

Confirmed HTTP 200:

- http://127.0.0.1:8760/
- http://127.0.0.1:8760/__beta_web_health
- http://127.0.0.1:8758/api/health
- http://127.0.0.1:8188/system_stats

Qwen inventory: `qwen2512` Certified, executable, `supportsReferences=true`.

Manual review: open Schnick Coffee → Character Creator → Korri. Active Character Reference Sheet should show the approved 2K Qwen sheet, `@Korri`, and Production Ready.

---

## Evidence

Under `docs/release-gate/character-creator/evidence/`:

- `A-compact-generator.png` … `H-generate-label.png`
- `I-generating.png`, `J-2k-sheet.png`, `J-korri-crs-2k.png` (2560×2560 file)
- `K-approved.png`, `M-reload-approved.png`
- `L-korri-crs.json`, `N-disposable-delete.json`

---

## Limitations (honest)

- Playwright I–K’s **passing** run reused the live Qwen 2K candidate already completed on this API (`qwen2512.ref`, asset `067453ce-…`, measured 2560×2560) rather than enqueueing a second GPU job after Approve. The sheet was produced on the post-reload Studio API during this certification window.
- `:8758` had stacked uvicorn workers from prior sessions; they were stopped and a single Studio API was started. Comfy was not recycled.
- Untracked `reference_parser.py` and `fidelity.py` are **not** part of the live `@` path and are not in this commit.
- Promote / Update Character Identity remains the advanced Continuity/Bible sync; creator Approve is the canon-finalization event.

---

## Binary verdict

`GO — CHARACTER CREATOR → 2K CRS SHEET → APPROVED CANON → UNIVERSAL @CHARACTER CERTIFIED`
