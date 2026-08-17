# M30F I18N Architecture

> **HISTORICAL.** Current governing certification:
> [`docs/release-gate/m30f/M30F_MULTILINGUAL_END_TO_END_CERTIFICATION.md`](../m30f/M30F_MULTILINGUAL_END_TO_END_CERTIFICATION.md)

| Field | Value |
|-------|-------|
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting SHA | `9899315ce4161524c4f3bb89b9a9cbc839bb117f` |
| Implementation SHA | `7fb6b0b4ff2501a9b7e10ded90038ca25a6d5fca` |
| Documentation SHA | `e097cdefcf5d3a224807b8be869870a9cc07116a` |
| Provider Manifest SHA | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` |
| Date | 2026-07-27 |


## Stack

- Frontend: `i18next` + `react-i18next` under `studio-web/src/i18n/`
- Offline JSON namespaces for twelve locales
- Backend: `studio-api/app/codirector/language_intelligence/`
- Preferences: interface / conversation / project / prompt policy / export (decoupled)

## Verdict

**VERIFIED** for architecture foundation.
