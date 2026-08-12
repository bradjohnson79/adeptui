# M3.0h Local-First Filmmaker Certification

**Full summary report:** [`docs/M3.0H_LOCAL_FIRST_CERTIFICATION_SUMMARY.md`](../../M3.0H_LOCAL_FIRST_CERTIFICATION_SUMMARY.md)

Additive gate under `docs/release-gate/m30h-local-first/`. Does not overwrite prior M3.0h / M3.0i reports.

## Policy

1. Preferred ready local ImageGen → ComfyUI LTX 2.3 I2V  
2. Compatible installed local alternates before fal  
3. fal.ai only with explicit paid approval — never silent  
4. No new paid fal submission for this certification  

## Fal submission counters (must not contradict)

| Counter | Value |
|---------|-------|
| `historicalFalSubmissionCount` | 1 (M3.0i PROVIDER_FAILED) |
| `m30hLocalCertificationFalSubmissionCount` | 0 |
| `currentJobFalSubmissionCount` | 0 |

## Evidence roots

- `artifacts/m30h-local-first/preflight/`
- `artifacts/m30h-local-first/real-local-execution/` (`REAL_LOCAL_EXECUTION`)
- Playwright: `tests/e2e/m30h-local-first/` (`DETERMINISTIC_BROWSER_REGRESSION`)

## Verdict independence

- **M3.0h** = local filmmaker path certification (export must succeed for GREEN)
- **Manual Beta Entry** = M3.0h YES **and** a11y GREEN (NVDA manual separate from launch)
- fal backup remains independently `PROVIDER_FAILED` unless separately repaired
