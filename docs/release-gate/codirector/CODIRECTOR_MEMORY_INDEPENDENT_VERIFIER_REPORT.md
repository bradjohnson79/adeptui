# Co-Director Persistent Memory — Independent Verifier Report

---

## CURRENT — Waves B–E / Layer 3 (2026-08-05 05:36 UTC)

> **Verifier:** Independent Composer 2.5 (did NOT implement Waves B–E or Layer 3).
> **Run ID:** `verifier-20260805T053600Z`
> **Scope:** Waves B–E unit tests, Layer 3 learning evolution, Layer 3 UI, reload-persistence on live Beta.
> **Beta:** http://127.0.0.1:8760/ · API: http://127.0.0.1:8758/

### Verdict

```text
READY FOR PRIMARY REVIEW — WAVES B–E / LAYER 3 INDEPENDENTLY CORROBORATED ON LIVE BETA
```

Independent verifier does **not** issue program GO or flip graduation.

### Preflight

| Check | Result |
| --- | --- |
| Web 8760 | HTTP 200 |
| API health | HTTP 200 |
| `selectedModel` | `qwen3.6:35b-a3b` (colon present) |
| `modelAvailable` | true |
| `GET /api/codirector/m212/status` | HTTP 200, `enabled: true` (not 404) |
| Post-test config guard | Colon intact, model still available |

### Independent re-runs (`retries=0`, `ADEPT_BETA_TARGET=1`)

| Layer | Files | Result | Exit | Duration |
| --- | --- | --- | --- | --- |
| Waves B–E (pytest) | `test_codirector_waves_b_e.py` | **PASS** (7 passed) | 0 | ~5s |
| Layer 3 learning (pytest) | `test_codirector_layer3_learning_evolution.py` | **PASS** (1 passed — 10 critique→promote cycles, isolation, export/import, retire) | 0 | (combined 8 passed) |
| Layer 3 UI (Playwright) | `codirector-memory-layer3-ui.spec.ts` | **PASS** (export/audit/view-source wired) | 0 | 2.3s |
| Reload persistence (Playwright) | `codirector-reload-persistence-race.spec.ts` | **PASS** (no truncation on reload) | 0 | 3.1s |

Combined pytest: **8 passed, exit 0** (5.58s). Combined Playwright: **2 passed, exit 0** (5.8s).

Artifacts:

- `docs/release-gate/codirector/artifacts/verifier-waves-be-layer3-pytest.txt`
- `docs/release-gate/codirector/artifacts/verifier-waves-be-layer3-playwright.txt`

### Cross-reference — implementer certification

Implementer doc `CODIRECTOR_MEMORY_EVOLUTION_CERTIFICATION.md` claims GO seeds for Waves B–E and Layer 3. Independent re-runs **match** implementer counts (8 pytest, Layer 3 UI + reload PASS on live Beta). m212 status endpoint live and enabled.

### Wave B–E scope corroborated (pytest)

- Compaction + fold skip
- Revision poll / SSE route contracts
- Memory export/import + intelligence snapshot
- Audit/repair paths
- M2.12 10-cycle promote/retire with **project isolation** (isolation project lessons unaffected)

### Limitations

- Layer 2 full 100-iter race cert not re-run in this Waves B–E pass (Wave A accepted by primary `verifier-20260805T042330Z`).
- Graduation dramatic-scene spec **not** re-run this session.
- Verifier did not mutate product source or operator config.

### Return

**READY FOR PRIMARY REVIEW**

Waves B–E / Layer 3: independent evidence supports PASS for memory evolution gates. Program Master remains subject to graduation and final-systems gates (see `ADEPT_UI_FINAL_ALL_GO_INDEPENDENT_VERIFIER.md`).

---

## Wave A — Intelligence Engine / conversation durability (historical)

> **Independent verification of Wave A (Intelligence Engine / conversation durability).**
> **Verifier:** Independent verify agent (did NOT implement Wave A).
> **Run ID:** `verifier-20260805T042330Z`
> **Date (UTC):** 2026-08-05 04:23–04:30
> **Repo:** `C:\AdeptFilmWorks\AIVideoStudio`
> **Protected project (never mutated):** `77a4b96c-8e3f-4501-897c-51bab99bedb7`
> **Beta:** http://127.0.0.1:8760/  API: http://127.0.0.1:8758/

## 0. Verdict

```text
GO — WAVE A INTELLIGENCE ENGINE / PERSISTENT MEMORY PROVEN AGAINST LIVE BETA
```

Layer 1 PASS (independently re-run). Layer 2 PASS against the instructed live
Beta target (`ADEPT_BETA_TARGET=1`, `retries=0`, 100 UI iterations). Reload-
persistence regression PASS against live Beta. Post-Layer 2 config regression
guard PASS (`qwen3.6:35b-a3b` colon intact, no mangling). Checklist 11/11 PASS.
Wave B is **UNBLOCKED** pending primary review. Program Master remains **NO-GO**
until Waves B–E complete.

## 1. Beta / API health

| Endpoint | Status |
| --- | --- |
| `http://127.0.0.1:8760/` (web) | 200 |
| `http://127.0.0.1:8758/` (API) | 200 |
| `http://127.0.0.1:8758/api/health` | 200 — ComfyUI ready, operator ollama `qwen3.6:35b-a3b` reachable |

Beta was already running and was NOT restarted or mutated by the verifier.

## 2. Layer 1 — independent re-run (deterministic API)

- **File:** `studio-api/tests/test_codirector_persistent_memory_race.py`
- **Command:** `studio-api\.venv\Scripts\python.exe -m pytest tests/test_codirector_persistent_memory_race.py -q --tb=short`
- **Artifact:** `artifacts/persistent-memory/verifier-20260804T202649Z/layer1_pytest.txt`

```
...............                                                          [100%]
15 passed, 5 warnings in 167.50s (0:02:47)
PYTEST_EXIT=0
```

**Result: PASS.** 15 test functions × 100 iterations = 1,500 assertions
(12 race scenarios × 100 = 1,200 + 3 guards × 100 = 300). Exit 0. No retries
as pass. No truncation, loss, duplication, cross-project leak, reorder, or
pass-on-retry observed. Matches the implementer's reported `15 passed`.

## 3. Layer 2 — independent run against live Beta (as instructed)

- **File:** `tests/e2e/codirector/codirector-memory-race-certification.spec.ts`
- **Command:** `npx playwright test codirector/codirector-memory-race-certification.spec.ts --project=chromium --workers=1 --retries=0` with `ADEPT_BETA_TARGET=1`, `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760`, `STUDIO_API_BASE=http://127.0.0.1:8758`
- **Artifact:** `artifacts/persistent-memory/verifier-20260804T202649Z/layer2_playwright.txt`

```
Running 1 test using 1 worker
  x  1 [chromium] › ...codirector-memory-race-certification.spec.ts:305:7 › ...100 UI iterations... (0ms)
  Error: expect(received).toBeTruthy()
    > 49 |   expect(res.ok()).toBeTruthy();
      at setMockScenario (...codirector-memory-race-certification.spec.ts:49:20)
      at ...:298:5  (beforeAll)
  1 failed
PLAYWRIGHT_EXIT=1
```

**Result: FAIL against Beta.** The spec's `beforeAll` calls
`setMockScenario(request, null)` → `POST /api/e2e/codirector/scenario`, which
returns **404** on the live Beta because the e2e router is mounted only when
`STUDIO_E2E` is set (`studio-api/app/main.py:489`), and the Beta supervisor
hard-sets `STUDIO_E2E=0` (`scripts/beta_runtime/supervisor.py:397`) and strips
it (`scripts/beta_runtime/envutil.py:59`). Even if the route existed, the mock
Co-Director provider is gated behind `e2e_enabled()`
(`studio-api/app/codirector/service.py:95-101,113`) and is unavailable on Beta,
so `sendChatTurn` would fall through to the real ollama provider — not the
stubbed `[mock]` replies the spec assumes.

The canonical Beta runner (`scripts/run-playwright-beta.mjs`) likewise does
**not** set `STUDIO_E2E`, confirming the production Beta target is intentionally
non-e2e.

## 4. Layer 2 — diagnostic run in the isolated e2e harness

Because the spec was authored for the isolated e2e harness
(`STUDIO_E2E=1`, mock provider — per the implementer's own report:
"Provider: mock (default under STUDIO_E2E=1)"), the verifier re-ran the same
spec in that native environment as a diagnostic to determine whether the spec
itself is sound.

- **Command:** `npx playwright test codirector/codirector-memory-race-certification.spec.ts --project=chromium --workers=1 --retries=0` with `STUDIO_E2E=1` (no `ADEPT_BETA_TARGET`)
- **Artifact:** `artifacts/persistent-memory/verifier-20260804T202649Z/layer2_playwright_e2e_harness.txt`

```
[WaveA L2] distribution {
  send_before_load: 9, rapid_sends: 9, reload_mid_response: 9, delayed_append: 9,
  duplicate_retry: 8, concurrent_tabs: 8, project_switch_mid_send: 8,
  refresh_after_send: 8, api_restart_sim: 8, hundreds_of_messages: 8,
  out_of_order_tool_assistant: 8, summary_during_send: 8
}
  ok 1 [chromium] › ...100 UI iterations... (1.6m)
  1 passed (1.9m)
PLAYWRIGHT_E2E_EXIT=0
```

**Result: PASS in the isolated e2e harness.** All 12 scenarios exercised (8–9
iterations each, total 100). Exit 0. The spec is structurally sound in its
intended environment. (A first attempt failed with `EADDRINUSE` on 8742/8765
from leftover harness processes; after cleaning those PIDs the clean retry
passed. That was an environment issue, not a spec issue.)

## 5. Reload-persistence regression spec (against live Beta)

- **File:** `tests/e2e/codirector/codirector-reload-persistence-race.spec.ts`
- **Command:** as above with `ADEPT_BETA_TARGET=1` (Beta target, real ollama provider)
- **Artifact:** `artifacts/persistent-memory/verifier-20260804T202649Z/layer2_reload_persistence_race.txt`

```
  ok 1 [chromium] › ...send before async load completes never truncates server conversation on reload (3.8s)
  1 passed (4.3s)
RELOAD_EXIT=0
```

**Result: PASS against Beta.** Seeds a 4-message history via the deprecated
`POST /conversations/{id}` (now append-merge), sends a real LLM turn before
async load completes, reloads, and asserts all seeded ids survive. This
independently confirms the Wave A event store is **live on the real Beta DB**
and that the append-merge path does not truncate through a real provider turn
and a reload.

## 6. Wave A GO checklist — audited against code + evidence

| # | Gate item | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Migration complete (M028 registered) | **PASS** | `studio-api/app/migrations/__init__.py:29,33` registers `M028`; `m028_codirector_conversation_events.py` creates table + `revision` + backfill |
| 2 | `messages_json` migrated & verified | **PASS** | `_backfill_events` is idempotent (message_id skip) + header revision bump; Layer 1 fold/idempotency assertions pass |
| 3 | No unguarded transcript-replacement in creator use | **PASS (server-side)** | `service.save_conversation` non-admin path is append-merge by id (never truncates); admin replace requires matching `expected_revision`. Client send flow uses `appendUserTurn` (`POST /events`) + `reconcileConversation` (GET). Note: client `persistMessages` still calls the deprecated `codirectorSaveConversation`, but the server path is append-merge so it cannot truncate. |
| 4 | Creator append idempotent | **PASS** | Unique partial indexes `ux_convo_events_client_request` + `ux_convo_events_message_id`; `append_events` returns `duplicate_count`; Layer 1 scenario 5 + Layer 2 `duplicate_retry` (e2e harness) pass |
| 5 | Assistant completion server-side | **PASS** | `chat_for_project` (service.py:889,941) and `stream_for_project` (service.py:1144) call `append_assistant_completion`; Layer 1 `test_chat_appends_assistant_server_side` passes |
| 6 | Tool calls/results appended | **PASS** | `append_tool_event` builds tool_call+tool_result event pair; Layer 1 scenario 11 + Layer 2 `out_of_order_tool_assistant` (e2e harness) pass |
| 7 | Concurrent tabs no truncation | **PASS** | Server-assigned sequence + idempotency; Layer 1 scenario 6 + Layer 2 `concurrent_tabs` (e2e harness) pass |
| 8 | Retry no duplicates | **PASS** | Idempotency indexes; Layer 1 scenario 5 + 409-conflict guard + Layer 2 `duplicate_retry` pass |
| 9 | Layer 1 1200 PASS | **PASS** | Independent re-run: `15 passed in 167.50s`, exit 0 |
| 10 | Layer 2 100 UI PASS | **FAIL against Beta / PASS in e2e harness** | Against the instructed Beta target: FAIL (beforeAll 404, `STUDIO_E2E=0`). In the isolated e2e harness: PASS (100 iterations, 1.9m, exit 0). |
| 11 | Do NOT self-cert | **PASS** | Verifier is independent of the implementer; this report is the independent verdict |

**Checklist result:** 10/11 PASS. Item 10 fails against the Beta certification
target as instructed. The durability logic itself is fully proven (items 1–9
plus e2e-harness Layer 2 plus the Beta regression spec).

## 7. Why NO-GO (honest reasoning)

The user's instruction #3 explicitly specified the live Beta as the Layer 2
target. The spec cannot run there because it requires `STUDIO_E2E=1` + the
mock provider, both deliberately disabled on production Beta. This is not a
durability failure — it is a **certification-target mismatch**: the Layer 2
spec was written for the isolated e2e harness, but the certification target is
live Beta. Per the binary rule, Layer 2 did not pass against the instructed
target, so Wave A cannot be declared GO by the independent verifier.

This is deliberately distinguished from a "durability is broken" NO-GO:
- Layer 1 independently PASS (1,200 + 300 assertions).
- Layer 2 PASS in its native e2e harness (100 UI iterations).
- The reload-persistence regression spec PASS against live Beta with a real
  LLM turn and reload, proving the event store is live on the Beta DB and
  append-merge does not truncate.
- All code-level checklist items (migration, no-full-replace, server-side
  assistant, idempotency, tabs, retry) verify against the source.

## 8. Remediation to flip Wave A to GO

One of the following (the primary agent decides; the verifier does NOT pick):

1. **Make the Layer 2 spec Beta-compatible.** Drop the
   `/api/e2e/codirector/scenario` dependency (the scenarios that only need
   ordering/idempotency don't need a mock scenario), and either run against the
   real ollama provider on Beta (slow but real) or add a Beta-exposed,
   auth-gated mock-scenario control. Then re-run the full 100 iterations
   against Beta.
2. **Formally designate the isolated e2e harness as the Layer 2 certification
   environment** for Wave A, with documented rationale that production Beta
   intentionally disables the mock provider, and that the reload-persistence
   regression spec covers the real-Beta path. Update the program status and
   this report accordingly, then re-issue the verdict.
3. **Add a Beta-target Layer 2 variant** that uses the real provider and
   asserts only the durability invariants (growth, no-loss, idempotency,
   cross-project isolation) without depending on mock scenarios.

Until one of these is done and Layer 2 passes against the agreed target,
Wave A stays NO-GO and Wave B stays blocked.

## 9. Live-Beta migration probe (Wave A is live on the Beta DB)

The verifier probed the live Beta API to confirm M028 is applied in production
(not just in the Layer 1 temp DB):

```
POST /api/codirector/conversations/<id>/events  → 200
  {"appendedCount":1,"duplicateCount":0,"revision":1,
   "events":[{"id":"probe-u-1","role":"user","content":"probe",...}]}
GET  /api/codirector/conversations/<id>          → 200
  {"messages":[...],"revision":1,...}
```

`revision` is returned and bumped on append — the `codirector_conversation_events`
table and the `revision` column are live on the Beta DB. The reload-persistence
spec passing against Beta (section 5) independently confirms this.

**Cleanup note (operator action required):** the probe left a disposable temp
project named `waveA-verify-probe` and an orphan conversation header for
project_id `38752` (a PowerShell `$pid` automatic-variable collision sent the
append to the shell's process id instead of the created project id). Neither
is the protected project. They are harmless but should be deleted by the
operator. The verifier did not force the deletion (auto-review blocked the
cleanup call; the verifier chose not to escalate).

## 10. Artifacts

Under `docs/release-gate/codirector/artifacts/persistent-memory/verifier-20260804T202649Z/`:

- `layer1_pytest.txt` — Layer 1 independent re-run (15 passed, exit 0)
- `layer2_playwright.txt` — Layer 2 against Beta (FAIL, beforeAll 404)
- `layer2_playwright_e2e_harness.txt` — Layer 2 in e2e harness (PASS, 100 iters)
- `layer2_reload_persistence_race.txt` — reload-persistence regression vs Beta (PASS)
- `verifier-summary.md` — short summary

## 11. Return

**READY FOR PRIMARY REVIEW.**

- Layer 1 exit: **0** (PASS, 15 passed)
- Layer 2 (Beta target) exit: **1** (FAIL — spec incompatible with Beta)
- Layer 2 (e2e harness, diagnostic) exit: **0** (PASS, 100 iterations)
- Reload-persistence regression (Beta) exit: **0** (PASS)
- Checklist: 10/11 PASS; item 10 FAIL against Beta target
- **Wave A: NO-GO** — Layer 2 not proven against the Beta certification target
  as instructed. Wave B remains blocked. Durability logic itself is proven;
  remediation is a spec/certification-target fix, not a durability repair.

---

## 9. Re-verify after Layer 2 Beta remediation (2026-08-05)

> **Verifier:** Fresh independent re-verify agent (did NOT implement the Layer 2
> remediation; did NOT modify product source). Run ID `verifier-20260804T204933Z`.
> Full detail: `docs/release-gate/codirector/artifacts/persistent-memory/verifier-20260804T204933Z/verifier-summary.md`.

### 9.1 Verdict: **NO-GO** — Layer 2 still not reproducible against live Beta.

The implementer remediated the spec (guarded the mock-scenario reset behind
`!BETA_TARGET`, raised the per-test timeout) and claimed Layer 2 Beta PASS
(2.1m, 100 UI iterations, exit 0). The fresh independent re-verify could NOT
reproduce that result.

### 9.2 Results (own re-runs, `retries=0`)

| Layer | Target | Result | Exit | Duration |
| --- | --- | --- | --- | --- |
| Layer 1 (pytest) | studio-api temp DB | **PASS** (15 passed) | 0 | 187.28s |
| Layer 2 (Playwright) | Live Beta (`ADEPT_BETA_TARGET=1`) | **FAIL** at iteration 1/100 | 1 | 129.2s |
| Reload-persistence regression | Live Beta | **FAIL** (Expected >=5, Received 4) | 1 | 34.2s |

### 9.3 Root cause (environment/provider, not durability code)

The live Beta's Co-Director selected ollama model **`gemma4:31b-it-qat` is NOT
installed**. `GET /api/health` → `operator.provider.modelAvailable: false`,
`selectedModel: "gemma4:31b-it-qat"`. The only installed ollama model is
`qwen3.6:35b-a3b` (confirmed via `/api/codirector/providers/ollama/models` and
ollama `/api/tags`). The Co-Director UI header reads
`gemma4-31b-it-qat - Model Unavailable` and the chat surfaces "Request failed.
The selected model 'gemma4:31b-it-qat' is not installed." (confirmed in both
failure screenshots). The real chat returns a model-missing error instead of a
reply, so `sendChatTurn` times out at 120s (Layer 2) and the turn is not
persisted (reload). The durability contract itself holds: Layer 1 PASS and the
reload test confirmed the seeded 4-message history was not truncated.

### 9.4 GO checklist (auditor view): 10/11 PASS — item 10 FAIL

Items 1–9 and 11 PASS (audited against source + Layer 1 re-run). Item 10
(Layer 2 100 UI PASS against Beta) FAIL in the verifier's own re-run.
Observation (not a Wave A blocker): `append_tool_event` is defined but not yet
invoked by the live tool-execution path; live tool-event persistence is a
Wave B+ concern.

### 9.5 Remediation path (for primary/operator — verifier does NOT pick/mutate)

1. Make the Co-Director selected model available on Beta: `ollama pull
   gemma4:31b-it-qat`, or switch the selected model to the installed
   `qwen3.6:35b-a3b`.
2. Re-confirm `GET /api/health` → `operator.provider.modelAvailable: true`.
3. Re-run Layer 2 + reload-persistence on Beta with `ADEPT_BETA_TARGET=1`,
   `retries=0`.
4. Only if both pass may a fresh verifier issue Wave A GO.

### 9.6 Cleanup note

The verifier's failed runs left disposable temp projects on the Beta DB
(`WaveA L2 send_before_load 0 ...`, `CoDir Reload Race ...`). The verifier did
not auto-delete remote projects (out of scope). The operator should delete
them. The protected project `77a4b96c-8e3f-4501-897c-51bab99bedb7` was never
touched.

### 9.7 Final

- Layer 1 exit: **0** (PASS, 15 passed, 187.28s)
- Layer 2 (Beta target) exit: **1** (FAIL at iteration 1/100 — ollama model missing)
- Reload-persistence regression (Beta) exit: **1** (FAIL — chat turn not persisted)
- Checklist: 10/11 PASS; item 10 FAIL against Beta target
- **Wave A: NO-GO** — Layer 2 not reproducible against the live-Beta target
  because the Co-Director's selected ollama model is not installed. Wave B
  remains BLOCKED. The durability logic itself is proven (Layer 1 PASS;
  seeded history not truncated); the blocker is operator provider/model
  availability on Beta, not a Wave A code defect.


---

## Second independent re-verify (2026-08-05 04:09 UTC) -- Run ID `verifier-20260805T040100Z`

**Verifier:** Fresh independent re-verify agent (did NOT implement Wave A; did
NOT modify product source or operator config).
**Verdict: NO-GO** -- Wave A Layer 2 not reproducible against the instructed
live-Beta certification target.

### Context

A prior independent verifier (`verifier-20260804T204933Z`) issued NO-GO because
live Beta Co-Director had `selectedModel=gemma4:31b-it-qat` with
`modelAvailable: false` (only `qwen3.6:35b-a3b` installed). The primary has
since switched Co-Director config to the installed model. This re-verify was
launched to confirm.

### Preflight (per mandate, BEFORE tests) -- PASSED at 04:00:39 UTC

- `GET /api/health` -> `operator.provider.modelAvailable: true`,
  `selectedModel: qwen3.6:35b-a3b`, status `Ready`.
- `GET /api/codirector/config` -> `selectedModel: qwen3.6:35b-a3b` (installed).
- `GET http://127.0.0.1:11434/api/tags` -> only `qwen3.6:35b-a3b` installed.
- `GET http://127.0.0.1:8760/` -> HTTP 200; `GET /api/health` -> HTTP 200.

Preflight matched the user's claim. Tests were started. **The healthy state was
transient** -- the config reverted and the Beta services collapsed
mid-certification.

### Results (own re-runs, `retries=0`)

| Layer | Target | Result | Exit | Duration |
| --- | --- | --- | --- | --- |
| Layer 1 (pytest) | studio-api temp DB (`STUDIO_E2E=1`, mock) | **PASS** (15 passed) | 0 | 198.85s |
| Layer 2 (Playwright race cert) | Live Beta (`ADEPT_BETA_TARGET=1`, real ollama) | **FAIL** at iteration 1/100 (`send_before_load`) | 1 | 129.4s |
| Reload-persistence regression | Live Beta (real ollama) | **FAIL** (`ECONNREFUSED 127.0.0.1:8758` -- API down) | 1 | 2.2s |

### Root cause: persisted config reverted to the uninstalled default; Beta then collapsed

- The persisted file `data/codirector_config.json` (mtime 04:02:41 UTC)
  contains `gemma4:31b-it-qat` -- something wrote the uninstalled default back
  AFTER the healthy 04:00:39 UTC reading. The default comes from
  `settings.ollama_model` in `studio-api/app/config.py:36`.
- By the time Layer 2 ran, `/api/health` showed `selectedModel:
  gemma4:31b-it-qat`, `modelAvailable: false`, `status: "Model Missing"`. The
  UI showed "model not installed"; `sendChatTurn` timed out at 120s on iter 1
  (same mode as the prior verifier).
- The reload run failed with `ECONNREFUSED 127.0.0.1:8758`. A final sweep at
  04:08:31 UTC showed BOTH Studio API (8758) and Beta web (8760) DOWN (HTTP
  000); only Ollama (11434) was up with `qwen3.6:35b-a3b` installed.
- This is an environment/operator-config blocker, not a Wave A durability
  defect. Layer 1 (15 passed, 1,500 assertions, exit 0) independently PASSes.

### Wave A GO checklist (1-11) -- auditor view: 10/11 PASS, item 10 FAIL

| # | Gate item | Status |
| --- | --- | --- |
| 1 | Migration complete (M028 registered) | PASS |
| 2 | `messages_json` migrated & verified | PASS |
| 3 | No unguarded transcript-replacement in creator use | PASS |
| 4 | Creator append idempotent | PASS |
| 5 | Assistant completion server-side | PASS |
| 6 | Tool calls/results appended | PASS (contract; observation: `append_tool_event` not yet invoked live -- Wave B+) |
| 7 | Concurrent tabs no truncation | PASS |
| 8 | Retry no duplicates | PASS |
| 9 | Layer 1 1200 PASS (independent re-run) | PASS (15 passed, exit 0, 198.85s) |
| 10 | Layer 2 100 UI PASS against Beta | **FAIL** (iter 1; model unavailable; then API/web down) |
| 11 | Do NOT self-cert | PASS |

### Remediation path (for primary/operator -- verifier does NOT pick/mutate)

1. Persistently switch the Co-Director config to the installed `qwen3.6:35b-a3b`
   (verify `data/codirector_config.json` on disk reflects it durably across
   restart), OR `ollama pull gemma4:31b-it-qat`, OR change the default
   `settings.ollama_model`.
2. Investigate and fix the config revert (writer at 04:02:41 UTC).
3. Stabilize the Beta environment (8758 + 8760 went DOWN mid-session).
4. Re-confirm `GET /api/health` `operator.provider.modelAvailable: true` AND
   stays true across an API restart.
5. Re-run Layer 2 + reload-persistence on Beta with `ADEPT_BETA_TARGET=1`,
   `retries=0`.
6. Only if both pass may a fresh verifier issue Wave A GO.

### Artifacts

`docs/release-gate/codirector/artifacts/persistent-memory/verifier-20260805T040100Z/`:
- `env_health.txt`, `layer1_pytest.txt`, `layer2_playwright_beta.txt`,
  `layer2_reload_persistence_race_beta.txt`, `verifier-summary.md`

### Verdict

**NO-GO.** Wave B remains BLOCKED. Program Master remains NO-GO until Waves A-E.

READY FOR PRIMARY REVIEW

---

## Third independent verify — Intelligence Engine Wave A (2026-08-05 04:30 UTC)

**Run ID:** `verifier-20260805T042330Z`
**Verifier:** Fresh independent verifier (did NOT implement Wave A; did NOT modify
product source or operator config).
**Verdict: GO**

### Context

Prior re-verify (`verifier-20260805T040100Z`) issued NO-GO because the persisted
Co-Director config reverted to uninstalled `gemma4:31b-it-qat` mid-session and
Beta services collapsed. Product fix: live Ollama dock ids now use
`ollama-tag:<exactTag>` and `llm_ollama_for_dock_model` round-trips the colon;
`test_ollama_dock_tag_roundtrip.py` added. This verify confirms the fix holds
under full Wave A certification.

### Preflight (BEFORE tests) — PASSED at 04:23:30 UTC

| Check | Result |
| --- | --- |
| `GET /api/health` `modelAvailable` | **true** |
| `GET /api/health` `selectedModel` | **`qwen3.6:35b-a3b`** (colon present) |
| `GET /api/codirector/config` | **`qwen3.6:35b-a3b`** |
| On-disk `data/codirector_config.json` | **`qwen3.6:35b-a3b`** |
| Ollama `/api/tags` | **`qwen3.6:35b-a3b`** present |
| Beta 8760 / API 8758 | HTTP **200** |

### Results (own re-runs, `retries=0`)

| Layer | Target | Result | Exit | Duration |
| --- | --- | --- | --- | --- |
| Layer 1 (pytest) | `test_codirector_persistent_memory_race.py` + `test_ollama_dock_tag_roundtrip.py` | **PASS** (18 passed) | 0 | 191.15s |
| Layer 2 (Playwright) | Live Beta (`ADEPT_BETA_TARGET=1`) | **PASS** (100 UI iterations) | 0 | 1.9m |
| Reload-persistence | Live Beta | **PASS** (1 passed) | 0 | 3.2s |

### Post-Layer 2 regression guard — PASS at 04:30:00 UTC

`selectedModel` remained `qwen3.6:35b-a3b` on health, config API, and disk.
No tag mangling.

### Wave A GO checklist (1–11): 11/11 PASS

All items PASS including item 10 (Layer 2 100 UI PASS against Beta).

### Artifacts

`docs/release-gate/codirector/artifacts/persistent-memory/verifier-20260805T042330Z/`

### Final

- Layer 1 exit: **0** (PASS, 18 passed)
- Layer 2 (Beta target) exit: **0** (PASS, 100 iterations)
- Reload-persistence (Beta) exit: **0** (PASS)
- Post-Layer 2 config guard: **PASS**
- Checklist: **11/11 PASS**
- **Wave A: GO** — Wave B **UNBLOCKED** pending primary review

READY FOR PRIMARY REVIEW

---

## Primary acceptance — Wave A (2026-08-05)

Primary reviewed [Wave A verifier](226a80ce-8868-455d-9ab4-2cc66e140986) evidence
`verifier-20260805T042330Z` (Layer 1/2/reload logs + summary; live config still
`qwen3.6:35b-a3b` with colon).

```text
GO — WAVE A INTELLIGENCE ENGINE / PERSISTENT MEMORY ACCEPTED BY PRIMARY
```

Wave B is **UNBLOCKED**. Program Master remains **NO-GO** until Waves B–E.
