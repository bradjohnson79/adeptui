# Database and Core Object Audit

## Executive conclusion

SQLite contains solid Project, Scene, Asset, and Job foundations, but relationships are mostly soft IDs and JSON. Generation and Memory have no durable tables. Timeline ownership overlaps across `scenes.director_json`, `director_sequences`, and `editor_projects`.

## Schema initialization

- `Base.metadata.create_all()` plus inline `ALTER TABLE ADD COLUMN`
- satellite modules expose `ensure_*_tables()`
- no schema-version table, migration runner, rollback journal, or guaranteed FK enforcement
- several startup failures are swallowed

## Table classification

| Table/store | Class | Disposition |
|---|---|---|
| `projects` | B | Keep; type core fields, reduce blob authority |
| `scenes` | B | Make central hub; add typed nullable links |
| `assets` | B | Canonicalize all media outputs |
| `jobs` | A/B | Keep; type kinds and link Generation |
| `profile_items` | B/C | Keep rows; add project/scene attachment model |
| `script_docs` | A | Keep |
| `script_segments` | B | Use `scene_id`; add revision lineage |
| `storyboard_panels` | B | Add durable revision/outdated semantics |
| `scene_master_sheets` | C | Dual-read into Scene Sheet |
| `spatial_scenes` | C | Preserve as archived/future metadata |
| `projects.spatial_map_json` | E | Legacy compatibility only |
| `avatar_sessions` | C | Compatibility package for Generate/Avatar |
| `director_sequences` | B/C | Preserve approval/version package |
| `editor_projects` | B/C | Compatibility wrapper for normalized Timeline/Clip |
| `asset_versions` | B | Preserve |
| `asset_edges` | C/D | Mixed entity IDs; migrate to typed lineage |
| `projects.learning_json` | C | Dual-read into MemoryItem |
| `generations` | F | Missing |
| `timelines` / `editor_clips` | F | Missing |
| `memory_items` | F | Missing |

## Soft-reference risks

- Scene frame/audio asset IDs have no FK.
- Job `scene_id`, Asset `parent_asset_id`, panel asset ID, sequence scene/asset IDs are soft.
- Editor clip references live inside JSON.
- `asset_edges` may connect assets, scenes, panels, segments, and spatial IDs despite asset-oriented APIs.
- Profile IDs are embedded in Master Sheet, Spatial, and Avatar JSON.

## Deletion behavior

Project deletion cascades only core ORM children. Script/storyboard, spatial, master sheets, avatar sessions, director sequences, editor projects, and graph rows can orphan. Scene deletion similarly leaves satellites and Editor/Story references. `timeline/apply replace_existing` can bulk-delete scenes without satellite cleanup. No “scene in use” protection exists.

## Core-object alignment

| Foundation | Status | Primary gap |
|---|---|---|
| Project | B | JSON overload |
| Scene | B | Missing typed hub links |
| Profile | C | Global-only; no attachment model |
| Asset | B | Inconsistent output registration |
| Generation | F | No durable entity |
| Timeline | C | Triple-store |
| Job | B | Free-string kinds; no Generation FK |
| Memory | F | Blob-only learning state |

## Required migrations

1. Versioned migration runner.
2. `generations`.
3. discriminated `timelines`.
4. normalized `timeline_clips`.
5. `memory_items`.
6. `scene_sheets` dual-read.
7. nullable Scene hub links.
8. `project_profile_links` / scene role attachments.
9. reference indexes and deletion audit/archive service.

## Smoke tests

- Fresh and existing DB startup twice
- Schema inventory and migration checksum
- Director JSON dual-write/dual-read
- Editor JSON and normalized clip parity
- Job → Generation → Asset link
- Learning JSON → Memory parity
- Project/scene deletion protection and orphan scan

## Files inspected / unchanged

Inspected DB, package tables, routers, schemas, worker, frontend types and consumers. No DB or source file was modified.

