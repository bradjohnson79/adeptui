# Character Creator V3 — Local Character Sheet Compose

**Governing document for this milestone (Law 30).**  
Does not recertify angle generation, fal Front Vision, Qwen, or headless Comfy.

**Date:** 2026-08-30  
**Branch:** `feat/character-creator-final-closure`  
**Creator UI:** `http://127.0.0.1:5173/`  
**Studio API:** `http://127.0.0.1:8758/`

**Owner lock:** project `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`, Anadriya `4c1c0bc8-a771-4998-b652-5d549b2a2b8d`. Front was not regenerated.

---

## Verdict

```text
GO — CHARACTER CREATOR V3 LOCAL CHARACTER SHEET COMPOSE + JSON ACTIVATION E2E CERTIFIED
```

Independent: **VERIFIED — FULL-STACK E2E PASSED** for this local compose slice.

---

## Root cause

`compose_sheet` called `enrich_multiview_canon` → fal multi-image Vision. Fal failure raised `VISION_UNAVAILABLE` **409**. The stitch compositor never ran.

Repaired: compose is local PIL stitch of approved Front | Side | 3/4 | Back + existing profile / `visualLock.facts`. Same-transaction `persist_crs_in_session`. No fal / Kie / Qwen / Comfy / Vision on this path.

---

## Measured Anadriya

| Item | Value |
|---|---|
| Front | `0c7d967f-eb3b-4003-a4d6-a4a562a38ee0` (unchanged) |
| Side | `98da27bf-e38b-4696-8371-2beb87a30509` |
| 3/4 | `480cca40-af47-49f1-88bc-697b6aa55bf9` |
| Back | `0f24d610-339b-4c83-9b69-c71bd5092ea3` |
| Sheet | `42828ced-1300-4143-9702-31c132bd8f3d` |
| Fingerprint | four ids + `jsonRevision` `1` |
| `@Anadriya` | CRS `approved_reference_asset_id` = sheet |
| `visualLock` | still `ok` |

Playwright clicked **Save and Create Character Sheet** (`cc-v2-compose-sheet`): compose **200**, no `any-llm/vision` / `retry-vision` / 5xx, preview visible, second click idempotent **200**, reload keeps the same sheet id.

---

## Tests (measured)

| Suite | Count |
|---|---|
| Compose local / angle-back / missing-file / in-flight 409 / jsonRevision new sheet | **5 passed** |
| fal XOR + existing fal Vision tests | **included in 12 passed** with compose |
| Playwright `anadriya-sheet-compose` | **1 passed** |

---

## E2E TRACE

| Stage | Result |
|---|---|
| User action | Click Save and Create Character Sheet |
| Frontend | `cc-v2-compose-sheet` → `POST …/sheet/compose` |
| API | 200; no provider URL |
| Backend | `compose_v3_character_sheet` + ingest + `persist_crs_in_session` |
| Persistence | `cc_v2.sheetAssetId` + `crs_canon` |
| Runtime | none (Comfy was already down; left down) |
| Result | sheet PNG + CRS active |
| Reload | same sheet id, `@Anadriya` |
| Downstream | CRS GET matches sheet |

All applicable: **PASS**.

---

## COMFY BEFORE / AFTER / RESTARTED?

| | |
|---|---|
| **COMFY BEFORE** | not listening on `:8188` |
| **COMFY AFTER** | not listening on `:8188` |
| **COMFY RESTARTED?** | **NO** |
| **WHY?** | Compose does not need Comfy. Port was already free. Not started. |

API recycle only (PID 69540). Vite `:5173` PID 62868 unchanged.

---

## Limitations

- Working tree dirty; not committed.
- Hosted Vercel not re-run.
- MiniMax `:8192` not touched.
- Optional `retry-revision-2` still exists; compose never calls it.
