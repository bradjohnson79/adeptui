# Local / Hosted / Spending — Independent Verifier Report

**Role:** Fresh independent verifier (not implementer)  
**UTC:** 2026-08-05T04:10:31Z  
**Artifact folder:** [`artifacts/verifier-20260805-041031/verifier-summary.md`](artifacts/verifier-20260805-041031/verifier-summary.md)

## Executive summary

Independent verification against live Beta completed. All three gate families pass with evidence from Beta health checks, 8/8 unit tests, 3/3 Playwright scenarios (retries=0), and targeted source review for secrets leakage and silent fallback patterns. Protected project `77a4b96c-8e3f-4501-897c-51bab99bedb7` was not mutated.

## Verdicts

| Family | Gates | Verdict |
|---|---|---|
| **Local Model Folder Discovery** | MODEL-1..3 | **GO** |
| **Hosted API Providers** | API-1..3 | **GO** |
| **Dock Usage Spending** | COST-1..5 | **GO** |

## Beta verification

| URL | Result |
|---|---|
| http://127.0.0.1:8760/ | 200 |
| http://127.0.0.1:8760/__beta_web_health | 200 |
| http://127.0.0.1:8758/api/health | 200 |
| http://127.0.0.1:8758/api/model-storage | 200 |
| http://127.0.0.1:8758/api/provider-usage/dock | 200 |

## Test execution

### Unit (studio-api)

```text
cd studio-api
python -m pytest tests/test_model_storage.py tests/test_provider_usage.py -q
→ 8 passed in 0.22s
```

Coverage: path-only register, Ollama manifest classification, drive unavailable honesty, estimated vs confirmed ledger, failure unknown billing, budget confirmation gate, resolver budgetPreference.

### Playwright (live Beta, retries=0)

```text
ADEPT_BETA_TARGET=1
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760
STUDIO_API_BASE_URL=http://127.0.0.1:8758
npx playwright test tests/e2e/setup/local-model-folder-discovery.spec.ts
  tests/e2e/setup/hosted-api-provider-setup.spec.ts
  tests/e2e/setup/api-spending-dock.spec.ts --retries=0 --project=chromium
→ 3 passed (5.3s)
```

## Gate detail

### MODEL-1..3 — GO

1. **Path-only registration:** `register_folder` default `import_into_library=False`; copy gated behind explicit import with `importDisclosed`.
2. **Honest classifiers:** Ollama resolves manifest tree, not blob digests; GGUF and HF/safetensors paths covered; validation statuses match reality.
3. **Drive resilience:** Missing paths return `Drive Unavailable`, registration retained in store, `silentSwitchForbidden` and `autoRedownloadForbidden` set; UI retry re-registers live path.

### API-1..3 — GO

1. **Extensible providers:** fal, kie, wavespeed in registry; OpenAI-compatible custom endpoints with encrypted secrets store.
2. **Honest capabilities:** LLM capability flagged only after successful models probe; no image/video/audio inference from chat endpoint alone.
3. **Routing integrity:** budgetPreference `low_cost` reverses resolver order; pinned provider failure does not silently switch; resolve payload includes `silentSwitchForbidden`.

### COST-1..5 — GO

1. **Ledger:** estimated and confirmed costs tracked separately with versioned rate card reference.
2. **Estimates:** disclaimers on all summaries; static rate cards labeled `static_estimate`.
3. **Dock + budgets:** preflight returns warn/confirm/block actions; dock exposes spend breakdown and budget flags.
4. **Failures:** failed records retain `billingStatus: unknown`, not zero-cost assumption.
5. **Co-Director:** `/codirector-summary` sets `secretsIncluded: false`; guidance forbids silent paid substitution.

## Source spot-check highlights

| Area | Finding |
|---|---|
| `studio-api/app/model_storage/store.py` | Copy only on explicit import |
| `studio-api/app/provider_usage/ledger.py` | Metadata strips key/secret fields |
| `studio-api/app/hosted_providers/custom_llm.py` | Secrets via `secrets_store`, not JSON config |
| `studio-web/src/components/HostedProvidersSetupPanel.tsx` | Password inputs; no localStorage for keys |
| `studio-api/app/hosted_providers/resolver.py` | No silent switch when pinned unavailable |

## Honest limitations

- Pytest from repo root without `cd studio-api` fails collection (`ModuleNotFoundError: app`).
- Playwright dock UI checks are best-effort when production-dock settings control absent; API paths fully validated.
- Global usage ledger accumulates test records (projects deleted; ledger not rolled back).

## Final line

**READY FOR PRIMARY REVIEW**
