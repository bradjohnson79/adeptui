# Phase 0 Architecture Boundaries

Phase 0 adds contracts and inventories only. It does not replace current routes,
schemas, database access, workflow builders, ComfyUI calls, FFmpeg calls, or
desktop behavior. Feature flags remain disabled by default.

## Database migrations

`studio-api/app/migrations` contains an explicit, forward-only registry and
runner. The runner creates `schema_migrations`, records stable checksums and
rollback metadata, and applies each pending migration in a transaction. SQLite
connections enable `PRAGMA foreign_keys=ON` before metadata or migration work.
M001 is an idempotent baseline and does not alter application tables. Nothing
invokes the runner during application startup.

Rollback fields are informational in Phase 0. There is no destructive or
automatic down-migration mechanism.

## Providers

`studio-api/app/providers` separates five concerns:

1. Lifecycle: start, stop, and health state.
2. Capabilities: discoverable features and constraints.
3. Authentication: provider-neutral credentials, scopes, and auth results.
4. Execution: request submission, handles, status, cancellation, and result
   retrieval.
5. Cost ownership: estimates and receipts identify whether local resources, a
   customer provider account, or an Adept Cloud account owns the cost.

Local, External API, and Adept Cloud are Protocol contracts only. No external
provider is implemented, selected, authenticated, or called.

## Workflow registry

`studio-api/app/workflows/registry.py` inventories existing LTX, WAN,
LatentSync, and image builders without invoking or changing them. Every entry
records a template version, supported provider kinds, required inputs,
capabilities, and ComfyUI compatibility metadata. Validation checks metadata
requirements only; it never calls a builder or probes ComfyUI.

## Repositories

`studio-api/app/repositories` defines Project, Scene, Profile, Generation,
Timeline, Asset, Job, and Memory repository Protocols. The SQLite types are
inert boundary markers and factory contracts. Existing SQLAlchemy models,
sessions, startup schema creation, and route access remain authoritative.

## Desktop platform

`studio-api/app/desktop_platform` defines host-neutral contracts for filesystem,
settings, secrets, windows, notifications, dialogs, clipboard, temporary files,
and explicit OS integration. The OS integration boundary exposes selected
operations such as opening or revealing a path and excludes arbitrary command
execution. These contracts contain no Electron dependency.

## Infrastructure adapters

`studio-api/app/adapters` provides unwired wrappers for the existing ComfyClient
and validated FFmpeg operations. The public FFmpeg boundary exposes stitching
and audio muxing only; it does not expose arbitrary FFmpeg arguments or shell
execution. Existing production call sites are unchanged.

## Feature flags

`studio-api/app/feature_flags.py` defines `unified_generate`, `story`,
`scene_sheets`, `jobs`, `resources`, and `future_rollout`. All default to
`false`. Overrides use `STUDIO_FEATURE_<FLAG_NAME>`. Current production code
does not consume these flags.
