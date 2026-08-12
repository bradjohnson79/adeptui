# M5.0 — Playwright Smoke Report

| Field | Value |
| --- | --- |
| Milestone | `M5.0 Final E2E` |
| Branch | `feature/ai-guided-setup` |
| SHA | `fa09c99d6395c29461cdec4555055faad116c435` |
| Beta UI | `http://127.0.0.1:8760/` |
| Beta API | `http://127.0.0.1:8758/` |
| Smoke timestamp (UTC) | `2026-08-02T16:40:40Z` |

## Scope

This report records two focused smoke slices against the same branch:

1. an isolated Playwright-managed stack (`5173` + `8742`) to confirm the specs themselves still run
2. the already-running Beta (`8760` + `8758`) to determine release-gate truth

The release-gate verdict must follow the live Beta run, not the isolated harness.

## Commands

### Isolated stack

```text
npx playwright test tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts tests/e2e/setup/setup-install-progress.spec.ts tests/e2e/codirector/codirector-status-cross-check.spec.ts
```

### Live Beta

```text
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760
npx playwright test tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts tests/e2e/setup/setup-install-progress.spec.ts tests/e2e/codirector/codirector-status-cross-check.spec.ts
```

## Results Summary

| Target | Result | Runtime | Interpretation |
| --- | --- | --- | --- |
| Isolated Playwright-managed stack | `12 passed / 0 failed / 0 flaky` | `4.0m` | The specs themselves are healthy against the managed local harness. |
| Live Beta | `7 passed / 4 failed / 1 flaky` | `11.5m` | The actual Beta is not release-ready for M5 final certification. |

## Live Beta Failures

| Spec | Result | Beta evidence |
| --- | --- | --- |
| `tests/e2e/codirector/codirector-status-cross-check.spec.ts` | `FAIL` | The creator-facing Co-Director status panel/history visibility smoke failed twice on Beta. |
| `tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts` | `FAIL` | Beta failed the lifecycle panel render, focused deep-link certify flow, and focused-component refresh flow. |
| `tests/e2e/setup/setup-install-progress.spec.ts` | `FLAKY` | `restores install progress after reload` failed once, then passed on retry. |

## Live Beta Passes

| Spec slice | Result | Beta evidence |
| --- | --- | --- |
| AI-Guided root redirect | `PASS` | `root AI-guided redirect preserves source and component` passed on Beta. |
| Setup install-progress critical flows | `PASS` | Remaining install-progress critical slices passed, including blocked-capability entry, stepper behavior, cancel, restart guidance, and add-source validation. |

## Key Failure Details

### Co-Director status

- Beta smoke for `codirector-status-cross-check` failed on both initial run and retry.
- This aligns with the live API status result in this pass: `POST /api/codirector/status/check` produced a persisted run with `statusIndicator=Degraded`, `score=82`, `band=Fair`.

### AI-Guided lifecycle render and deep links

- Beta could not reliably render the expected setup shell:
  - `.setup-wizard-page` not visible in the failed lifecycle entry case
  - `AI-Guided Setup` heading not visible for the focused Hunyuan deep-link case
  - `Opened for FLUX.1 Dev.` text not visible for the focused refresh case
- These are creator-facing entry failures, not minor assertion noise.

### Reload stability

- `restores install progress after reload` was not stable on the first Beta attempt.
- A retry converted the case to `flaky`, which is still below honest M5 final release quality.

## Artifact Pointers

- Beta smoke output: `artifacts/functional-audit/`
- Failed screenshot/trace examples recorded under:
  - `artifacts/functional-audit/test-output/setup-ai-guided-setup-*`
  - `artifacts/functional-audit/test-output/setup-setup-install-progre-*`

## Smoke Verdict

**NO-GO**

The isolated harness still proves the tests are valid, but the live Beta smoke slice remains below release-gate quality. For M5 final certification, the release target must be scored from the live Beta result: `7 passed / 4 failed / 1 flaky`.
