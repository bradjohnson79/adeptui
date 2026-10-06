# Character Creator 4-View + JSON Professional Closure

**Law 30:** this is the only governing report for Character Creator 4-View + JSON Professional Closure. The prior final-closure report is historical / superseded:

`docs/release-gate/character-creator-final-closure/CHARACTER_CREATOR_FINAL_CLOSURE.md`

Do not treat the prior `PARTIAL` / cert-script Rev 4 as this milestone’s GO.

**Date:** 2026-08-22 / 2026-08-23  
**Branch:** `feat/character-creator-final-closure`  
**HEAD (committed):** `1c865606571664ed3c06dffdf468f643cd9a3da8`  
**Working tree:** dirty. Do not commit. Do not reset. Do not deploy.

**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`.  
**Korri:** `c49371ed-ba6b-4c16-ba98-a8b28b72118b` — production character, **read-only** this closure. Covered by Production Canon Approval Law (not a name special case). Owner decides later whether to keep or replace persist CRS Rev 4.

**Creator UI:** Vite `http://127.0.0.1:5173/` + Studio API `http://127.0.0.1:8758/`. Do not start `:8760`. Do not `POST /api/projects`.

**Allowed final language only:**

```text
GO — ADEPT UI CHARACTER CREATOR 4-VIEW + JSON FULL-STACK PRODUCTION CERTIFIED
```

or `NO-GO` / `PARTIAL` / `BLOCKED BY ENVIRONMENT` with the exact blocker.

---

## Product contract

Profile + optional Character Reference → **Generate** → one **4-view Draft** (Front, Side, Back, Head/Neck Close-Up) → **Preview** → **Approve** or **Reject**.

- Generate never writes persist CRS.
- Reject deletes the draft only.
- Approve is the only persist-CRS writer and produces Character JSON.
- No 3/4 on the default path. 5-view law remains isolated / legacy.
- Default GPU route: Flux `flux.txt2img` × 4 tiles → Adept 2×2 compose.
- 2509 is not a GO gate. No new model download.

### Production Canon Approval Law

No script, certification harness, subagent, API-only test, autonomous bot, or background process may approve or replace the canonical CRS of a character that already has persist CRS. Canon mutation requires an explicit owner-facing Approve from the live Character Creator UI with `ownerConfirmed: true`. Automated lifecycle tests use disposable engineering characters only.

---

## Architecture Before

Mapped by the Architecture specialist ([Architecture](6b9e28fc-a452-4a52-a9ad-917b3bb30cae)) before edits.

**Owner Generate (before):** `buildCharacterSheetStartBody` → `POST .../visual-sheet/generate` → `start_visual_sheet_generation` with `task="CRS_GENERATION"`. Frontend did **not** send `taskType` / layout. Backend enqueued **five** law views (Front / 3/4 / Side / Back / Close-Up) and composed a labeled 3×2 when `n==5`.

**KEEP:** CharacterCore spine; generate/advance/compose ingest; Approve = `persist_crs_in_session` only; Reject never bumps CRS; reject deletion service; Flux txt2img; 2×2 compose helper; disposable-character tests; `FOUR_PANEL_ROLES` crop map.

**ISOLATE:** `CRS_VIEW_GENERATION`; 5-view `LAW_REQUIRED_VIEWS` / labeled 3×2 compose; hosted one-image `fourViewSingleOutput`; 2509 crop taxonomy as a GO path; cert helper scripts under `evidence/_korri_*.py`.

**Defects that blocked GO:** UI Generate ≠ 4-view; Approve/Reject hid when persist approved and draft id == approved id; cert scripts wrote Korri persist Rev 4; 2509 rejected `reference_image`; Co-Director remounted ERS/Scene leftovers.

---

## Architecture After

- Default identity packet `requiredViews` = `FOUR_VIEW_REQUIRED_VIEWS` (front / side / back / close-up).
- `CANDIDATE_SHEET_VIEW_ROLES` is four tiles. `FIVE_VIEW_LAW_ROLES` remains isolated.
- `four_view_sheet.REQUIRED_VIEWS` is four names (no 3/4).
- Pack candidate `layout` = `four_view`, `fourViewSingleOutput` = false. Jobs stay `CRS_SINGLE_VIEW` tiles.
- Compose `n==4` → unlabeled 2×2. Structural `assess_four_view_layout(..., view_count=4, composed=True)` fail-closes a non-four-view sheet. Generate still does not persist CRS.
- `_hydrate_candidate_layout` preserves `composed=True` / `viewCount=4` and does not assess per-camera tiles as the sheet.
- Default 4-view compose skips the per-tile one-figure gate (false-positives on real Flux tiles). The queue-worker gate also skips default 4-view pack tiles (`fourViewPackTile`) and never silently enqueues Qwen. Isolated 5-view law still uses tile gates.
- Compose does not `_attach_role(..., "hero_identity")`. Approve is the only persist / canon writer.
- Live Generate while tiles are queued/running returns the existing pack. Failed leftover jobs are cancelled, then a new 4-view is enqueued.
- `POST .../approve-candidate` accepts `ownerConfirmed`. Persist canon + missing flag → `403 PRODUCTION_CANON_PROTECTED`.
- `GET .../character-json` returns profile + approved sheet + four panel roles + existing identity packet. No third schema.
- Reject of an already-gone draft returns `200` `{ ok, alreadyGone }`.
- Character Reference (`reference_image`) is consumed on the Flux path without 2509 sheet-role fail-close.
- Frontend default generator is Flux. Generate body always sends the 4-view contract. Poll waits for `sheetAssetId` (not the first tile `assetId`).
- Active CRS shows **both** Approved and Draft when they are different images. Approved canon uses Regenerate (no “Update Character Identity” chrome).
- Co-Director leftover remount drops ERS/Scene packs. `JOB_NOT_FOUND` is Dismiss only.

---

## API matrix

| Call | Result |
| --- | --- |
| `POST .../visual-sheet/generate` `layout=four_view` | 4 `CRS_SINGLE_VIEW` Flux tiles. No persist CRS. |
| `GET .../visual-sheet` | Draft pack. `sheetAssetId` only after 2×2 compose. |
| `POST .../approve-candidate` `{ ownerConfirmed: true }` | Persist CRS + Character JSON. Disposable only in automation. |
| `POST .../approve-candidate` missing/false `ownerConfirmed` on existing persist | `403 PRODUCTION_CANON_PROTECTED` |
| `POST .../reject-candidate` | Deletes draft only. Already-gone → `200` `{ alreadyGone: true }` |
| `GET .../character-json` | Existing CRS / identity packet + approved sheet + four panel **labels**. Each `views[*].assetId` is a `crs_derived_crop` when present, otherwise the **same** approved composed sheet id. This path does not invent four crop files. |
| `GET .../characters/{korri}/crs` after API restart | Persist Rev 4 intact (read-only) |

---

## GPU / Comfy evidence

Default route observed on RTX 5090 (prior live pack, later deleted by Playwright `finally`):

- Workflow key: `flux.txt2img` (`flux1-kontext-dev.safetensors` + `ae.safetensors` + DualCLIP, 2048², 20 steps, euler/simple, CUDA)
- Four tiles completed with real `comfy_prompt_id`s; 2×2 compose produced `sheetAssetId=32285f21-d193-475c-9ffe-ad209e7eb239`
- `nvidia-smi` samples: RTX 5090 ~100% / ~29 GB during Flux. No silent CPU.
- Artifacts: `docs/release-gate/character-creator-4view-json/evidence/gpu-*.json`, `gpu-smi-samples.jsonl`, `gpu-four-view-composed.json`

**Environment collision (blocker):** concurrent SenseNova U1.5 smoke keeps occupying Adept-owned Comfy and `Restart-AdeptBetaBackend.ps1 -Service comfyui` at 07:28Z dropped a pending Flux prompt. Interrupt is ignored during SenseNova weight load. After the latest UI Generate, four Flux jobs remain `queued` in Studio while Comfy runs SenseNova (`bfcfd213-...`) and a Flux graph sits pending without a bound `comfy_prompt_id` on those jobs. Evidence: `environment-sensenova-collision.json`, `gpu-jobs-playwright-rerun.json`.

---

## Tests (measured)

| Suite | Result |
| --- | --- |
| `studio-api` 4-view + adversarial + four_view_sheet + reject_character_candidate + crs_single_figure_gate | **54 passed** |
| `studio-web` `src/components/character` vitest | **94 passed** (9 files) |
| Playwright Korri inspect | **PASS** (403 `PRODUCTION_CANON_PROTECTED`; UI Approve hidden). Repeated after API restarts. |
| Playwright disposable Generate → Preview → Reject → Generate → Approve → JSON → Co-Director | **NOT PASSED** — UI Generate created disposable `ca4300c0-...` with four Flux tiles, but Comfy never bound those jobs while SenseNova held `queue_running`. Prior attempts died on `ECONNREFUSED :8758` (external API restart) or lost Flux prompts after a Comfy restart. |

Do not treat unit green as full-stack E2E (Law 31).

---

## Peer review

| Reviewer | Model | Verdict |
| --- | --- | --- |
| A | GLM 5.2 (`glm-5.2-max`) | **READY FOR PRIMARY REVIEW** — all 7 contract points PASS. False-GO risks: live Playwright pending; enqueue spies; structural (not visual) layout check; JSON view `assetId` may collapse to one sheet. |
| B | Kimi K3 (`kimi-k3-max`) | First pass **REJECTED — first-draft Reject blocked**. Follow-up [Kimi K3](ede2c03a-3568-43c9-925e-387809ab8d74) **REJECTED** again: worker-level one-figure gate + silent AUTO-Flux→Qwen fallback on default 4-view tiles. First-draft Reject was already remediating in-tree; worker-gate follow-up below. Disposable Playwright remains environment-blocked. |

Lead remediations from review / live failures (already in tree):

- Hydrate no longer overwrites `composed=True` verification.
- First Flux tile is not the draft (`sheetAssetId` only).
- Reject no longer treats a draft `roleAssets.hero_identity` pointer as canon; Reject clears that pointer.
- `heal_pack_references` does not attach an unapproved draft hero as a profile reference.
- Name-keyed `KORRI_LOCK` identity prompt removed from Generate. Production identity comes from the profile / persist CRS.
- Isolated 5-view law now fail-closes on `_validate_candidate_view_consistency`. Default 4-view tiles keep independent seeds and compose first.
- Worker-level `apply_crs_single_figure_gate_to_job` is advisory/skip on default 4-view pack tiles. AUTO Flux no longer enqueues an untracked `qwen2512.txt2img` fallback on that path. Isolated 5-view still hard-gates. Playwright no longer whitelists `reject-candidate` 4xx.
- Live Generate does not cancel in-flight tiles.
- Playwright health poll does not fail immediately on `ECONNREFUSED`.
- Character JSON view collapse (one composed sheet, four labels) is disclosed in the API matrix.

---

## Limitations

- Hosted Vercel is out of scope.
- 2509 is not a GO gate.
- Korri persist CRS Rev 4 is read-only this closure.
- Structural four-view verify is compose-count + `composed=True`, not a vision “same character” model.
- Character JSON `views.*.assetId` falls back to the single approved sheet unless `crs_derived_crop` rows exist.
- Concurrent SenseNova smokes and external Studio API restarts have interrupted live GPU certification more than once.

---

## E2E TRACE

| Step | Result |
| --- | --- |
| User action (Korri inspect / API-only approve) | PASS |
| Frontend Generate body = 4-view Flux | PASS (unit + live POST) |
| API accept / four tile jobs | PASS |
| Persistence (Generate does not write persist CRS) | PASS (unit) |
| Runtime / GPU four Flux tiles + 2×2 compose | PASS (prior live pack `32285f21-...` on RTX 5090) |
| Result / Preview / Reject / Approve / JSON / reload / Co-Director | FAIL — disposable UI loop never completed on a live draft |
| Korri persist after API restart | PASS (Rev 4 read-only) |

---

## Verdict

```text
BLOCKED BY ENVIRONMENT — Adept-owned Comfy is occupied by concurrent SenseNova U1.5 smokes and Comfy restarts; disposable Playwright Generate→Reject→Approve→JSON never completed. Product contract is implemented and unit-tested. Korri remains read-only (403 PRODUCTION_CANON_PROTECTED).
```
