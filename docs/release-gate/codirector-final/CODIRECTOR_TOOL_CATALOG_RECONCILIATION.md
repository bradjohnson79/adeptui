# Co-Director Tool Catalog Reconciliation

Date: 2026-08-02  
Repo: `C:\AdeptFilmWorks\AIVideoStudio`  
Branch: `feature/ai-guided-setup`  
Beta: UI `http://127.0.0.1:8760/` API `http://127.0.0.1:8758/`

## Scope

This follow-up gate audited the declared Co-Director tool contract across:

- `studio-api/app/codirector/tools/definitions.py`
- `studio-api/app/codirector/tools/registry.py`
- model-exposed catalog route at `GET /api/codirector/tools`
- execution and proposal routing in `studio-api/app/routers/codirector.py`
- `studio-api/app/codirector/tools/execution.py`
- `studio-api/app/codirector/tools/capability_bridge.py`
- `studio-api/tests/test_codirector_tools.py`

Beta was down at the start of the audit, so `Restart-AdeptUI-Beta.ps1` was run first. Beta came back cleanly and was used for the live-call matrix below.

## Mismatch Inventory

1. `tests/test_codirector_tools.py` hard-coded read/mutating tool snapshots no longer matched the declared catalog.  
Classification: `obsolete snapshot expectation`

- The old snapshot covered an earlier subset of the product contract.
- The authoritative catalog now contains `427` declared tools: `233` read and `194` mutating.
- The registry, handler bindings, and `/api/codirector/tools` were already aligned; the test snapshot was stale.

2. `tests/test_codirector_tools.py` still asserted pre-envelope read payloads like `body["result"]["name"]`.  
Classification: `schema drift`

- The current read-tool contract returns canonical retrieval envelopes under `body["result"]["data"]`.
- The runtime behavior was correct; the assertions were targeting the old response shape.

3. `get_generation_tools_catalog` was exposed in the catalog and availability surfaces, but returned `500` in live Beta.  
Classification: `schema drift`

- Root cause: `studio-api/app/codirector/tools/read_envelope.py` treated any top-level `status` field as envelope metadata.
- `studio-api/app/codirector/tools/handlers/generation_tools.py` returns a domain payload with `status` as a list of tool probe results.
- The wrapper performed set membership against that list and raised `TypeError: unhashable type: 'list'`.
- Fix: only treat top-level `status` as envelope metadata when it is a string in the retrieval status vocabulary.

4. `tests/test_codirector_tools.py::test_approving_twice_does_not_apply_twice` expected a second approval attempt to return `409 APPROVAL_ALREADY_RECORDED`.  
Classification: `obsolete snapshot expectation`

- `ProposalService.approve()` now intentionally behaves idempotently for completed proposals and returns the original success receipt instead of re-applying.
- The implementation matched its own docstring and receipt behavior; the test expectation had fallen behind.

5. `tests/test_codirector_tools.py::test_chat_tool_call_without_a_project_is_reported` expected `502 STRUCTURED_OUTPUT_INVALID` when the mock model proposed a tool without an open project.  
Classification: `intentionally excluded tool`

- Current chat behavior degrades to a plain assistant reply with `toolInvocations: []` and no proposal.
- Tool execution is intentionally excluded when there is no project context.

## Authoritative Contract Decisions

1. `definitions.py` plus `registry.py` are the authoritative source of truth for tool ids, kinds, approval requirements, schemas, and handler binding.
2. `/api/codirector/tools` must mirror `registry.catalog()` exactly. This was verified: identical ids and identical serialized tool payloads.
3. The audited mutating tools are exactly:
   - `production_plan.create_draft`
   - `audio.cancel_batch`
4. Read-tool HTTP responses must use the canonical retrieval envelope shape, with domain payloads nested under `result.data`.
5. Proposal approvals for completed proposals are idempotent and return the original success receipt instead of failing.
6. Chat without a project may not execute tools; the tool path is intentionally excluded in that state.
7. Capability bridge coverage is complete for the declared catalog:
   - no missing capability-key mappings
   - no stale aliases
   - no duplicate tool registrations
   - no declared tool without a bound handler

## Files Changed

- `studio-api/app/codirector/tools/read_envelope.py`
- `studio-api/tests/test_codirector_tools.py`
- `docs/release-gate/codirector-final/CODIRECTOR_TOOL_CATALOG_RECONCILIATION.md`

## Pytest Result

Command:

```text
cd studio-api && python -m pytest tests/test_codirector_tools.py -q --tb=short
```

Result:

```text
76 passed, 5 warnings in 276.16s (0:04:36)
```

Notes:

- The warnings were existing `PydanticDeprecatedSince20` warnings from dependency code, not Co-Director tool failures.

## Live Call Matrix

All calls below were run against Beta API `http://127.0.0.1:8758/` on project `fcd7b4b0-7d36-4757-ac82-a701e6e1a50c` (`The Dreamweaver`).

1. Project tools  
Command:
```text
POST /api/codirector/projects/fcd7b4b0-7d36-4757-ac82-a701e6e1a50c/tools/read
{"toolId":"get_project_profile","arguments":{}}
```
Response: `200`  
Status: `succeeded` / `success`

2. Wiki / Bible tools  
Command:
```text
POST /api/codirector/projects/fcd7b4b0-7d36-4757-ac82-a701e6e1a50c/tools/read
{"toolId":"get_production_bible_summary","arguments":{}}
```
Response: `409`  
Status: `CAPABILITY_NOT_CONFIGURED`  
Reason: Dreamweaver currently has no Production Bible in this Beta-local state, and the tool correctly fail-closed.

3. Plan tools  
Command:
```text
POST /api/codirector/projects/fcd7b4b0-7d36-4757-ac82-a701e6e1a50c/tools/read
{"toolId":"production_plan.list","arguments":{}}
```
Response: `200`  
Status: `succeeded` / `success`  
Summary: `1 plan record(s).`

4. Character tools  
Command:
```text
POST /api/codirector/projects/fcd7b4b0-7d36-4757-ac82-a701e6e1a50c/tools/read
{"toolId":"character.list","arguments":{}}
```
Response: `200`  
Status: `succeeded` / `empty`  
Summary: `0 Character Identity profile(s).`

5. Scene tools  
Command:
```text
POST /api/codirector/projects/fcd7b4b0-7d36-4757-ac82-a701e6e1a50c/tools/read
{"toolId":"scene.list","arguments":{}}
```
Response: `200`  
Status: `succeeded` / `success`  
Summary: `1 of 1 scene(s).`

6. Generation tools  
Command:
```text
POST /api/codirector/projects/fcd7b4b0-7d36-4757-ac82-a701e6e1a50c/tools/read
{"toolId":"get_generation_tools_catalog","arguments":{}}
```
Response: `200`  
Status: `succeeded` / `success`  
Notes: `resultTruncated=true` because the catalog payload is large, but the tool now succeeds instead of throwing `500`.

7. Approval tools  
Command:
```text
POST /api/codirector/projects/fcd7b4b0-7d36-4757-ac82-a701e6e1a50c/tools/read
{"toolId":"proposal.list","arguments":{}}
```
Response: `200`  
Status: `succeeded` / `success`  
Summary: `4 proposal(s).`

Supporting live sanity checks:

- `GET /api/health` -> `200`
- `GET /__beta_web_health` -> `200`
- `GET /api/projects` -> `200`, with exactly one remaining project: `The Dreamweaver`

## Dreamweaver Regression Check

Result: `pass`

Reason:

- This gate did not rerun the mutating M214 Dreamweaver UI certification script because that flow would actively post and approve content on the certified project.
- Instead, a non-mutating Dreamweaver regression probe was run against live Beta:
  - project still present as `The Dreamweaver`
  - `/api/projects` still returns exactly one project
  - representative project, plan, scene, character, generation, and approval tool reads succeeded
  - Bible tools correctly fail-closed with `CAPABILITY_NOT_CONFIGURED` rather than surfacing raw registry/runtime errors
- No regression was discovered in the certified Dreamweaver path during this catalog reconciliation.

## Gate Verdict

**READY FOR WHOLE-PRODUCT CODIRECTOR CERT**

Rationale:

- definitions, registry, handlers, capability bridge, and model-exposed catalog are reconciled
- no stale aliases, duplicate registrations, or missing handler bindings remain in the audited surfaces
- the live Beta generation-catalog `500` was repaired
- `tests/test_codirector_tools.py` is green end-to-end
- Beta is up and the representative live matrix completed successfully
