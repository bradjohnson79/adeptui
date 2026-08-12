# Co-Director Persistent Memory — Unified Report

> **Authoritative unified report for the Co-Director Persistent Memory initiative.**
> This file is the single current source of truth for program status and per-wave results.
> Maintained by the primary agent from implementer + independent verifier outputs.

## CURRENT AUTHORITATIVE STATUS

```text
GO — Wave A Intelligence Engine / Persistent Memory (PRIMARY ACCEPTED 2026-08-05)
NO-GO — Program Master (Waves B–E remain)
```

- Wave A is **GO** (primary accepted) — independent verify (`verifier-20260805T042330Z`)
  reproduced Layer 1 + Layer 2 + reload-persistence against live Beta with stable
  `qwen3.6:35b-a3b` config (colon intact, no mangling).
- Program Master GO remains **NO-GO** until Waves B–E complete.
- Graduation remains **CONDITIONAL** until Wave D.
- Wave B is **UNBLOCKED** — primary accepted Wave A GO (2026-08-05).
- **Independent verify (2026-08-05 04:30 UTC, did NOT implement Wave A, did
  NOT modify product source or operator config; run ID
  `verifier-20260805T042330Z`):** Preflight stable at 04:23:30 UTC
  (`qwen3.6:35b-a3b`, `modelAvailable: true`, Beta 200). Layer 1 PASS (18
  passed, exit 0, 191.15s); Layer 2 vs Beta PASS (100 UI iters, exit 0, 1.9m);
  reload vs Beta PASS (exit 0, 3.2s); post-Layer 2 config regression guard PASS.
  Checklist 11/11 PASS.

## Wave status

| Wave | Scope | Status |
| --- | --- | --- |
| A | Server event store + idempotent append + server-side assistant/tool append + client reconcile + Layer 1/2 cert | **GO (independent verify 2026-08-05 04:30 UTC)** — Preflight stable (`qwen3.6:35b-a3b`, colon intact); Layer 1 PASS (18 passed, exit 0); Layer 2 vs Beta PASS (100 UI iters, exit 0); reload vs Beta PASS; post-Layer 2 config regression guard PASS. Checklist 11/11. |
| B | Summarization / long-transcript compaction | **UNBLOCKED** — primary accepted Wave A GO; Wave B may start |
| C | Cross-device sync + realtime revision broadcast | Not started |
| D | Retention / export / import; graduation flip to GREEN | Not started |
| E | Audit + repair tooling | Not started |

---

## Wave A — Conversation Durability (Independent Verifier Result)

> **Verifier:** Independent verify agent (did NOT implement Wave A).
> **Run ID:** `verifier-20260804T202649Z`
> **Verdict:** **NO-GO** — Layer 2 not proven against the instructed live-Beta target.
> Full detail: `CODIRECTOR_MEMORY_INDEPENDENT_VERIFIER_REPORT.md`

### A.1 Results

| Layer | Target | Result | Exit | Duration |
| --- | --- | --- | --- | --- |
| Layer 1 (pytest) | studio-api temp DB | **PASS** (15 passed; 12×100 + 3 guards×100 = 1,500 assertions) | 0 | 194.95s (implementer re-run) / 167.50s (verifier) |
| Layer 2 (Playwright) | Live Beta (`ADEPT_BETA_TARGET=1`, real ollama) | **PASS** (100 UI iterations, 12 scenarios, 8–9 each) | 0 | 2.1m (implementer remediation) |
| Layer 2 (Playwright, diagnostic) | Isolated e2e harness (`STUDIO_E2E=1`, mock) | **PASS** (100 UI iterations, 12 scenarios) | 0 | 1.9m (verifier) |
| Reload-persistence regression | Live Beta (real ollama) | **PASS** (1 passed) | 0 | 2.9s (implementer re-run) / 3.8s (verifier) |

> **Layer 2 Beta remediation:** the original spec 404'd at `beforeAll` on Beta
> because it required `/api/e2e/codirector/scenario` (gated behind
> `STUDIO_E2E=1`, disabled on production Beta). The remediation guards the
> mock-scenario reset behind `!BETA_TARGET` so the same spec drives the real
> Co-Director + real ollama provider + public event-store append/reconcile
> path on Beta, preserving the mock fast path in the e2e harness. 100 UI
> iterations and all 12 scenarios unchanged; per-test timeout raised to
> absorb real-LLM latency. Layer 1 untouched. See section A.8.

### A.2 GO checklist (audited against code + evidence)

11/11 PASS after remediation (item 10 flipped from FAIL to PASS against Beta).

| # | Gate item | Status |
| --- | --- | --- |
| 1 | Migration complete (M028 registered) | PASS |
| 2 | `messages_json` migrated & verified | PASS |
| 3 | No unguarded transcript-replacement in creator use (server append-merge) | PASS (server-side) |
| 4 | Creator append idempotent | PASS |
| 5 | Assistant completion server-side | PASS |
| 6 | Tool calls/results appended | PASS |
| 7 | Concurrent tabs no truncation | PASS |
| 8 | Retry no duplicates | PASS |
| 9 | Layer 1 1200 PASS (independent re-run + implementer re-run) | PASS |
| 10 | Layer 2 100 UI PASS against Beta | **PASS** (implementer remediation; independent re-verify requested) |
| 11 | Do NOT self-cert | PASS (implementer returns READY FOR PRIMARY REVIEW) |

### A.3 Root cause of Layer 2 Beta failure

The Layer 2 spec (`tests/e2e/codirector/codirector-memory-race-certification.spec.ts`)
was authored for the isolated e2e harness: its `beforeAll` posts to
`/api/e2e/codirector/scenario` and its scenarios assume the mock Co-Director
provider. The production Beta runtime explicitly disables both
(`scripts/beta_runtime/supervisor.py:397` sets `STUDIO_E2E=0`;
`studio-api/app/main.py:489` mounts the e2e router only when `STUDIO_E2E` is
set; `studio-api/app/codirector/service.py:95-113` hides the mock provider
outside E2E). The canonical Beta runner (`scripts/run-playwright-beta.mjs`)
likewise does not set `STUDIO_E2E`. So the spec fails at `beforeAll` with a 404
on the e2e route, and even past that, `sendChatTurn` would use the real ollama
provider instead of the stubbed `[mock]` replies the spec assumes.

This is a **spec/certification-target mismatch**, not a durability defect.
The durability contract is independently proven:
- Layer 1 (1,200 + 300 guard assertions) PASS.
- Layer 2 (100 UI iterations) PASS in the isolated e2e harness.
- The reload-persistence regression spec PASS against live Beta with a real
  LLM turn + reload, confirming the event store is live on the Beta DB and
  append-merge does not truncate.
- All code-level checklist items verify against the source.

### A.4 Live-Beta migration probe

`POST /api/codirector/conversations/{id}/events` on the live Beta returned
`200` with `appendedCount:1, duplicateCount:0, revision:1`; `GET` returned the
folded conversation with `revision:1`. M028 is live on the production Beta DB.

Cleanup note: the probe left a disposable temp project `waveA-verify-probe`
and an orphan conversation header for project_id `38752` (PowerShell `$pid`
collision). Neither is the protected project. Operator should delete them.

### A.5 Remediation to flip Wave A to GO

The primary agent chooses one (the verifier does NOT pick):

1. Make the Layer 2 spec Beta-compatible (drop the e2e-scenario dependency;
   use the real provider or add a Beta-exposed auth-gated mock control), then
   re-run 100 iterations against Beta.
2. Formally designate the isolated e2e harness as the Layer 2 certification
   environment for Wave A, with rationale that Beta intentionally disables the
   mock provider and the reload-persistence regression covers the real-Beta
   path; update program status and re-issue the verdict.
3. Add a Beta-target Layer 2 variant asserting only the durability invariants
   (growth, no-loss, idempotency, cross-project isolation) on the real provider.

### A.6 Artifacts

`docs/release-gate/codirector/artifacts/persistent-memory/verifier-20260804T202649Z/`:
- `layer1_pytest.txt`
- `layer2_playwright.txt`
- `layer2_playwright_e2e_harness.txt`
- `layer2_reload_persistence_race.txt`
- `verifier-summary.md`

`docs/release-gate/codirector/artifacts/persistent-memory/remediate-20260805T033700Z/` (implementer remediation run):
- `layer1_pytest.txt` — Layer 1 re-run (15 passed, exit 0, 194.95s)
- `layer2_playwright_beta.txt` — Layer 2 against live Beta (1 passed, 100 UI iters, exit 0, 2.1m)
- `layer2_reload_persistence_race_beta.txt` — reload-persistence regression vs Beta (1 passed, exit 0, 2.9s)
- `remediation-summary.md` — short summary

### A.7 Implementer artifacts (prior)

`docs/release-gate/codirector/artifacts/persistent-memory/implementer-20260804T195204Z/`:
- `layer1_pytest.txt`, `layer1_pytest_final.txt`

### A.8 Layer 2 Beta remediation (implementer, 2026-08-05)

**Problem:** the original Layer 2 spec's `beforeAll` posted to
`/api/e2e/codirector/scenario`, a route mounted only when `STUDIO_E2E=1`
(`studio-api/app/main.py:489`). Production Beta hard-sets `STUDIO_E2E=0`
(`scripts/beta_runtime/supervisor.py:397`) and hides the mock provider
(`studio-api/app/codirector/service.py:95-113`), so the spec 404'd at
`beforeAll` against the instructed live-Beta target.

**Fix (single spec, environment-aware):**
- `tests/e2e/codirector/codirector-memory-race-certification.spec.ts` imports
  `BETA_TARGET` from `tests/e2e/helpers/app.ts` and guards the
  `setMockScenario` calls in `beforeAll`/`afterAll` behind `!BETA_TARGET`.
- On Beta the spec drives the real Co-Director + real ollama provider + the
  public event-store append/reconcile path (`/api/codirector/conversations/{id}/events`,
  `/api/codirector/conversations/{id}`), which are mounted unconditionally
  (`studio-api/app/main.py:284`). In the e2e harness the mock-provider fast
  path is unchanged.
- The 100 UI iteration requirement and all 12 race scenarios are unchanged.
- Per-test timeout raised (30 min on Beta, 10 min in e2e harness) to absorb
  real-LLM latency — the default 120s was too short for 100 real-LLM turns.
- Layer 1 (`studio-api/tests/test_codirector_persistent_memory_race.py`) was
  NOT modified.

**Evidence (live Beta, `ADEPT_BETA_TARGET=1`,
`PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760`,
`STUDIO_API_BASE=http://127.0.0.1:8758`):**

```
Layer 2:  1 passed (2.1m)  — 100 UI iterations, 12 scenarios (8–9 each), exit 0
Reload:  1 passed (2.9s)   — reload-persistence regression, exit 0
Layer 1: 15 passed in 194.95s — exit 0
```

Distribution (Beta Layer 2): send_before_load 9, rapid_sends 9,
reload_mid_response 9, delayed_append 9, duplicate_retry 8, concurrent_tabs 8,
project_switch_mid_send 8, refresh_after_send 8, api_restart_sim 8,
hundreds_of_messages 8, out_of_order_tool_assistant 8, summary_during_send 8.

**Cleanup:** disposable probe project `waveA-verify-probe` (left by the prior
verifier probe) was deleted; not the protected project
(`77a4b96c-8e3f-4501-897c-51bab99bedb7`, never touched). No `WaveA L2`/`CoDir
Reload Race` orphans remain after the runs.

**Verdict (implementer):** Layer 2 now PASSES against the instructed
live-Beta certification target. Wave A checklist is complete from the
implementer's perspective, but the implementer of this remediation does NOT
self-issue final Wave A GO — a fresh independent re-verify is requested.
**READY FOR PRIMARY REVIEW.**

---

## A.9 Independent re-verify after Layer 2 remediation (2026-08-05)

> **Verifier:** Fresh independent re-verify agent (did NOT implement the Layer 2
> remediation; did NOT modify product source). Run ID `verifier-20260804T204933Z`.
> **Verdict: NO-GO** — Layer 2 not reproducible against the instructed live-Beta target.
> Full detail: `CODIRECTOR_MEMORY_INDEPENDENT_VERIFIER_REPORT.md` and
> `docs/release-gate/codirector/artifacts/persistent-memory/verifier-20260804T204933Z/verifier-summary.md`.

### A.9.1 Results (own re-runs, `retries=0`)

| Layer | Target | Result | Exit | Duration |
| --- | --- | --- | --- | --- |
| Layer 1 (pytest) | studio-api temp DB (`STUDIO_E2E=1`, mock) | **PASS** (15 passed) | 0 | 187.28s |
| Layer 2 (Playwright) | Live Beta (`ADEPT_BETA_TARGET=1`, real ollama) | **FAIL** at iteration 1/100 (`send_before_load`) | 1 | 129.2s |
| Reload-persistence regression | Live Beta (real ollama) | **FAIL** (Expected >=5, Received 4) | 1 | 34.2s |

### A.9.2 Root cause (environment, not durability code)

The live Beta's Co-Director selected ollama model **`gemma4:31b-it-qat` is NOT
installed**. `GET /api/health` → `operator.provider.modelAvailable: false`;
`GET /api/codirector/providers/ollama/models` and ollama `/api/tags` show the
only installed model is `qwen3.6:35b-a3b`. The Co-Director UI header reads
`gemma4-31b-it-qat - Model Unavailable` and the chat surfaces "Request failed.
The selected model 'gemma4:31b-it-qat' is not installed." (confirmed in both
failure screenshots). The real chat returns a model-missing error instead of a
reply, so `sendChatTurn` times out at 120s (Layer 2) and the turn is not
persisted (reload). The durability contract itself holds: Layer 1 PASS and the
reload test confirmed the seeded 4-message history was not truncated.

### A.9.3 GO checklist (auditor view): 10/11 PASS — item 10 FAIL

Item 10 (Layer 2 100 UI PASS against Beta) FAIL in the verifier's own re-run.
Items 1–9 and 11 PASS (audited against source + Layer 1 re-run). Observation
(not a Wave A blocker): `append_tool_event` is defined but not yet invoked by
the live tool-execution path; live tool-event persistence is a Wave B+ concern.

### A.9.4 Remediation path (for primary/operator — verifier does NOT pick/mutate)

1. Make the Co-Director selected model available on Beta: `ollama pull
   gemma4:31b-it-qat`, or switch the selected model to the installed
   `qwen3.6:35b-a3b`.
2. Re-confirm `GET /api/health` → `operator.provider.modelAvailable: true`.
3. Re-run Layer 2 + reload-persistence on Beta with `ADEPT_BETA_TARGET=1`,
   `retries=0`.
4. Only if both pass may a fresh verifier issue Wave A GO.

### A.9.5 Artifacts

`docs/release-gate/codirector/artifacts/persistent-memory/verifier-20260804T204933Z/`:
- `layer1_pytest.txt` — Layer 1 (15 passed, exit 0, 187.28s)
- `layer2_playwright_beta.txt` — Layer 2 vs Beta (FAIL iter 1, exit 1, 129.2s)
- `layer2_reload_persistence_race_beta.txt` — reload vs Beta (FAIL, exit 1, 34.2s)
- `verifier-summary.md`

### A.9.6 Cleanup note

The verifier's failed runs left disposable temp projects on the Beta DB
(`WaveA L2 send_before_load 0 ...`, `CoDir Reload Race ...`). The verifier did
not auto-delete remote projects (out of scope). The operator should delete
them. The protected project `77a4b96c-8e3f-4501-897c-51bab99bedb7` was never
touched.

---

## Related documents

- `CODIRECTOR_MEMORY_INDEPENDENT_VERIFIER_REPORT.md` — full independent verifier report (Wave A)
- `CODIRECTOR_PERSISTENT_MEMORY_PROGRAM_STATUS.md` — program status table
- `CODIRECTOR_CONVERSATION_RACE_CERTIFICATION.md` — implementer Layer 1/2 certification report
- `CODIRECTOR_MEMORY_MIGRATION_REPORT.md` — M028 migration report
- `CODIRECTOR_PERSISTENT_MEMORY_ARCHITECTURE.md` — architecture stub

---

## A.10 Second independent re-verify (2026-08-05 04:09 UTC)

> **Verifier:** Fresh independent re-verify agent (did NOT implement Wave A; did
> NOT modify product source or operator config). Run ID
> `verifier-20260805T040100Z`.
> **Verdict: NO-GO** -- Layer 2 not reproducible against the instructed live-Beta
> target. Full detail: `CODIRECTOR_MEMORY_INDEPENDENT_VERIFIER_REPORT.md` and
> `docs/release-gate/codirector/artifacts/persistent-memory/verifier-20260805T040100Z/verifier-summary.md`.

### A.10.1 Preflight was healthy (per mandate), but transient

At 04:00:39 UTC, `GET /api/health` returned `operator.provider.modelAvailable:
true`, `selectedModel: qwen3.6:35b-a3b` (installed), Beta web HTTP 200 -- matching
the user's claim that the primary had switched Co-Director to the installed
model. Tests were started. The mandate's preflight was satisfied.

### A.10.2 Results (own re-runs, `retries=0`)

| Layer | Target | Result | Exit | Duration |
| --- | --- | --- | --- | --- |
| Layer 1 (pytest) | studio-api temp DB (`STUDIO_E2E=1`, mock) | **PASS** (15 passed) | 0 | 198.85s |
| Layer 2 (Playwright race cert) | Live Beta (`ADEPT_BETA_TARGET=1`, real ollama) | **FAIL** at iteration 1/100 (`send_before_load`) | 1 | 129.4s |
| Reload-persistence regression | Live Beta (real ollama) | **FAIL** (`ECONNREFUSED 127.0.0.1:8758` -- API down) | 1 | 2.2s |

### A.10.3 Root cause: persisted config reverted; Beta then collapsed

- The persisted file `data/codirector_config.json` (mtime 04:02:41 UTC)
  contains `gemma4:31b-it-qat` -- something wrote the uninstalled default back
  AFTER the healthy 04:00:39 UTC reading. The default comes from
  `settings.ollama_model` in `studio-api/app/config.py:36`.
- By the time Layer 2 ran, `/api/health` showed `selectedModel:
  gemma4:31b-it-qat`, `modelAvailable: false`, `status: "Model Missing"`. The
  UI showed "model not installed"; `sendChatTurn` timed out at 120s on iter 1
  (same mode as the prior verifier `verifier-20260804T204933Z`).
- The reload run failed with `ECONNREFUSED 127.0.0.1:8758`. A final sweep at
  04:08:31 UTC showed BOTH Studio API (8758) and Beta web (8760) DOWN (HTTP
  000); only Ollama (11434) was up with `qwen3.6:35b-a3b` installed.
- This is an environment/operator-config blocker, not a Wave A durability
  defect. Layer 1 (15 passed, 1,500 assertions, exit 0) independently PASSes.

### A.10.4 GO checklist (auditor view): 10/11 PASS -- item 10 FAIL

Items 1-9 and 11 PASS (audited against source + Layer 1 re-run). Item 10 (Layer
2 100 UI PASS against Beta) FAIL in the verifier's own re-run. Observation
(not a Wave A blocker): `append_tool_event` is defined but not yet invoked by
the live tool-execution path; live tool-event persistence is a Wave B+ concern.

### A.10.5 Remediation path (for primary/operator -- verifier does NOT pick/mutate)

1. Make the Co-Director selected model persistently available on Beta
   (persist `qwen3.6:35b-a3b` to `data/codirector_config.json` durably across
   restart, OR `ollama pull gemma4:31b-it-qat`, OR change the default
   `settings.ollama_model`).
2. Investigate and fix the config revert (identify the writer that re-applied
   `gemma4:31b-it-qat` at 04:02:41 UTC after the healthy 04:00:39 UTC reading).
3. Stabilize the Beta environment (both 8758 and 8760 went DOWN mid-session).
4. Re-confirm `GET /api/health` `operator.provider.modelAvailable: true` AND
   stays true across an API restart.
5. Re-run Layer 2 + reload-persistence on Beta with `ADEPT_BETA_TARGET=1`,
   `retries=0`.
6. Only if both pass may a fresh verifier issue Wave A GO.

### A.10.6 Artifacts

`docs/release-gate/codirector/artifacts/persistent-memory/verifier-20260805T040100Z/`:
- `env_health.txt` -- preflight + post-failure endpoint sweep + persisted config file
- `layer1_pytest.txt` -- Layer 1 (15 passed, exit 0, 198.85s)
- `layer2_playwright_beta.txt` -- Layer 2 vs Beta (FAIL iter 1, exit 1, 129.4s)
- `layer2_reload_persistence_race_beta.txt` -- reload vs Beta (FAIL ECONNREFUSED, exit 1)
- `verifier-summary.md`

### A.10.7 Cleanup note

The verifier's failed Layer 2 run left a disposable temp project
(`WaveA L2 send_before_load 0 ...`) on the Beta DB. The verifier did not
auto-delete remote projects (out of scope). The operator should delete it.
The protected project `77a4b96c-8e3f-4501-897c-51bab99bedb7` was never touched.

---

## A.11 Third independent verify — Intelligence Engine Wave A (2026-08-05 04:30 UTC)

> **Verifier:** Fresh independent verifier (did NOT implement Wave A; did NOT
> modify product source or operator config). Run ID `verifier-20260805T042330Z`.
> **Verdict: GO** — Wave A Intelligence Engine / Persistent Memory proven against
> live Beta. Full detail: `CODIRECTOR_MEMORY_INDEPENDENT_VERIFIER_REPORT.md` and
> `docs/release-gate/codirector/artifacts/persistent-memory/verifier-20260805T042330Z/verifier-summary.md`.

### A.11.1 Preflight (per mandate, BEFORE tests) — PASSED and stable

At 04:23:30 UTC:
- `GET /api/health` → `operator.provider.modelAvailable: true`,
  `selectedModel: qwen3.6:35b-a3b` (colon present), status `Ready`.
- `GET /api/codirector/config` → `qwen3.6:35b-a3b`.
- On-disk `data/codirector_config.json` → `qwen3.6:35b-a3b`.
- `GET http://127.0.0.1:11434/api/tags` → `qwen3.6:35b-a3b` installed.
- Beta web (8760) and API (8758) HTTP 200.

The prior re-verify blocker (config mangling / revert to uninstalled default) is
resolved. Preflight remained stable through certification.

### A.11.2 Results (own re-runs, `retries=0`)

| Layer | Target | Result | Exit | Duration |
| --- | --- | --- | --- | --- |
| Layer 1 (pytest) | studio-api temp DB (`STUDIO_E2E=1`, mock) | **PASS** (18 passed: 15 race + 3 ollama dock tag roundtrip) | 0 | 191.15s |
| Layer 2 (Playwright race cert) | Live Beta (`ADEPT_BETA_TARGET=1`, real ollama) | **PASS** (100 UI iterations, 12 scenarios) | 0 | 1.9m |
| Reload-persistence regression | Live Beta (real ollama) | **PASS** (1 passed) | 0 | 3.2s |

### A.11.3 Post-Layer 2 regression guard — PASS

At 04:30:00 UTC after Layer 2 + reload:
- `GET /api/health` → `selectedModel: qwen3.6:35b-a3b`, `modelAvailable: true`.
- `GET /api/codirector/config` and on-disk file → `qwen3.6:35b-a3b` (colon intact).

No config mangling during certification.

### A.11.4 GO checklist (auditor view): 11/11 PASS

Items 1–11 PASS. Item 10 (Layer 2 100 UI PASS against Beta) PASS in the
verifier's own re-run. Observation (not a Wave A blocker): `append_tool_event`
not yet invoked live — Wave B+ concern.

### A.11.5 Artifacts

`docs/release-gate/codirector/artifacts/persistent-memory/verifier-20260805T042330Z/`:
- `env_health.txt` — preflight + post-Layer 2 regression guard
- `layer1_pytest.txt` — Layer 1 (18 passed, exit 0, 191.15s)
- `layer2_playwright_beta.txt` — Layer 2 vs Beta (PASS, 100 iters, exit 0, 1.9m)
- `layer2_reload_persistence_race_beta.txt` — reload vs Beta (PASS, exit 0, 3.2s)
- `verifier-summary.md`

### A.11.6 Verdict

**GO.** Primary accepted Wave A GO (2026-08-05). Wave B is **UNBLOCKED**.
Program Master remains **NO-GO** until Waves B–E complete.
