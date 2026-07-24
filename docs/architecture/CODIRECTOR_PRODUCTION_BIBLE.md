# Co-Director Milestone 2.1 — Production Bible

**Date:** 2026-07-24
**Branch:** `phase2/codirector-m2-1-production-bible`
**Related:** `docs/architecture/CODIRECTOR_IMPLEMENTATION_PLAN.md` (M1, implemented),
`docs/architecture/CODIRECTOR_PRODUCTION_BRAIN.md` (M2/M3 vision this milestone partially
fulfills), `docs/architecture/CODIRECTOR_PROPOSALS_AND_APPROVALS.md` (the write path),
`docs/audit/CODIRECTOR_M2_1_PREFLIGHT.md`, `docs/audit/CODIRECTOR_M2_1_IMPLEMENTATION_REPORT.md`
**Status:** Implemented.

---

## 1. What this is

The Production Bible is a versioned, structured, per-project knowledge base — characters,
locations, visual style, production/continuity rules, narrative threads, scene facts, props,
and organizations — that Co-Director reads from on every chat turn and can *propose* changes
to, but never writes to directly. It replaces "the user re-explains established facts every
chat" with a durable, diffable record.

It deliberately does **not** implement (see `CODIRECTOR_PRODUCTION_BRAIN.md` and the M2.1 scope
boundary below): task graphs, render orchestration, arbitrary tool calling, automatic/silent
Bible mutation, prompt compilers, asset lineage, or a continuity engine that blocks generation.
Those remain M2/M3 candidates this milestone deliberately does not pull forward.

---

## 2. Data model

Seven tables, added by `studio-api/app/migrations/m002_production_bible.py` and mirrored as
SQLAlchemy models in `studio-api/app/db.py` (both paths are exercised by
`test_migration_and_create_all_produce_the_same_bible_tables`, which asserts the migration's
`CREATE TABLE` DDL and `Base.metadata.create_all()` produce identical columns):

| Table | Purpose |
|---|---|
| `production_bibles` | One row per project (`project_id` unique). Points at `current_version_id`. |
| `production_bible_versions` | Immutable snapshots. `version_number`, `parent_version_id`, `summary`, `change_reason`, `created_by`, `created_at`. Never updated in place — see §3. |
| `production_bible_entities` | Rows scoped to one `bible_version_id`. `entity_type`, `entity_key`, `display_name`, `data_json`. |
| `production_bible_facts` | Free-form continuity/narrative statements scoped to one version, optionally tied to an `entity_key`. |
| `codirector_proposals` | Durable, reviewable proposed Bible mutations. See `CODIRECTOR_PROPOSALS_AND_APPROVALS.md`. |
| `codirector_approvals` | Audit trail of every approve/reject/request-revision/cancel decision on a proposal. |
| `codirector_execution_receipts` | One row per proposal execution attempt, keyed by an idempotency `input_hash`. |

**Entity types** (`app/codirector/bible/schemas.py::EntityType`): `project_profile`,
`character`, `location`, `visual_style`, `production_rule`, `continuity_rule`,
`narrative_thread`, `scene_fact`, `prop`, `organization`.

### 2.1 Copy-on-write versioning

Every write — manual edit or approved proposal — goes through
`operations.apply_mutation_set()`, which:

1. Loads the current version's full entity/fact set (or nothing, for version 1).
2. Applies the mutation set (`EntityMutation`/`FactMutation`, each either an upsert or a
   `remove: true`) in memory.
3. Persists the *entire resulting set* as brand-new `ProductionBibleEntity`/`ProductionBibleFact`
   rows under a brand-new `ProductionBibleVersion` row.
4. Repoints `production_bibles.current_version_id` at the new version.

Older versions are never mutated or deleted — `GET /bible/versions/{n}` always returns exactly
what was true at that version, which is what makes "what did the Bible say when scene 4 was
generated" answerable later (the continuity-engine precondition called out in
`CODIRECTOR_PRODUCTION_BRAIN.md`).

---

## 3. Read path: `ProjectContextService`

`app/codirector/bible/context.py::ProjectContextService.build(db, project_id, token_budget=1200)`
is the *only* way the Bible reaches a chat turn. It is called from
`codirector/service.py::_prepare_chat_request` — the same centralized context-building function
M1 already used for project/scene context and learning preferences — so Bible injection has one
call site, not N.

```python
bible_excerpt, context_manifest = ProjectContextService.build(db, project_id)
if bible_excerpt:
    context = (context or "") + "\n\n" + bible_excerpt
```

Behavior:

- **No `project_id`, no Bible, or no current version** → returns `("", empty ContextManifest)`.
  Projects without a Bible see byte-for-byte the same context as before M2.1 — this is additive,
  not a breaking change to M1's context construction.
- **Bounded by `token_budget`** (default 1200, ~4 chars/token estimate). Entities are sorted by
  `ENTITY_TYPE_PRIORITY` (`project_profile`, `visual_style`, `character`, `location`,
  `continuity_rule`, `production_rule`, `narrative_thread`, `organization`, `prop`, then
  `scene_fact` last — the most granular/least universally-relevant type is trimmed first).
  The **first** entity is always included regardless of cost so a tiny budget never yields an
  empty excerpt; everything after that is dropped once the running budget goes negative, and
  `manifest.truncated` is set.
- Returns a `ContextManifest` (`projectId`, `bibleVersionId`, `bibleVersionNumber`,
  `includedEntityKeys`, `includedFactIds`, `tokenBudget`, `estimatedTokens`, `truncated`) — this
  is what the FE receives as a `context_manifest` SSE event (streaming) or the `contextManifest`
  field (non-streaming `/chat`), so the UI can eventually show "grounded in Bible v3, 6/9
  entities included" without re-deriving it.

---

## 4. APIs (`/api/codirector/projects/{projectId}/bible...`)

`projectId` in the path always wins over any project id embedded in a request body (there is no
project id in any Bible request body — it's implicit from the path).

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/bible` | Current version + version count. `404 BIBLE_NOT_FOUND` if none exists yet. |
| `GET` | `/bible/versions` | All versions, newest first. |
| `GET` | `/bible/versions/{n}` | One immutable historical version by number. `404 BIBLE_VERSION_NOT_FOUND`. |
| `POST` | `/bible/import/preview` | Derives a Bible seed from existing project data (name, `global_prompt` → `visual_style`, tagged assets → `character`/`prop`, scene prompts → `scene_fact`). **Pure read — persists nothing.** |
| `POST` | `/bible/import/confirm` | Persists the previewed (or edited) entities/facts as version 1. `409 BIBLE_ALREADY_EXISTS` if a Bible already exists — re-seeding goes through a new version, not re-import. |
| `POST` | `/bible/versions` | Manual, user-authored edit: applies a `BibleMutationSet` directly, creating the next version immediately (no proposal round-trip — this is the *user* editing their own Bible, not the model). |

The import preview/confirm split exists so nothing is written until the user has reviewed what
would be imported — the FE's `ProductionBibleWorkspace` renders the preview, then only calls
confirm once the user clicks "Confirm — create version 1".

---

## 5. Frontend: `ProductionBibleWorkspace`

`studio-web/src/components/ProductionBibleWorkspace.tsx`, registered as the `bible` workspace in
`core/workspaces.ts` (reachable via the project editor's hamburger menu → Production, or
`?workspace=bible`). States:

1. **No Bible yet** → "Import from project" CTA.
2. **Preview** → read-only list of entities/facts that would be imported, with a Cancel/Confirm
   choice. Nothing is persisted in this state.
3. **Bible view** → current version's entities and facts, a version switcher (`v1`, `v2`, …), and
   a manual "Add entity" mini-form that immediately creates a new version via
   `POST /bible/versions`.

Bible mutations are **never** routed through `CoDirectorSession`'s local `runSteps`/`ActionPlan`
mechanism (the FE-only heuristic planner from M1) — they go directly through the dedicated
`api.{getBible,previewBibleImport,confirmBibleImport,createBibleVersion,...}` client methods
against the Bible API surface above.

---

## 6. What the model can and cannot do

**Reads:** the model sees a bounded, summarized excerpt every turn (§3) — it can reference
established facts without the user repeating them.

**Writes: never directly.** The model has no tool or API path that mutates the Bible. Its only
lever is emitting a ```` ```proposal ```` fenced JSON block in a chat reply, which the backend
parses into a durable, human-reviewable `CoDirectorProposal` row — the model proposes, the user
disposes. See `CODIRECTOR_PROPOSALS_AND_APPROVALS.md` for that full lifecycle.

---

## 7. Testing

- **Unit** (`studio-api/tests/test_production_bible.py`, 31 tests): import preview/confirm,
  version immutability/copy-on-write, entity add/remove mutations, `ProjectContextService`
  token-budget truncation and empty-Bible passthrough, structured-output fence parsing, and
  migration/`create_all` schema parity.
- **E2E** (`tests/e2e/codirector/production-bible.spec.ts`, `@critical` for the import-confirm
  and proposal-approve flows): import preview → confirm creates version 1 in the real UI; manual
  entity add creates version 2.
