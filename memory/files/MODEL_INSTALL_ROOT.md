# Model / runtime install root (binding)

**Law (2026-08-14):** New Adept model and runtime installs land under `D:\01_Models`.
Do not invent a second settings system. Do not move `STUDIO_DATA_DIR` / `data_dir`
just to relocate models. Do not set `STUDIO_COMFY_MODELS_DIR=D:\01_Models` globally
(that is the Comfy-Desktop shared models folder; Beta env forbids it).

The folder is `D:\01_Models` — no space. Brad's `D:/ 01_Models` note was a typo.

## Existing setting (already persisted)

Source Manager / Model Storage already owns this:

- File: `data/model_storage.json`
- Fields: `preferredRoot`, `roots.default`, `roots.video` (and other category roots)
- Code default: `app.model_storage.store.DEFAULT_PREFERRED_ROOT = D:\01_Models`
- Helpers: `preferred_root()`, `category_root(category)`, `get_roots()`, `set_root()`

Current live values (do not reset unless Brad asks):

- `preferredRoot` = `D:\01_Models`
- `roots.default` / `roots.video` / `roots.image` / `roots.llm` / … = `D:\01_Models`
- `roots.temp_cache` stays under `data_dir` (`data/model_cache`)

Krea 2 already follows this law: `D:\01_Models\krea2` (`krea2_model_root` /
`krea2_image_root()`). MiniMax H3 uses `STUDIO_MINIMAX_H3_MODEL_ROOT=D:\01_Models`
for its own Route A tree (`D:\01_Models\Video\MiniMax-H3\...`), not as the
avatar-runtime destination.

## How destinationRoot is chosen

1. Wizard / Source Manager / Avatar install panel open Preflight
   (`setupSuggestedPath` → `suggested_install_path`).
2. Creator can keep that path or use **Choose Install Location** (`browse_path`).
3. Confirm writes `POST /api/setup/install-jobs` with `destinationRoot`.
4. Install-jobs use `destinationRoot` / `installPath` when present; otherwise
   `suggested_install_path(componentId)`.

Avatar runtimes (`infinitetalk-local`, `musetalk-1-5-local`,
`longcat-video-avatar-1-5-local`, `echomimic-v2-local`):

- Suggested path is `category_root("video") / <runtime_slug>`
- That is `D:\01_Models\<slug>` going forward
- Examples: `D:\01_Models\infinitetalk`, `D:\01_Models\musetalk-1-5`,
  `D:\01_Models\longcat-video-avatar-1-5`
- `destinationRoot` is the **per-runtime folder**, not `D:\01_Models` itself.
  Passing the parent dumps `source/` and `venv/` into the models root
  (that already happened once — `D:\01_Models\source` and `D:\01_Models\venv`).

Legacy default was `{data_dir}/runtimes/avatar/<slug>`. Partial/failed trees
may still exist there. New installs must not reuse that C: path.

Comfy-linked checkpoints (LTX / WAN / path_link) still suggest
`settings.comfy_models_dir` via `default_models_root()`. That is intentional
and separate from this law.

## After reboot (LongPathsEnabled)

Do not start InfiniteTalk / MuseTalk / LongCat until the PC has rebooted with
`LongPathsEnabled=1`. Then POST the bodies in the next section. Do not commit,
push, or deploy this configuration work as part of the path-root change.

## Retry API bodies

`POST /api/setup/install-jobs` (API origin is the Beta API, typically
`http://127.0.0.1:8758`). `confirm` and `confirmDownloadModels` are required
or the job stays `awaiting_confirmation`.

### infinitetalk-local

```json
{
  "componentId": "infinitetalk-local",
  "confirm": true,
  "confirmDownloadModels": true,
  "destinationRoot": "D:\\01_Models\\infinitetalk"
}
```

### musetalk-1-5-local

```json
{
  "componentId": "musetalk-1-5-local",
  "confirm": true,
  "confirmDownloadModels": true,
  "destinationRoot": "D:\\01_Models\\musetalk-1-5"
}
```

### longcat-video-avatar-1-5-local

```json
{
  "componentId": "longcat-video-avatar-1-5-local",
  "confirm": true,
  "confirmDownloadModels": true,
  "destinationRoot": "D:\\01_Models\\longcat-video-avatar-1-5"
}
```

Aliases accepted by the router: `installPath` / `install_path` for the same
folder; `confirm_download_models` for the confirm flag.
