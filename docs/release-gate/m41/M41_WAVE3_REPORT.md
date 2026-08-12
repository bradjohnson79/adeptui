# M41 Phase 4.1 — Wave 3: Canonical Production Read Tools

| Field | Value |
|---|---|
| **Phase** | 4.1 — Co-Director Production Completion |
| **Wave** | 3 — Canonical production retrieval |
| **Date** | 2026-07-28 |
| **Product** | Adept UI Studio / Co-Director / Adept FilmWorks |
| **Baseline** | Wave 1 GO · Wave 2 GO · [`M41_CODIRECTOR_AUDIT.md`](./M41_CODIRECTOR_AUDIT.md) |
| **Related** | [`M41_IMPLEMENTATION_REPORT.md`](./M41_IMPLEMENTATION_REPORT.md) · [`M41_TEST_REPORT.md`](./M41_TEST_REPORT.md) |
| **Verdict** | **GO — M41 Wave 3 canonical production retrieval complete** |

---

## 1. Objective

Extend the existing closed Co-Director tool registry into a grounded **production reader**: canonical envelopes, dotted aliases, gap read tools, project isolation, and Project Content retrieval cards — without becoming the production operator.

Wave 3 exclusively owns **M41-CD-35 through M41-CD-54**. Mutations, generation, Editor place, job retry, and Wave 4+ plan state machines remain out of scope.

---

## 2. Scope

| In scope | Out of scope |
|---|---|
| Read envelopes at `execute_read` | Mutating execute endpoint |
| Gap tools (scripts, proposals, jobs, plans, continuity, workspace, capabilities) | Proposal apply / approve via tools |
| Dotted aliases + pagination defaults (25/100) | Editor place / subtitles |
| Project Content retrieval cards | Specialist execution |
| Same ProposalService as Approvals | Fabricated progress / invented URLs |
| Short TTL project-keyed cache (stable reads) | Wave 4+ operator waves |

---

## 3. Read-capability audit

Pre-implementation matrix is recorded in [`M41_IMPLEMENTATION_REPORT.md`](./M41_IMPLEMENTATION_REPORT.md) (Wave 3 Read Capability Audit). Post-implementation: Missing gaps filled; Duplicate surfaces labeled; Placeholder paths remain honesty-flagged (m214 scaffolded, mock provider E2E-only).

---

## 4. Canonical registry

Closed registry in `studio-api/app/codirector/tools/` remains the single bind table. Wave 3 adds definitions + handlers; does **not** create a parallel registry.

- Handlers keep typed domain returns.
- `ToolExecutionService.execute_read` wraps `RetrievalResult` envelopes.
- Mutating tools still require `propose` → human approve.

Counts after Wave 3: **82 read / 37 mutating** (119 total declarations including aliases).

---

## 5. Registered tool matrix (Wave 3 canonical)

| Tool ID | Version | Repository | Requires project | Pagination | Filters | Status | Test evidence |
|---|---|---|---|---|---|---|---|
| `project.get_summary` | 1 | project_service + stores | Yes | — | — | Working | M41-CD-44 |
| `project.list_blockers` | 1 | session_context + bible conflicts | Yes | — | — | Working | M41-CD-44 |
| `script.list/get/search` | 1 | script_storyboard | Yes | cursor/limit | query/scriptId | Working | M41-CD-41,45 |
| `scene.list/get/search` | 1 | scene_service | Yes | limit | query | Working | M41-CD-45 |
| `scene.list_characters/assets` | 1 | scene + assets | Yes | — | sceneId | Working | M41-CD-45 |
| `character.list/get/search` | 1 | character_identity | Yes | limit | query | Working / Partial if flag off | M41-CD-46 |
| `production_bible.*` | 1 | bible ops/domain | Yes | limit | entityType/query | Working | M41-CD-47 |
| `asset.list/get/search` | 1 | assets | Yes | cursor/limit | query | Working | M41-CD-42,48 |
| `production_plan.list/get` | 1 | intelligence + m214 (scaffolded) | Yes | cursor/limit | — | Working | M41-CD-49 |
| `proposal.list/get` | 1 | ProposalService | Yes | cursor/limit | status | Working | M41-CD-49 |
| `job.list/get` | 1 | executive + render | Yes | cursor/limit | source/status | Working | M41-CD-50 |
| `continuity.list/get_finding` | 1 | bible conflicts + vision | Yes | cursor/limit | — | Working | M41-CD-51 |
| `workspace.get_active_context` | 1 | session_context | Yes | — | scene/workspace | Working | M41-CD-54 |
| `system.list_capabilities` | 1 | tool registry | Yes | — | — | Working | M41-CD-54 |

Aliases (examples): `scene.list`→`list_scenes`, `character.list`→`list_character_profiles`, `production_bible.get_entry`→`get_bible_entity`.

---

## 6. Repositories reused

Live domain services/stores only (`project_service`, `script_storyboard`, `SceneService`, `character_identity`, bible ops/domain, assets, intelligence plans, `ProposalService`, executive `JobStore`, classic `Job`, vision store, `session_context`). Inert `app/repositories/` contracts unused.

---

## 7. Read-only enforcement

- `POST .../tools/read` rejects mutating tools with `TOOL_KIND_MISMATCH` (M41-CD-39).
- Script reads never call `get_or_create_script_doc`.
- Continuity listing uses `detect_all_conflicts` (no `sync_conflicts` write).
- Read suite regression asserts asset timestamps unchanged.

---

## 8. Project isolation

- Project id required in URL path (no silent remembered-project retrieval).
- Cross-project script/asset access returns 403/404 (`PROJECT_SCOPE_VIOLATION` / `TOOL_TARGET_NOT_FOUND`).
- Absolute paths scrubbed from results (`<path>`).

---

## 9. Retrieval envelopes

`studio-api/app/codirector/tools/read_envelope.py`

- Result: `status` success|partial|empty|failed, `summary`, `data`, `evidence[]`, `pagination?`, `warnings[]`, `retrievedAt`
- Evidence: `sourceType`, `sourceId`, `repository`, optional name/version/updatedAt
- Compatibility: handlers unchanged for internal callers; envelope only at `execute_read`

Error codes added/aliased: `TOOL_VERSION_UNSUPPORTED`, `RETRIEVAL_FAILED`, `RETRIEVAL_PARTIAL`, `PROJECT_ACCESS_DENIED`, `TOOL_ARGUMENT_INVALID`.

---

## 10. Pagination and search semantics

- Default page **25**, max **100** (`clamp_limit`).
- Cursor is opaque integer offset string where implemented.
- Search methods disclosed as `case-insensitive text search` (not semantic/vector).
- Scene–character links labeled `canonical` vs `textual_match`.

---

## 11. Project Content integration

- `studio-web/src/components/CoDirector/retrieval/*` — envelope cards + evidence disclosure.
- Overview / Library / Plans / Bible / Jobs tabs load via `runCoDirectorReadTool`.
- Approvals continues to use `api.listProposals` → **same ProposalService** as `proposal.list`.
- No mutation controls on retrieval cards.

---

## 12. Security findings

| Finding | Disposition |
|---|---|
| Cross-project ID checks on get handlers | Enforced |
| Absolute filesystem paths in results | Scrubbed |
| Unknown args | Dropped by sanitize (schema allow-list) |
| Invented preview URLs | Forbidden (`previewUrl: null`) |
| Fabricated job progress (executive) | `progress: null`, `progress_available: false` |
| Cache keyed by project+tool+args; jobs/proposals always fresh | Implemented (`read_cache.py`, TTL ~8s) |
| Stored project text treated as untrusted for model render | Existing scrub + char budgets |

---

## 13. Files changed (primary)

**Backend:** `read_envelope.py`, `read_cache.py`, `aliases.py`, `handlers/wave3_reads.py`, `definitions.py`, `registry.py`, `execution.py`, `errors.py`, `handlers/scenes.py`, `handlers/character_identity.py`, `handlers/bible_read.py`, `handlers/bible_domain.py`, `routers/codirector.py`

**Frontend:** `retrieval/*`, `CoDirectorProjectContent.tsx`, `navEntries.ts`, `api.ts`, `codirector-cinematic.css`

**Tests/reports:** `test_m41_codirector_wave3.py`, `m41-cd-wave3.spec.ts`, wave2 jobs-nav expectation update, this report + IMPLEMENTATION/TEST updates

**Artifacts:** `artifacts/m41/wave3/*.png`

---

## 14. M41-CD-35 … M41-CD-54 results

| ID | Title | Result |
|---|---|---|
| M41-CD-35 | Read registry exposes only approved canonical read tools | PASS |
| M41-CD-36 | Unknown tool ID is rejected | PASS |
| M41-CD-37 | Unsupported tool version is rejected | PASS |
| M41-CD-38 | Invalid tool arguments are rejected | PASS |
| M41-CD-39 | Wave 3 route cannot execute mutation tools | PASS |
| M41-CD-40 | Project-scoped read requires explicit project | PASS |
| M41-CD-41 | Project A cannot retrieve Project B scripts | PASS |
| M41-CD-42 | Project A cannot retrieve Project B assets or Bible entries | PASS |
| M41-CD-43 | Remembered project is never silently used for retrieval | PASS |
| M41-CD-44 | Project summary returns real counts and evidence | PASS |
| M41-CD-45 | Script and scene retrieval return canonical records | PASS |
| M41-CD-46 | Character retrieval returns stored profile without fabrication | PASS |
| M41-CD-47 | Production Bible distinguishes canonical and draft entries | PASS |
| M41-CD-48 | Asset retrieval returns safe metadata without invented URLs | PASS |
| M41-CD-49 | Plans and proposals return stored state without advancement | PASS |
| M41-CD-50 | Job retrieval does not fabricate progress | PASS |
| M41-CD-51 | Continuity retrieval returns only real findings | PASS |
| M41-CD-52 | Empty, partial, failed, and successful reads remain distinct | PASS |
| M41-CD-53 | Reconnect does not duplicate a read-tool execution | PASS |
| M41-CD-54 | Project Content renders structured retrieval with evidence | PASS |

---

## 15. Wave 1 regression

```text
pytest tests/test_m41_codirector_wave1.py -q
# 16 passed
```

---

## 16. Wave 2 regression

```text
npx playwright test tests/e2e/m41/m41-cd-wave2.spec.ts
# passed (exit 0)
```

Note: Jobs nav is now enabled for **read-only** Project Content (Wave 3). Wave 2 e2e expectation updated accordingly; no mutation controls introduced.

---

## 17. Manual / Playwright-assisted scenarios

Covered via Wave 3 e2e: project summary, scene/list retrieval, character list honesty, bible search (or honest unavailable), asset metadata, plans/proposals readonly, jobs without fake progress, continuity findings, Project Content evidence, Approvals empty honesty, requestId dedupe.

---

## 18. Screenshot evidence

Under `artifacts/m41/wave3/`:

- `m41-cd-44-project-summary.png`
- `m41-cd-45-scene-retrieval.png`
- `m41-cd-46-character-profile.png`
- `m41-cd-47-bible-canonical-status.png`
- `m41-cd-48-asset-metadata.png`
- `m41-cd-49-plan-proposal-readonly.png`
- `m41-cd-50-job-no-fake-progress.png`
- `m41-cd-51-continuity-findings.png`
- `m41-cd-52-partial-result.png`
- `m41-cd-54-project-content-evidence.png`

---

## 19. Known limitations

- Tool loop remains `TOOL_LOOP_LIMIT = 1` (one read per chat turn).
- Pagination is offset-cursor, not opaque DB cursors.
- Character Identity tools return partial/unavailable when feature flag off.
- m214 plans are scaffolded honesty only.
- Heuristic continuity suggestions excluded from canonical findings.
- Cache is process-local memory (not shared across workers).

---

## 20. Deferred work

Mutations, generation, Editor place/subtitles, job cancel/retry, specialist execution, Director 2.0 timeline apply, Wave 4 plan state machine, full Phase 4.1 certification beyond M41-CD-35…54.

---

## 21. Final verdict

**GO — M41 Wave 3 canonical production retrieval complete**
