# M42 Wave 3 — Character & Environment Builders

## Character Builder

Generate actions: front / side / rear / expression / costume via `builtin-character-sheet` + ReferenceAsset bridge. Attach-only flows preserved.

## Environment Builder

Image-runtime generate panel (concept/room/landscape/city/spacecraft/fantasy/background) alongside M2.13 camera-spin. Preset `builtin-environment-sheet`; ReferenceAsset type `environment`.

## ReferenceAsset store

Persisted under `data/image_product/{projectId}/references.json` with CRUD + UI role → type normalization.

Artifacts: `character_builder_results.json`, `environment_builder_results.json`, `reference_results.json`.
