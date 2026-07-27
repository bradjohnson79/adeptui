# M30E TEST REPORT

| Field | Value |
|-------|-------|
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting SHA | `5af34eff0a5207febf05ef6cc4a3e4f7d572eb15` |
| Implementation SHA | `bdc43f8e70cc69d767089f9ed2b0358c7fb82f42` |
| Documentation SHA | `PLACEHOLDER_DOCS_SHA` |
| Provider Manifest SHA | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` |
| Date | 2026-07-27 |

## Commands

```bash
cd studio-api
python -m pytest -q tests/test_m30e_model_intelligence.py
python -m pytest -q
```

## Totals (stamp after final suite)

Backend full suite: **650 passed / 0 failed / 6 skipped**. MIL suite: **19 passed**.
