# Additive Schema Migration Plan

**Rule:** No destructive migration. New tables are dual-written, backfilled, verified, and feature-flagged before cutover.

## Migration framework

### M001 — `schema_migrations`

Record version, name, timestamp, checksum, and rollback-disabled state. Apply each migration transactionally. Enable `PRAGMA foreign_keys=ON` per connection. Keep existing startup column checks during transition.

### M002 — backup metadata

Add `project_backups(id, project_id, path, created_at, checksum, note)` only after backup/restore tooling is designed.

## Foundation migrations

### M003 — `generations`

Fields: IDs for project/scene/job, mode, provider, workflow template, model, status, prompt/negative, params JSON, output asset IDs, source lineage JSON, timestamps.

- Insert on enqueue; update from worker.
- Backfill completed Jobs idempotently.
- Job-only reads remain fallback.

### M004 — `timelines`

Discriminator `director|editor`, project/optional scene, status, duration, version, data JSON.

- Scene Director PUT dual-writes `director_json` and timeline.
- Director Sequence remains an approved/versioned package.
- Editor compatibility endpoint dual-writes its editor timeline.

### M005 — `timeline_clips`

Normalize Editor clips with timeline/track/asset/source Director/Storyboard/Script IDs, timing, audio values, and metadata.

- `GET/PUT /editor` remains wrapper.
- Backfill from `editor_projects.data_json`.
- Verify clip counts and pending-newer flags.

### M006 — `memory_items`

Project, category, text, source, approved, timestamps.

- Backfill `learning_json.items`.
- Continue learning JSON mirror until Phase 6.
- Preserve dismissed-continuity state separately.

### M007 — `scene_sheets`

Project/scene, approved version, five-section data JSON, lightweight blocking JSON, legacy Master Sheet ID.

- Add `/scene-sheet` alias.
- Existing `/master-sheet` reads/writes both.
- Preserve full Spatial rows; copy only blocking summaries/references.

### M008 — Scene hub links

Add nullable `scene_sheet_id`, `script_document_id`, `status`, and extensible metadata. Use satellite lookup as fallback.

### M009 — Profile attachments

Add project/scene/profile/role link table. Do not copy/delete global profile rows during initial migration.

### M010 — indexes and cleanup inventory

Index soft references. Do not add restrictive FKs until orphan reports are clean.

### M011 — deletion audit/archive

Before project/scene deletion:

1. detect Editor/Sequence/Story usage;
2. block or require explicit confirmation;
3. archive satellites;
4. record affected IDs and paths;
5. set nullable refs to null where appropriate.

## Compatibility schedule

| Legacy | Unified | Retain through |
|---|---|---|
| `/learning` | `/memory` | Phase 6 |
| `/master-sheet` | `/scene-sheet` | Phase 6 |
| scene `/director` | director Timeline | Phase 5+ |
| `/editor` JSON | editor Timeline/Clip | Phase 5+ |
| Job-only history | Generation + Job | Phase 3+ |

## Verification per migration

- before/after row counts and hashes
- idempotent second execution
- API round-trip through legacy and unified endpoints
- sample project reopen
- no orphan increase
- feature flag rollback to old reader

## Rollback

Rollback is code-path reversal plus database-file restore—not destructive reverse DDL. Keep new tables, disable new reads/writes, restore the verified SQLite snapshot if data parity fails.

