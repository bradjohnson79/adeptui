# M30F Phase 0 Baseline

| Field | Value |
|-------|-------|
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting SHA (M3.0F entry) | `9899315ce4161524c4f3bb89b9a9cbc839bb117f` |
| Prior tip before M3.0e report commit | `0dbbee7d906f95f021d38e7acdb50039c1bfd62a` |
| Provider Manifest SHA | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` **LOCKED** |
| Date | 2026-07-27 |

## Suites before localization behavior change

| Suite | Totals | Verdict |
|-------|--------|---------|
| Backend pytest | **650 passed / 0 failed / 6 skipped** | PASS |
| Frontend build | **exit 0** | PASS |
| Playwright | recorded in Phase 8 / runtime evidence after baseline run completes | — |

## Constraints preserved

- No Provider Manifest changes
- No new generation providers
- Do not weaken existing tests
- Do not claim MIL multilingual capability without pack `languageSupport` evidence
