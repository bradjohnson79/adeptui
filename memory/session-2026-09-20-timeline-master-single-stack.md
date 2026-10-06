# Session Memory: 2026-09-20 — Timeline + Co-Director Dual-Stack Retirement (Master-only)

Context: Priority-1 mission on Brad's machine (BRAD-5090 / AdeptFilmWorks\AIVideoStudio). Local dirty tree — LOCAL-ONLY; no CloudAgent push of mixed work. API often on `:8758` (lite lifespan); `:8759` returned 401 during CERT smoke.

---

## Primary verdict (banked)

**GO — TIMELINE + CO-DIRECTOR SINGLE-STACK MASTER AUTHORITY CERTIFIED**

Disposable CERT project (NOT Schnick/Korri):
- Project: `523b5c67-7028-4322-9a7a-3d17f2c1a8f9`
- Scene: `f5f346e4-b9a1-4541-912b-8893d0bb7e24`
- Evidence root: `C:\Users\bradj\theme_walk\timeline_master_single_stack\`
  - `phase01_contract_windows\`
  - `phase23_write_read\`
  - `phase45_cert\LIVE_CERT_FINAL_GO.md` (+ `LIVE_CERT_API_TRACE.json`, `LIVE_CERT_CD01_NAV.json`)

Caveat (non-blocker per charter): optional 15s gen+audio skipped — MiniMax `:8192` unreachable; Comfy `:8188` left read-only.

---

## Mission bots (three-phase)

| Bot | Scope | Outcome |
|---|---|---|
| TL Master — Contract+Windows | Phase 0–1 governing note, rematerialize Take-P fence, ceil windows | READY → Primary GO |
| TL Master — WritePath+FE | Phase 2–3 Master-first writes, Inspector Master-read, duration, speech Master-only | READY → Primary GO |
| TL Master — CD+Speech+Cert | Phase 4–5 CD nav + dialogue contract + live CERT | code/unit READY → live CERT GO |

---

## Code landings (do not regress)

1. **CD Timed Prompt → Master-direct** — `studio-api/.../director_timeline_tools.py` (`_upsert_master_timed_prompt`); no `reconcile_legacy_to_master` on add/remove.
2. **Take-P rematerialize fence** — `execution_window_materialize.py` / `_build_batch_blocks`: root keeps scene Timed Prompt; extensions CONTINUATION only (no full-scene clone into every 15s window). Pytest 4/4 (+ phase1 suite → 8 passed reported).
3. **`put_director` Master prompt shim** — inbound `prompt_segments` → Master by start-containment; fail closed `TIMELINE_MASTER_PROMPT_SHIM_FAILED`.
4. **FE Master-FIRST** — `TimelineEditorShell`: `persistBatchPrompts` content compare (`segKey`); Master persist before `putDirector`; undo/redo Master-first.
5. **Inspector / duration / DirectorTracks** — Master-primary Timed Prompt read; no H3 15s product hard reject; unbound prompt saves via mutate (`PHASE23_PROMPT_SAVE_VIA_MUTATE`).
6. **speech_compile Master-only** — generate SoT = `batch.promptSegments`; fail-closed `MASTER_PROMPT_SEGMENTS_REQUIRED` / required speech not silence-locked.
7. **CD01 nav** — Env Creator + Image Generator navigate + fail-closed bogus tab (Playwright live on CERT).

---

## Owner laws added / reinforced this session

- **Law 65 (2026-09-20):** After every finished FE/code task (especially bot patches), parse-check touched TS/TSX before calling done. Vite/oxc overlay parse errors (e.g. double comma `,,`) = incomplete. Prefer esbuild / tsc --noEmit / clean Vite overlay.
- **Parse fix:** `studio-web/src/components/DirectorTracks.tsx` L1693 trailing `,,` from Phase23 mutate patch — fixed; esbuild clean.

---

## Preview Monitor Publish (status clarification)

- New "Publish when all gens complete" bot task was **queued then CEASED** with the hard stop — Chief did **not** ship that narrower ask in the dual-stack mission.
- Product **already has** Preview Monitor Publish chrome: `LivePreviewMonitor` + `TimelinePreviewComposer` → `directorTimelinePublishScene`, gated by Final Check `SCENE_FINISHED` / `SCENE_FINISHED_WITH_ACCEPTED_ISSUES` + scene stitch (`timelineMaster/scenePublish.ts`).
- If owner wants Publish on batch-complete without Final Check, that is still an open ask.

---

## Ceased / parked (owner hard stop earlier)

- Prior TL Audit A01–A12 repair bots — CEASED
- CD↔Timeline E2E smoke (Bot3) — CEASED (Bot1 GO banked only on Schnick Scene2 clear/A/C/D/place)
- Preview Publish *new* button mission — CEASED (re-queue if wanted; see clarification above)
- Do not keep bidirectional sync; do not re-enable generate-path `reconcile_legacy_to_master`

---

## Ops notes

- Comfy `:8188` / MiniMax `:8192` — read-only during CERT (no restart).
- Studio API recycle via ensure-api `:8759` only when healthy; CERT used `:8758` `/health` 200 after `:8759` 401.
- Never spawn `:8742`.
- Sound + character voices always required; silent success when speech exists = defect.
- Timeline batch charter: start-containment; root owns scene Timed Prompt; extensions continuation only.

---

## Related evidence / theme_walk

- Dual-stack: `C:\Users\bradj\theme_walk\timeline_master_single_stack\`
- Parallel Speech Authoring Phase1 A01–A04 GO (separate track): `theme_walk\timeline_audit_repair\phase1_speech_authoring\` — CERT unlock for that track waits Phase2 Completion+Takes.

---

## Follow-ups (not started unless owner reopens)

- Optional live gen+audio CERT when MiniMax `:8192` is up
- Narrower Preview Publish-on-batch-complete (if still wanted)
- `test_timeline_prompt_refs_speech` referenceAssetIds request_builder failures (flagged non-blocker for Phase23 SoT)
- Full lifespan hang root-cause (API often run with lifespan off)
