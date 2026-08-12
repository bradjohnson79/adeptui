# Local / Hosted / Spending — Unified Report



## Program status



```text

GO — INDEPENDENT VERIFIER PASS (2026-08-05T04:10:31Z)

```



| Family | Verdict |

|---|---|

| MODEL-1..3 (Local folder discovery) | **GO** |

| API-1..3 (Hosted providers + OpenAI-compatible) | **GO** |

| COST-1..5 (Usage ledger, dock spend, budgets) | **GO** |



Independent verifier report: [`LOCAL_HOSTED_SPENDING_INDEPENDENT_VERIFIER_REPORT.md`](LOCAL_HOSTED_SPENDING_INDEPENDENT_VERIFIER_REPORT.md)  

Artifacts: [`artifacts/verifier-20260805-041031/verifier-summary.md`](artifacts/verifier-20260805-041031/verifier-summary.md)



## Implementer summary



| Area | Specs / tests | Implementer | Independent verifier |

|---|---|---|---|

| Local discovery | `local-model-folder-discovery.spec.ts` + unit | PASS | **GO** |

| Hosted providers | `hosted-api-provider-setup.spec.ts` | PASS | **GO** |

| Spending | `api-spending-dock.spec.ts` + unit | PASS | **GO** |



## Beta (verified 200)



- UI: http://127.0.0.1:8760/

- API: http://127.0.0.1:8758/

- Endpoints: `/api/model-storage`, `/api/provider-usage/dock`



## Test commands (verifier run)



```powershell

cd studio-api

python -m pytest tests/test_model_storage.py tests/test_provider_usage.py -q

# 8 passed



$env:ADEPT_BETA_TARGET='1'

$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:8760'

$env:STUDIO_API_BASE_URL='http://127.0.0.1:8758'

npx playwright test tests/e2e/setup/local-model-folder-discovery.spec.ts `

  tests/e2e/setup/hosted-api-provider-setup.spec.ts `

  tests/e2e/setup/api-spending-dock.spec.ts --retries=0 --project=chromium

# 3 passed

```



## Key files



- `studio-api/app/model_storage/`

- `studio-api/app/provider_usage/`

- `studio-api/app/hosted_providers/custom_llm.py`

- `studio-web/src/components/ModelStoragePanel.tsx`

- `studio-web/src/components/production-dock/DockSpendPanel.tsx`



## Limitations (disclosed)



- Unit pytest requires `cd studio-api` (repo-root import fails).

- Playwright dock UI assertions conditional on production-dock settings control presence.

- Global usage ledger retains test records after disposable project cleanup.



**READY FOR PRIMARY REVIEW**

