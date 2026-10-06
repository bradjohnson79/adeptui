# Timeline Whole-Scene Takes System

**Date:** 2026-09-15  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf76693e359cedc60c50c4405daf1b4e3a1` (working tree includes this Takes mission; uncommitted)  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Scene 12B:** `d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`  
**Review URL:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline&sceneId=d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`  
**Studio API:** `http://127.0.0.1:8758/` (`/api/healthz` HTTP 200, PID `33808`)  
**Local creator UI:** `http://127.0.0.1:5173/` (HTTP 200)  
**Comfy `:8188`:** READ-ONLY. PID `34484` before and after. **COMFY RESTARTED?: NO**  
**API recycle:** `scripts/restart_studio_api_only.py` only. Comfy PID unchanged.

This is the governing report for whole-scene Timeline Takes (`+ New Take` vs Re-Take).

---

## Frozen product law

- **Take** = one complete multi-batch render of the current scene (`Take A` … `Take Z` then `Take Z1`).
- **Re-Take** repairs only the **current** Take.
- **New Take** snapshots current production config and regenerates every batch sequentially with continuity. No approval between batches.
- Existing complete render migrates to **Take A** without rerender.
- Only one Take is **Current**. Preview can inspect another Take without changing Current.
- Publish records `sceneId` / `takeId` / `takeLabel` / `batchIds` / `publishedAssetId` from the Current Take.
- MAGI receives the **published master** only. Takes stay Timeline production history.
- Quality (H3 MP / canvas) is frozen on each Take.

---

## Live Scene 12B

| Take | Status | Quality | Result | Notes |
| --- | --- | --- | --- | --- |
| A `stk_281f295b9941` | Ready / Current after cert | H3 2.0 MP · 1920×1088 | `9170c85b-a44a-496d-9434-5082a6ed4f4b` | Migrated from the existing full render. Batch assets `3277533f…`, `5cd44b0a…` unchanged. Historical Visual Re-Takes `rr_9efc603faf02`, `rr_74d70616d2cb` bound to A only. |
| B `stk_43500bfba200` | Cancelled / Incomplete | H3 2.0 MP · 1920×1088 | none | First New Take at 2.0 MP. OOM, then Comfy prompt `c8305366…` stalled 3600s. Stop Jobs → Cancelled. Not Ready. Resume remains available. |
| C `stk_2bf7dd8e8f55` | Ready / Published | H3 0.4 MP · 864×480 | `6f223baa-b8ac-40ff-8629-10db325679a2` | Controlled New Take after owner-allowed quality change. Batch 1 → CandidateReady / NeedsDialogueRetake → auto Batch 2 → stitch. Assets `d95ef9d7…`, `944ab235…`. |

**Published master (after Update Published with C Current):**  
`c60231ae-4923-4c5a-8044-740ca16145cf` · `takeId=stk_2bf7dd8e8f55` · `takeLabel=Take C`

Switching Current back to Take A left that published lineage on Take C.

**MAGI allow list after publish:** published `c60231ae…`, published-source stitch `6f223baa…`, prior upscale `c51066df…`. Take A stitch `9170c85b…` is not allowed. Default MAGI source = published Take C.

---

## Section 25

| Item | Verdict |
| --- | --- |
| TAKES ACCORDION | PASS — Inspector Takes, compact rows, quality lines |
| NEW TAKE BUTTON | PASS — `+ New Take`; disabled while a Take is rendering |
| TAKE A MIGRATION | PASS — no rerender; stitch + batch assets preserved |
| TAKE B FULL RENDER | FAIL at 2.0 MP (OOM + 3600s stall) → Cancelled / Incomplete. Not treated as Ready |
| TAKE C FULL RENDER | PASS — sequential 2-batch New Take at 0.4 MP, ~12 min, Ready + stitch |
| MULTI-BATCH | PASS — Batch 1/2 then auto Batch 2/2; no Approve between batches |
| CONTINUITY | PASS — snapshot `orchestratorMode=sequential_continuity`; Batch 2 queued after Batch 1 CandidateReady; C did not reuse A assets |
| STATUS | PASS — `Rendering Take C — Batch 1/2 — n%` then `2/2`; accordion `Rendering 1/2 — 35%` |
| TAKE LABELS | PASS — A, B, C. Resolver 1→A … 26→Z, 27→Z1 (unit) |
| CURRENT TAKE | PASS — C did not steal Current while rendering; Make Current C; Make Current A; A media intact |
| PREVIEW | PASS — Preview C loaded stitch `6f223baa…` at 864×480 without changing Current |
| RE-TAKE ISOLATION | PASS — unit: repair stamps Current only. Live: Sept 14 `rtclip_*` stay on Take A; Make Current C plays C batches `d95ef9d7…` / `944ab235…`, not A retakes |
| QUALITY SNAPSHOT | PASS — A remains 2.0 / 1920×1088 after C at 0.4 / 864×480 |
| PUBLISH LINEAGE | PASS — Update Published with C Current → `Take C` / `stk_2bf7dd8e8f55`. After Current=A, published still Take C |
| DELETE SAFETY | PASS — delete Current C → 400 `TAKE_DELETE_BLOCKED`. Delete published C while A Current → “This take is published.” |
| RESUME | IMPLEMENTED — Resume on Cancelled B; remaining-batch `force_all` path. Live 2.0 resume did not finish (stall). C did not need Resume |
| SAVE/RELOAD | PASS — A / B / C order, Current, Published badge, quality lines survive Timeline reload |
| CO-DIRECTOR | PASS — `inspect_scene_takes`, `propose_new_scene_take`, `propose_make_scene_take_current`, `propose_preview_scene_take`; grounding for current / published / compare; snapshot `sceneTakes` / `currentSceneTake` / `publishedTake`. No separate CD take database |
| MAGI HANDOFF | PASS — `_allowed_magi_asset_ids` is published master (+ its stitch + upscale) when published exists. Default choose = published Take C |

---

## Tests

- `studio-api/tests/test_scene_takes.py` — **7 passed** (letters, migrate A, next index, adopt legacy retakes onto A only, delete law, retake isolation, rendering take does not inherit prior assets)
- `studio-api/tests/test_scene_publish.py::test_magi_uses_published_master_not_other_take_stitch` — **passed**
- `studio-web` vitest `sceneTakes.test.ts` + `playableVisualTakes.test.ts` — **12 passed** (lettering + playable + filter Re-Takes per Take)

---

## Evidence

- `.runtime/scene_takes_12b_take_c.json` — New Take C launch snapshot (0.4 MP, sequential_continuity, both prompts)
- `.runtime/scene_takes_12b_poll_c.json` — Batch 1 → auto Batch 2 → Ready + result
- `.runtime/scene_takes_12b_cert_after_c.json` — Make Current, publish Take C, switch A, MAGI allow list
- `.runtime/timeline_takes_accordion_12b_take_c_panel.png` — A Current, B Cancelled, C Rendering 1/2
- `.runtime/timeline_takes_12b_c_current_owned.png` — Make Current C monitor (new 0.4 performance, not A retakes)
- `.runtime/timeline_takes_12b_reload_persist.png` — A / B / C after reload

---

## Limitations (honest)

- Take B at H3 2.0 MP / 15s×2 did not complete in this session (OOM, then stall watchdog). History is kept as Cancelled. The certified whole-scene New Take is **Take C at 0.4 MP**.
- Live Re-Take of a marked 5s–8s range was not re-run on 12B this pass; isolation is unit-tested and proven by A-owned `rtclip_*` not following C.
- Live Resume of Take B to Ready was not completed (same 2.0 stall). Resume control and remaining-batch contract are implemented.
- Co-Director tools and grounding are wired to master state; this pass certified via API/snapshot, not a new disposable-project Playwright CD chat.
- Batch chrome may show `NeedsDialogueRetake` after a New Take because auto-approve is off while the new Take is not Current. Playable Current/Preview follow Take membership, not that chrome.

---

## COMFY / runtime

```text
COMFY BEFORE: PID 34484 / health 200
COMFY AFTER:  PID 34484 / health 200
COMFY RESTARTED?: NO
WHY?: Timeline Takes + Studio API recycle only. Desktop Comfy reused, not adopted or killed.
```

---

## FINAL VERDICT

**GO — TIMELINE WHOLE-SCENE TAKES SYSTEM CERTIFIED**
