# M30I Closure Register

| Field | Value |
|-------|-------|
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting SHA | `190b3e1a97d6e4ee082d30a7098f0e309711c59d` |
| Provider Manifest SHA | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` **LOCKED** |
| Product | Adept UI Studio |
| Date | 2026-07-27 |

## Verdict coupling

- Live fal GREEN + S1–S9 regression → M3.0h may YES (a11y not required for h)
- A11y incomplete / SR NOT RUN → M3.0g NO
- Manual Beta Entry YES only if g YES and h YES (+ Director/audio/360 gates)

## Inherited blockers

| ID | Source | Original result | Closure action | Blocks g YES | Blocks h YES | Blocks Beta |
|----|--------|-----------------|----------------|--------------|--------------|-------------|
| MI-LIVE-01 | M3.0g/h | BLOCKED / INCONCLUSIVE | One-shot Studio-queue Seedance music-off | Yes | Yes | Yes |
| A11Y-KB-01..20 | M3.0g | PARTIAL | Playwright keyboard journeys | Yes | No | Yes |
| A11Y-SR-01..12 | M3.0g | NOT GREEN | NVDA+Chromium manual | Yes | No | Yes |
| RTL-A11Y-01..12 | M3.0g | PARTIAL | ar/ur a11y Playwright | Yes | No | Yes |
| AXE | M3.0g | 0 critical (prior) | Rerun 0 critical/serious | Yes | No | Yes |
| REG-01..10 | both | — | Focused regression | Yes | Yes | Yes |
| REG-11..16 | addenda | — | Director + audio PW | Yes* | No | Yes |
| REG-17..23 | addenda | — | 360 env + visible character + unified preflight | Yes* | No | Yes |
| BETA-GATE-01 | M3.0i | — | All entry requirements | — | — | Yes |

\* Manual Beta Entry extras (g YES still requires a11y+live; these are additional Beta gates).

## Final status columns

Updated as phases complete in `artifacts/m30i/closure-register/status.json` and PM reports.
