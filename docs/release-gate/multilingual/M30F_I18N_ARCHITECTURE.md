# M30F I18N Architecture

| Field | Value |
|-------|-------|
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting SHA | `9899315ce4161524c4f3bb89b9a9cbc839bb117f` |
| Implementation SHA | `PLACEHOLDER_IMPL_SHA` |
| Documentation SHA | `PLACEHOLDER_DOCS_SHA` |
| Provider Manifest SHA | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` |
| Date | 2026-07-27 |


## Stack

- Frontend: `i18next` + `react-i18next` under `studio-web/src/i18n/`
- Offline JSON namespaces for twelve locales
- Backend: `studio-api/app/codirector/language_intelligence/`
- Preferences: interface / conversation / project / prompt policy / export (decoupled)

## Verdict

**VERIFIED** for architecture foundation.
