# Test and Smoke Plan

## Current quality state

- No Python, frontend, E2E, or CI test suite.
- No root/API test script; pytest is not a dependency.
- Available gates: `tsc -b`, `oxlint`, API health endpoints, setup detection.
- Comfy client can become injectable; FFmpeg subprocess calls require an interface.
- No committed sample project fixture.
- Export exists; restore is missing.

## Verified commands (manifest inspection only)

These were **not executed** in the audit because they may write data/caches:

```powershell
# Web
cd studio-web
npm run lint
npx tsc -b --pretty false
npm run build

# API import validation
cd studio-api
.\.venv\Scripts\python -m compileall app

# Runtime
npm run api
npm run web
```

`pytest` is not currently valid until a dev test dependency/harness is added.

## Isolation rules

- Always use a temporary `STUDIO_DATA_DIR`.
- Never point smoke tests at user data.
- Create uniquely named temporary projects and remove the whole temp root.
- Mock Comfy/fal/Ollama for deterministic tests.
- Inject an FFmpeg runner; retain one optional real FFmpeg integration test.

## Smoke matrix

| ID | Scenario | Gate |
|---|---|---|
| S01 | API + Web startup | G1 |
| S02 | TypeScript typecheck/lint/build | G2 |
| S03 | Python imports + double migration startup | G3 |
| S04 | Create/reopen Project and Scene | G4 |
| S05 | Profile create/attach | G4 |
| S06 | Script edit + storyboard outdated behavior | G4 |
| S07 | Scene Sheet round-trip | G4 |
| S08 | Director Sequence creation | G8 |
| S09 | Image/video job queue | G5 |
| S10 | cancellation/missing model/Comfy failure | G5/G6 |
| S11 | Job status persists/reconciles after restart | G6 |
| S12 | output Asset appears in Library with lineage | G7 |
| S13 | audio import/generation to Editor | G7/G8 |
| S14 | Editor clip and Open Source | G8 |
| S15 | non-destructive version replacement | G8 |
| S16 | Editor preview/export | G8 |
| S17 | backup and restore | G9 |
| S18 | final target navigation | G10 |

## Phase gates

1. Startup
2. Type safety
3. Backend integrity
4. Project integrity
5. Workflow integrity
6. Jobs integrity
7. Asset integrity
8. Timeline integrity
9. Backup integrity
10. Navigation integrity

Run relevant gates before and after every migration/route replacement, before deletion, and at phase completion.

## Harness recommendation

- `studio-api/requirements-dev.txt`: pytest, pytest-asyncio, httpx/respx
- temp-data fixtures and FastAPI TestClient
- fake Comfy adapter and injectable FFmpeg runner
- tests for health, CRUD, migration idempotence, jobs/cancel, media ops, sequence/editor lineage
- root scripts for API tests, Web gates, and smoke runner
- minimal fixture project with tiny media

## Current blockers

- G9 cannot pass: no restore implementation.
- G4 fixture coverage cannot pass: no committed sample fixture.
- G6 restart semantics are broken for queued/running jobs.
- full workflow gates depend on local model availability; deterministic mocks are required.

## Files inspected / unchanged

Manifests/configs, startup, health, DB init, worker, providers, media ops, API client/UI surfaces. No command was executed and no source file changed.

