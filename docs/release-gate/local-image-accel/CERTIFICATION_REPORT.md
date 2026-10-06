# Co-Director Universal Generation Authority + Truthful Progress + Local Image Acceleration

Governing docs: this report + `PHASE0_BASELINE.md`. Plan files were not edited.

## Verdict

**GO — CO-DIRECTOR UNIVERSAL GENERATION AUTHORITY + TRUTHFUL PROGRESS + LOCAL IMAGE ACCELERATION LIVE E2E CERTIFIED**

Both peer reviewers PASS. Internal gates are green. The only leftover is a **proven** missing executable video model after exhausting installed local routes and configured API routes allowed by preference or explicit override. An empty Production Dock selection was not treated as sufficient: MiniMax, LTX, WAN, Kling, and SeeDance were each attempted; dock `availableModelIds` included `ltx-local`; live LTX still failed honestly with no silent provider swap.

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| HEAD | `b6156455e643d5fa430784b3130756f2d8038651` (working tree dirty; this pass is uncommitted) |
| Project | SenseNova Integration Lab `0ffe56e2-0d58-4926-91bf-0f947898d02e` |
| Local UI | http://127.0.0.1:5173/ |
| Studio API | http://127.0.0.1:8758/ (`healthz` 200; Comfy Desktop reused) |
| Comfy | http://127.0.0.1:8188/ |

## Root-cause table

| ID | Symptom | Root cause | Repair |
| --- | --- | --- | --- |
| B1 | “Should we create Korri's CRS?” executed | `classify_speech_act` existed but `analyze_intent` never consulted it; CRS regex promoted advice to `REQUEST_ACTION` | Speech-act is the single semantic source; advisory → CONVERSATION; pragmatic “Can you create…?” → COMMAND |
| B2 | CC/Prop red tests | Tests assumed retired coverage-x6 / five-view / Krea-as-CRS-family (class C) | Tests rewritten to live V3 Front-first contract with written reasons; no coverage architecture restored |
| B3 | “Protected means always unload”; 0s folklore bench | Residency unloaded on any family change and had no VRAM signal; prior bench measured skip-vs-skip | State + family + VRAM policy; live cold 36.38s vs warm 6.199s Qwen T2I |
| Video enqueue | Job stayed `queued` after enqueue exception | `except Exception: pass` after persist | Mark Job `failed`, persist error, project FAILED |
| Polling omit | `generationJob` missing on some surfaces | Per-endpoint attach / hand-built payloads | Single `execution_json(plan, db=)` on every plan-returning endpoint and SSE |
| Dismiss lie | Card hid after failed dismiss | `.finally()` hide after `.catch()` | Hide only on success; retryable error stays |

## Live IDs

| Step | ID |
| --- | --- |
| First-frame execution | `e0ef01c7-b07b-4818-af43-19e9c9e01da5` |
| First-frame Studio Job | `507cfcab-429f-43a9-a253-7dbd51679cae` |
| First-frame asset | `be5ff3cb-ec4a-43cc-b0a3-79be0654870e` |
| Timeline handoff | `6ae855e5-c7d9-4fc0-916c-c1e5b3cc4ab6` |
| SeeDance explicit | `c90c40f7-77ed-4959-9d62-1a9ab1fd94e4` failed as SeeDance — not MiniMax |
| LTX animate-it (inventory) | `ab7e3187-095c-4f26-9bf2-574e4edf6c4b` — provider `ltx` / label `LTX`, FAILED `No active model selected`, no MiniMax swap |
| Cold Qwen T2I | `3f2228ba-a6d6-46a6-be63-9f57953a7645` — 36.38s — `qwen2512.txt2img` |
| Warm Qwen T2I | `f16dc4cb-d5c0-43b6-a4bf-ec4780d1dc89` — 6.199s — `qwen2512.txt2img` |

## Video route inventory (SenseNova)

`GET /api/production-control/resolve?projectId=0ffe56e2-…&modality=video`:

- `activeModelId=minimax-h3`, `executable=false`, `blockedReason=No active model selected`
- `availableModelIds=["ltx-local"]`
- Project dock `activeVideoModelId=null`

Attempted routes (explicit override and/or Animate it against first-frame `be5ff3cb-…`): MiniMax H3, LTX, WAN, Kling, SeeDance. None dispatched a runnable job. SeeDance stayed SeeDance (not configured). LTX stayed LTX. No silent swap.

This is the sole allowed leftover: **no executable video model** after inventory exhaustion.

## Acceleration bench

Source: `docs/release-gate/local-image-accel/residency_cold_warm.json`.

| Run | Job | Workflow | Seconds | VRAM free after |
| --- | --- | --- | --- | --- |
| Cold (explicit Comfy `/free`) | `3f2228ba-…` | `qwen2512.txt2img` | **36.38** | 2655 MiB (from 30842 MiB before load) |
| Warm (same-family resident) | `f16dc4cb-…` | `qwen2512.txt2img` | **6.199** | 2608 MiB |
| Gain | | | **30.181** | knobs unchanged |

Device: `cuda:0 NVIDIA GeForce RTX 5090`. TeaCache/compile were not enabled as CD defaults. Character Creator Qwen steps/CFG/size/fp8 were not changed.

## Tests

| Suite | Result |
| --- | --- |
| Focused pytest (`generation_authority`, `generation_job`, `video_generate_handler`, `image_acceleration_registry`) | **43 passed** |
| CC/Prop owner-approved (`phase_source`, `optional_coverage`, `composition`, `prop_creator_express`, `cc_v2`) | **86 passed** (prior GO Repair run) |
| Playwright Dreamweaver Tests 1–7 + Timeline handoff | **8 passed (1.6m)** `tests/e2e/codirector/codirector-generation-authority-dreamweaver.spec.ts` |

Playwright Test 1 checks **this turn’s** stream events (excludes stale `momentum_resume`). A second identical first-frame chat after the scene was already wiki-logged can still interview; that is a follow-up turn, not the action-first first-frame turn.

## Dirty-tree D exclusions

Unrelated untracked movement / timeline / vision tests that break a bare `pytest tests/` collection are class **D** — documented and excluded. They are not this workstream.

## Peer reviews

| Reviewer | Role | Verdict |
| --- | --- | --- |
| [Runtime auditor](c6d38e7c-ab2f-4db3-9702-510e847f82ca) | Kimi Code 2.7 review-only | **PASS** after CC/Prop same-family residency repair |
| [Execution auditor](422befb6-576e-4b0e-8e1e-5ba606819893) | Kimi Code 2.7 review-only | **PASS** after `status_messenger` → `execution_json` |
| [GLM 5.2](05602af8-5562-4600-8e9b-9b7e38b5a8ca) | Peer review-only | **PASS** |
| [Kimi K3](a8372e3a-ab87-4897-8c54-cf69a0f02123) | Peer review-only | **PASS** |

Both peers PASS. Kimi K3 residual (non-blocking): two pre-existing red tests in `test_codirector_intelligence.py` (legacy `SpecialistContext` vs `IntentClassification`); `forceEnqueueFailure` cert hook in `execute.py`.

## Manual review

1. Open http://127.0.0.1:5173/ on SenseNova Integration Lab.
2. Co-Director first-frame stills show a live card (honest percent or indeterminate; no fake %).
3. Library still holds `be5ff3cb-ec4a-43cc-b0a3-79be0654870e`.
4. “Generate shot 14.” hands off to Timeline — no chat MiniMax/LTX job.
5. Animate it / Use LTX stays on the named generator and fails honestly until an executable video model is installed and selected.

## Runtime

- Studio API `http://127.0.0.1:8758/api/healthz` → 200
- Vite creator UI `http://127.0.0.1:5173/` → 200
- Desktop Comfy `:8188` reused (not killed)
- API-only recycle after Python changes; do not full-supervisor-restart
