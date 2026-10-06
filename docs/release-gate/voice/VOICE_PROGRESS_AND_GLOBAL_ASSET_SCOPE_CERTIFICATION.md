# Voice Progress + Global Asset Scope

**Date:** 2026-09-16  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf7` (working tree includes this mission; not committed unless requested)  
**Studio API:** `http://127.0.0.1:8758/` PID 43540  
**Creator UI:** `http://127.0.0.1:5173/`  
**COMFY BEFORE:** PID 34484 (Comfy Desktop) healthy  
**COMFY AFTER:** PID 34484 healthy  
**COMFY RESTARTED?:** NO  
**WHY?:** Ordinary API recycle only (`restart_studio_api_only.py`). `:8188` observed, never restarted.

Supersedes `docs/release-gate/creators/GLOBAL_ASSET_SCOPE_CERTIFICATION.md` as live-wiring evidence.

---

## Projects

| Role | Name | ID |
| --- | --- | --- |
| Owner / Cade | Cade Scenes | `fb24ff0f-8772-4d50-a602-ac69d14b5a6b` |
| Project A | Global Scope A | `4e621501-cd80-498c-85f0-67c7ba9dd921` |
| Project B | Global Scope B | `77a189a3-826f-41fb-ace2-44f8e53035eb` |

---

## VOICE

**PROGRESS SOURCE:** Persisted `voice_generate_job` trait + `GET /api/projects/{projectId}/characters/{characterId}/voice/generate/status`. Frontend polls ~800ms. Not a decorative timer.

**PERCENT:** `derive_percent` from phase + completed samples. Never 100 until `status=complete` and audio candidates exist.

**PHASES:** `preparing` → `analyzing_voice` (clone) → `preparing_model` → `generating_sample` i of n → `saving` → `complete` / `failed`.

**SAMPLE COUNT:** Requested 1–4. Async worker now reads `sampleCount` / `candidateCount` from the **dict payload** (`normalize_design_request` + stamped payload). Live bug found: getattr-on-dict defaulted design jobs to 3. Fixed and re-proved.

**CREATE NEW VOICE:** Live UI — Generate disabled as `GENERATING...`, bar at 6% Preparing recording, then sample phases, then 100% Voice samples ready. Three playable players after the pre-fix 3-sample leak. Corrected 1-sample async job: only `Generating sample 1 of 1`, 1 candidate, 100% on complete.

**CLONE FROM RECORDING:** Prior complete job reconnects on reload (100%, Sample 1 of 1, Play). New clone requires re-choosing the recording file (`cloneFile` is in-memory only). Cancel is not surfaced — mid-GPU cancel is not safely supported.

**FAILURE:** First design attempt (pre-VRAM free) stopped at 18% with the real GPU-memory error. Did not show 100%.

**RELOAD:** Reconnects to queued/running/complete job. Complete candidates restore including DESIGN.

**CONSOLE:** No Adept uncaught exceptions observed on Voice Studio / Image Generator walks.

---

## GLOBAL

**CHARACTER FIELD:** `is_global` (SQL) / `isGlobal` (JSON). Owner `project_id` retained.  
**PROP FIELD:** `is_global` / `isGlobal` on `PropEntity` + `creator_asset_scope`.  
**ENVIRONMENT FIELD:** `isGlobal` on ERS sheet + `creator_asset_scope`.

**CREATE GLOBAL:** CharacterGlobalTest9c1f3f `aedad561-c84e-4807-a589-0ea784f4d00c`, PropGlobalTestLive `5e14688f-710f-423e-ac04-8dc76be03de7`, EnvironmentGlobalTest9c1f3f `16426173-d7bf-4ea2-ba19-6111ab29020d` — all `isGlobal true`, owner Project A.

**UPDATE GLOBAL:** CharacterLocalTest9c1f3f `bb69e112-…` OFF→ON same ID, then ON→OFF same ID.

**GLOBAL OFF:** After OFF, entity disappears from Project B list; ID unchanged.

**PROJECT QUERY:** `list_profiles` / `list_visible_props` / `list_visible_sheets` = local OR `is_global`. One query. Deduped by entity ID.

**LIBRARY/BACKING FILE ACCESS:** `GET /api/projects/{viewingProject}/assets/{assetId}/file` via `resolve_readable_asset` (characterId / propId / environmentId / sheet / trait / identity). Not whole-library open.

**TIMELINE:** Project B Cast (3): Cade O'Connor, CharacterGlobalTest9c1f3f, TestGlobalCharacterf2dc3af3. Locals absent.

**IMAGE GENERATOR:** Project B selectors — `@CadeOConnor` (`85e37d4b-…`) + `#AnadriyaSQuarters` (`84ef72cb-…`). `referenceAssetIds`: `b6565a04-…`, `e4c10cdb-…`. Both images loaded (2560×1080 and 1672×941) from Project B file URLs.

**CO-DIRECTOR:** Same snapshot lists. Project B: “This project can use global characters Cade O'Connor, CharacterGlobalTest9c1f3f, TestGlobalCharacterf2dc3af3; global props PropGlobalTestLive, TestGlobalPropf2dc3af3; global environments EnvironmentGlobalTest9c1f3f, Anadriya's Quarters, TestGlobalEnvf2dc3af3.”

**CHARACTER ANGLES:** From B, `cc-v2` 200 (was 403 owner-lock). Front / side / 3/4 / back / sheet file GET 200.

**PRS:** Test global props have no approved sheet (listed, disabled “no image”). Scope field + identity_asset_id path is wired. No 403 thumbnail.

**ERS:** Anadriya ERS `e4c10cdb-fc70-453f-84d1-d639dbcec09c` 200 from B (2,258,553 bytes). Test env sheets have no composite.

**TAG COLLISION:** `find_tag_collision` 409 — no silent bind.

**REFERENCE DURABILITY:** `load_entity_for_reference` resolves by canonical ID after Global OFF.

**DELETE SAFETY:** Character + Prop call `require_delete_safety` (409 GLOBAL_IN_USE unless confirm). Environment has no delete API.

**SAVE/RELOAD:** Hard reload Project B Image Generator — same global lists, locals still hidden.

**CROSS-PROJECT E2E:** Create / list / toggle / IG select / Timeline cast / CD ask / file GET / reload — PASS.

---

## SMOKE TEST REPORT

**VOICE SMOKE:**  
Create New: PASS (live bar + 3 playable samples; count leak fixed after).  
Clone: PASS reconnect + play; new file pick required for a second clone.  
1 sample: PASS after fix (`Generating sample 1 of 1`, 1 candidate).  
3 samples: PASS (UI produced samples 1–3 + Play).  
Progress: PASS honest phases/percent.  
Completion: PASS 100% only with audio.  
Playback: PASS Play → Pause sample 1.  
Errors: first GPU fail honest; later jobs clean.

**GLOBAL CHARACTER:** A=`aedad561-…` + Cade `85e37d4b-…`. B sees both. ID preserved. CRS/angles resolve. Timeline Cast + Image Generator + Co-Director. Reload PASS.

**GLOBAL PROP:** A=`5e14688f-…`. B lists same ID. No PRS bytes on test props. Downstream list PASS. Reload PASS.

**GLOBAL ENVIRONMENT:** A=`16426173-…` listed on B. Anadriya ERS selectable + image loads. Reload PASS.

**LOCAL NEGATIVE:** CharacterLocalTest / PropLocalTest / EnvironmentLocalTest absent on B; present on A.

**GLOBAL→LOCAL / LOCAL→GLOBAL:** CharacterLocalTest same ID, visibility flips.

**NETWORK / CONSOLE:** Healthz 200, Vite 200, Comfy stats 200. No broken image 403s on walked surfaces. No request storms observed.

---

## FINAL VERDICT

**GO — VOICE PROGRESS + GLOBAL ASSET SCOPE CERTIFIED**

**GO — LIVE WIRING SMOKE TEST CERTIFIED**
