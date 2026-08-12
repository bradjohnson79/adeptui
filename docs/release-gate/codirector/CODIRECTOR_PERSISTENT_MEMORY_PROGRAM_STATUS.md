# Co-Director Persistent Memory — Program Status

> **Authoritative program status for the Co-Director Persistent Memory initiative.**

## Current status

```text
GO — Wave A Intelligence Engine / Persistent Memory (PRIMARY ACCEPTED 2026-08-05)
GO — CO-DIRECTOR CONVERSATION MEMORY DURABLE
GO — CO-DIRECTOR COMPLETE PROJECT MEMORY READY
GO — CO-DIRECTOR REMEMBERS, LEARNS, AND EVOLVES ACROSS TASKS
GO — CO-DIRECTOR PERSISTENT MEMORY AND EVOLUTION READY
```

> Primary accepted memory/evolution after independent MEMORY — PASS (`verifier-20260805T053600Z`)
> and Layer 3 / Waves B–E evidence. Final Systems All-GO + Graduation are separately GO;
> see `docs/release-gate/final-systems/ADEPT_UI_FINAL_SYSTEMS_AND_RESILIENCE_UNIFIED.md`.


> **Primary acceptance (2026-08-05):** Reviewed [Wave A verifier](226a80ce-8868-455d-9ab4-2cc66e140986)
> run `verifier-20260805T042330Z`. Spot-checked artifacts on disk + live
> `selectedModel: qwen3.6:35b-a3b` (colon intact, `modelAvailable: true`).
> **Wave A GO accepted.** Wave B is **UNBLOCKED**.
>
> Updated 2026-08-05 04:30 UTC by the independent verify agent
> (`verifier-20260805T042330Z`; did NOT implement Wave A; did NOT modify product
> source or operator config).
>
> Preflight at 04:23:30 UTC was HEALTHY and **stable**:
> - `GET /api/health` → `operator.provider.modelAvailable: true`,
>   `selectedModel: qwen3.6:35b-a3b` (colon present)
> - `GET /api/codirector/config` → `qwen3.6:35b-a3b`
> - On-disk `data/codirector_config.json` → `qwen3.6:35b-a3b`
> - Ollama `/api/tags` → `qwen3.6:35b-a3b` installed
> - Beta web (8760) and API (8758) HTTP 200
>
> Results (own re-runs, `retries=0`):
> - Layer 1 (pytest): **18 passed** (15 race + 3 ollama dock tag roundtrip), exit 0, 191.15s — PASS.
> - Layer 2 (race cert) vs Beta: **PASS** (100 UI iterations, 12 scenarios, exit 0, 1.9m).
> - Reload-persistence vs Beta: **PASS** (1 passed, exit 0, 3.2s).
> - Post-Layer 2 regression guard: `selectedModel` still `qwen3.6:35b-a3b` — no mangling.
>
> Wave A checklist: **11/11 PASS**. Wave B is **UNBLOCKED** pending primary review.
> Program Master remains **NO-GO** until Waves B–E complete.
>
> See `CODIRECTOR_MEMORY_UNIFIED_REPORT.md` section A.11 and
> `CODIRECTOR_MEMORY_INDEPENDENT_VERIFIER_REPORT.md`.

Graduation is separately **GO** (independent corroboration 2026-08-05). See Final Systems unified report.

## Wave status

| Wave | Scope | Status |
| --- | --- | --- |
| A | Server event store + idempotent append + server-side assistant/tool append + client reconcile + Layer 1/2 cert | **GO (independent verify 2026-08-05 04:30 UTC)** |
| B | Summarization / long-transcript compaction | **GO** — compact API + fold skip + UI Summarize |
| C | Cross-device sync + realtime revision broadcast | **GO** — revision endpoint + SSE + client poll |
| D | Retention / export / import | **GO** — memory export/import + intelligence snapshot |
| E | Audit + repair tooling | **GO** — audit + rebuild-fold + Check memory health UI |

## Why GO (independent verify 2026-08-05 04:30 UTC)

1. **Preflight passed and remained stable.** `modelAvailable: true`,
   `selectedModel: qwen3.6:35b-a3b` on health, config API, on-disk file, and
   Ollama tags. Prior re-verify config-mangling blocker is resolved.
2. **Layer 1 independently PASS** (18 passed, exit 0, 191.15s) — 1,800 race
   assertions plus 3 ollama dock tag roundtrip tests.
3. **Layer 2 against the instructed live-Beta target PASS** (`ADEPT_BETA_TARGET=1`,
   `retries=0`): 100 UI iterations, all 12 scenarios, exit 0, 1.9m.
4. **Reload-persistence regression PASS** against live Beta (exit 0, 3.2s).
5. **Post-Layer 2 regression guard PASS** — config tag unchanged after certification.
6. **Checklist 11/11 PASS.** Binary certification: Wave A **GO**.
7. **Waves B–E + Layer 3** independently corroborated MEMORY — PASS; primary issued
   the four memory/evolution GO strings. Final Systems All-GO + Release Freeze
   are recorded under `docs/release-gate/final-systems/`.

## Handoff

- Implementer handoff: this directory + the architecture stub.
- **Independent verify result (2026-08-05 04:30 UTC): GO** — Wave A proven.
  See `CODIRECTOR_MEMORY_INDEPENDENT_VERIFIER_REPORT.md` and artifact
  `verifier-20260805T042330Z/verifier-summary.md`.
- Wave B is **UNBLOCKED** (primary accepted Wave A GO).
- **Prior independent re-verify (2026-08-05 04:09 UTC): NO-GO** — config reverted
  mid-session; see `verifier-20260805T040100Z/verifier-summary.md`.
