# Playwright Full Green Report

Date: 2026-07-27

## Captured command

```text
npx playwright test
```

Captured result:

```text
6 skipped
111 passed (4.0m)
exit_code: 0
elapsed_ms: 239775
```

Totals: **117 tests, 111 passed, 0 failed, 6 skipped**. Result: **PASS**.

## Skip classifications

The six skips are classified from `docs/m3.0-completion/PLAYWRIGHT_CLOSURE.md`:

1. `capability-intelligence-m28.spec.ts:53` — flags-off inverse case; default E2E flags are on. **Inverse / environment**
2. `production-executive-m27.spec.ts:222` — flag-off inverse case; Production Executive is on by default. **Inverse / environment**
3. `production-executive-m27.spec.ts:486` — restart recovery is covered by `test_job_queue_recovery.py`. **Delegated**
4. `m30-completion-local-live.spec.ts:24` — local ImageGen readiness gate; `ADEPT_M30A_LOCAL_LIVE` unset. **Live gate**
5. `m30-completion-local-live.spec.ts:42` — real local artifact gate; same live gate unset. **Live gate**
6. `m30a-fal-ai-provider.spec.ts:84` — real FAL key gate; `ADEPT_M30A_FAL_LIVE` / key unset. **Live gate**

These are intentional skips, not silent passes. The live-gated tests remain pending because no real provider credentials or local-live enablement were supplied.
