# M30F Electron Preparation (documentation only)

| Field | Value |
|-------|-------|
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting SHA | `9899315ce4161524c4f3bb89b9a9cbc839bb117f` |
| Implementation SHA | `7fb6b0b4ff2501a9b7e10ded90038ca25a6d5fca` |
| Documentation SHA | `PLACEHOLDER_DOCS_SHA` |
| Provider Manifest SHA | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` |
| Date | 2026-07-27 |


M3.0F does **not** implement Electron.

Later Electron should supply:

- OS locale to `resolveInterfaceLocale`
- Native menu / installer / updater / file-dialog / notification language

Language preferences remain in the platform-neutral `adept_ui_language_prefs_v1` store.
