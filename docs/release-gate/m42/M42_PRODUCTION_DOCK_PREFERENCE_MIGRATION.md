# Production Dock — Preference Migration Report

**Branch:** `phase2/m42-production-dock`  
**Stamp:** `data/production_control/migration_stamp.json`  
**Runner:** `POST /api/production-control/migrate` / `scripts/m42_production_dock_certify.py`

## Mapping

| Old setting | New preference field | Result |
| --- | --- | --- |
| `codirector_config.json` → `selectedModel` / `primaryModel` | `user.llm.activeModelId` (mapped to registry id when possible) | Migrated on first launch |
| `hosted_providers/preferences.json` → `preferredProvider` | `user.defaultHostedProviderId` | Migrated |
| Legacy theme preference (if present) | `user.theme` | Migrated or default `aurora-night` |
| Audio Studio per-request preferred provider | Project/user `audio` routing | Adopted via dock resolve; not wiped |
| Project video/image defaults | `project.activeVideoModelId` / `activeImageModelId` | Available for project overrides |

## Precedence after migration

```text
Project override → user default → system default
```

## Idempotency

Second `migrate` call returns `alreadyMigrated: true` and does not reset working settings.

## Runtime consumption (post-migration)

| Modality | Dock field | Runtime mapping | Consumer |
| --- | --- | --- | --- |
| Audio | `audio.activeModelId` / project override | ACE-Step / MMAudio readiness | `audio_studio/service._prepare_generation` |
| Image | `image.activeModelId` / project override | e.g. `qwen-image-2512-local` → `qwen2512` | `image_product/service.generate_images` |
| Video | `video.activeModelId` / project override | e.g. `ltx-local` → `ltx` | `render_project`, `enqueue_intent` |
| LLM | `llm.activeModelId` | e.g. `ollama-gemma4-31b` → `gemma4:31b-it-qat` | Co-Director `config_store` |

## Certification

`artifacts/m42/production-dock/preference_migration_results.json` — `ok: true`  
`artifacts/m42/production-dock/resolver_consumption_results.json` — audio/image/video consumed
