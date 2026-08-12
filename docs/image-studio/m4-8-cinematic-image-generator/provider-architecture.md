# M4.8 Provider Architecture

## Truth sources (do not invent a third)

1. **Production Dock local catalog** — `production_control.model_registry.list_models("image")`
2. **Hosted discovery** — `hosted_providers.discovery.dock_api_models("image")`
3. **Family / dock map** — `production_control.runtime_map.IMAGE_FAMILY_BY_MODEL` + `apply_image_dock_preference`
4. **Workflow certification** — `config/image-workflows/certified-registry.json` via `recommend._family_status`

Unified surface: `studio-api/app/image_studio/providers.py` → `ImageProviderDescriptor`.

## Generation modes

| Mode | Behavior |
| --- | --- |
| `best_match` | Single recommended ready provider (recommend.py family → first ready descriptor) |
| `choose_model` | All ready image-capable providers |
| `all_models` | Full inventory including `not_installed` / `needs_auth` (honest labels) |

Hosted ready models set `requiresPaidConfirmation: true`.

## API

- `GET /api/image-studio/providers`
- `POST /api/image-studio/providers/for-mode`
- `GET /api/image-studio/families` and fixed `GET /api/image-product/families` (includes **qwen2512**)

## Install slots

HiDream / FLUX Schnell / FLUX Dev appear as descriptors or family catalog rows with honest non-Certified status until live install+generate cert.
