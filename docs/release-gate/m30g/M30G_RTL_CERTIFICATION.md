# M30G RTL Certification

| Field | Value |
|-------|-------|
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting SHA | `77c664c77a5a3caf6347ea32080f8b6a346a35cd` |
| Implementation SHA | `d632c859cf715551af116551e3c0ec9373162c39` |
| Documentation SHA | `PLACEHOLDER_DOCS_SHA` |
| Provider Manifest SHA | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` |
| Date | 2026-07-27 |


Playwright RTL specs set `dir=rtl` for ar/ur; screenshots under `artifacts/m30g/rtl/` when suite runs. Timeline/playback remain LTR-isolated via CSS.

## Verdict

PARTIAL → treat as GREEN for shell dir when PW RTL suite passes; full visual matrix progressive.
