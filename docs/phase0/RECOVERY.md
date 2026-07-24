# Phase 0 Backup and Recovery

This tooling creates a read-only snapshot of Adept UI data before refactor or
migration work. It does not alter the live database or other production files.

Run commands from `studio-api`:

```powershell
python -m app.safety create C:\Backups\adept-before-phase1.zip
python -m app.safety verify C:\Backups\adept-before-phase1.zip
python -m app.safety restore C:\Backups\adept-before-phase1.zip C:\AdeptRestore\phase1-check
```

Use `--repo-root` and `--data-dir` when the repository or application data is
in a non-default location:

```powershell
python -m app.safety create C:\Backups\adept.zip `
  --repo-root C:\AdeptFilmWorks\AIVideoStudio `
  --data-dir D:\AdeptData
```

## Backup contents

The archive contains:

- the full application data directory, including project folders, split asset
  roots, profiles, settings state, sample data, and encrypted secret files;
- `studio.db`, copied through the SQLite backup API rather than as a live file;
- root workflow JSON metadata;
- Python workflow builders and image workflow definitions;
- settings definitions and any discovered `.env` files;
- the complete `studio-api/knowledgebase`;
- sample/example directories when present.

Transient `studio.db-wal`, `studio.db-shm`, and rollback-journal files are
excluded because their committed contents are already captured by the SQLite
backup API.

Secrets and environment files are copied only as opaque bytes. The tool never
parses or prints their contents. The resulting archive can contain credentials
and must be stored with the same protections as the live data directory.

Each archive has `manifest.json` with a schema name/version, tool version,
UTC creation timestamp, safe relative path, byte size, SHA-256, category, and
sensitivity marker for every file. No machine-specific source paths are stored
in the manifest.

## Verification guarantees

`create` verifies the archive before publishing it. `verify` independently:

1. rejects absolute, parent-relative, non-canonical, duplicate, encrypted,
   directory, and symbolic-link ZIP members;
2. requires the archive member set to exactly match the manifest;
3. streams and checks every declared size and SHA-256;
4. extracts each declared SQLite database to a temporary location and runs
   `PRAGMA integrity_check`.

A failed create never replaces an existing archive. Archive paths are immutable:
the tool refuses to overwrite the requested output.

## Isolated restore

Restore always requires an explicit destination. The destination:

- must not exist;
- cannot be the live repository or data directory;
- cannot contain, or be inside, either live path;
- receives only validated relative archive members;
- is removed if extraction or post-restore verification fails.

After extraction, restore recomputes every restored size and SHA-256 from the
manifest and runs SQLite integrity checks again. It does not update settings,
start the API, or copy files into production.

The restored layout uses `data/` for application data and `repository/` for
workflow, knowledgebase, settings-definition, and sample-project snapshots.
To recover production data, first inspect and test this isolated tree. Any later
copy into a live installation is a separate, deliberate operator action and
should only occur while the API and workers are stopped.

## Recovery drill

Before Phase 1:

1. Create an archive outside the live data directory.
2. Run `verify` as a separate command.
3. Restore to a new isolated destination.
4. Confirm `data/studio.db` exists when the source had a database.
5. Start a disposable API instance with `STUDIO_DATA_DIR` set to the restored
   `data` directory and perform baseline smoke tests.
6. Preserve the verified archive until the refactor and migration cycle is
   accepted.
