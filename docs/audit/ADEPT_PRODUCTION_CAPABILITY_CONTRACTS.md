# Adept Production Capability Contracts

**Implements:** `studio-api/app/capabilities/` (`registry.py`, `probes.py`, `service.py`, `models.py`, `errors.py`, `api.py`)
**Consumed by:** `studio-web/src/capabilities.ts`, `studio-web/src/components/CapabilityPanel.tsx`, the Setup Wizard, the Source Manager, and (next) the Co-Director M2.2 tool registry
**Verified by:** `studio-api/tests/test_capabilities.py`, `tests/e2e/capabilities/capabilities.spec.ts`

This is the API contract. The companion matrix (`ADEPT_PRODUCTION_CAPABILITY_MATRIX.md`) lists
*which* capabilities exist; this document defines *what the payload means* and what a consumer
is and is not allowed to conclude from it.

---

## 1. The rule that makes the rest of it work

> **A consumer never re-derives readiness.**

Before this milestone, three different surfaces each decided independently whether the studio
was usable: the chrome status strip counted `health.missing_models`, the Setup Wizard summed
component statuses, and the Source Manager looked at source availability. They could and did
disagree — the strip could show "ComfyUI Connected" while a render was guaranteed to fail on a
missing node type.

Every readiness question now has exactly one answer, computed server-side from the registry plus
live probes, and published at `GET /api/capabilities`. A consumer that wants to know whether
something is usable reads `available` on that capability. It does not check a model path, count a
component list, or ping ComfyUI itself.

---

## 2. Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/capabilities` | Full snapshot. Optional `?projectId=…` adds project-scoped evaluation; `?refresh=true` forces a re-probe. |
| `GET` | `/api/capabilities/{capabilityId}` | One capability, with its dependencies evaluated. `404` with `CAPABILITY_NOT_FOUND` for an unknown id. |
| `GET` | `/api/projects/{projectId}/capabilities` | Project-scoped snapshot. `404` with `PROJECT_NOT_FOUND` for an unknown project. |
| `POST` | `/api/capabilities/refresh` | Drop the probe cache and re-probe. **Read-only side effects only** — never installs, downloads, or mutates project state. |
| `GET` | `/api/comfy/health` | Structured ComfyUI health (see §7). |
| `GET` | `/api/workflows` | Static description of every registered workflow. |
| `GET` | `/api/workflows/{workflowId}/readiness` | Whether one workflow can run now, with `missingModels` / `missingExtensions`. |

### Why the project route 404s but the query parameter does not

`GET /api/capabilities?projectId=X` answers a dashboard question — *what can this studio do, in
this project's context?* — so an unknown project yields a `200` whose project-scoped entries are
`blocked` with `PROJECT_NOT_FOUND`. `GET /api/projects/X/capabilities` is a lookup of one
project's capabilities, so an unknown id is a `404`. Returning a full snapshot of blockers there
would make a typo'd project id look like a broken studio.

---

## 3. Snapshot payload

```json
{
  "projectId": null,
  "generatedAt": "2026-07-24T22:25:03.559353+00:00",
  "correlationId": "3f2c…",
  "counts": { "locally_verified": 34, "blocked": 13, "partially_wired": 13, "...": 0 },
  "capabilities": [ /* CapabilityOut, one per registry entry */ ],
  "blockers": [ /* CapabilityBlockerOut, subset of capabilities */ ],
  "callable": ["project.create", "project.scenes.update", "..."],
  "probeWarnings": []
}
```

| Field | Contract |
|-------|----------|
| `counts` | Status name → count. Sums to `capabilities.length`. |
| `capabilities` | Every registry entry, always. A capability is never omitted because it is unavailable — absence would be indistinguishable from "not in this build". |
| `blockers` | Strictly a subset of `capabilities`, filtered to the blocking statuses. Never a parallel list with its own ids or wording. |
| `callable` | Exactly the ids where `available === true`. This is the list a tool registry may act on. |
| `probeWarnings` | Probes that could not answer. Affected capabilities report `unknown`; they are never guessed. |
| `correlationId` | One id per snapshot, for correlating a UI complaint with server logs. |

### `CapabilityOut`

| Field | Meaning |
|-------|---------|
| `id`, `displayName`, `subsystem`, `summary` | Identity. `id` is stable API surface. |
| `status` | One of the eleven statuses (§4). |
| `available` | **The only field a caller should gate on.** `true` iff `status ∈ {locally_verified, production_ready, degraded}`. |
| `configured` / `healthy` | Why it is unavailable: configuration missing vs. dependency unhealthy. |
| `readOnly` | `false` means calling it mutates state. |
| `requiresApproval` | `true` means a human must confirm before it runs. Advisory to the caller; the HTTP route does not enforce it. |
| `dependencies` | Capability ids this one needs. Failures propagate (§5). |
| `reasonCode` | Stable string (§6). Branch on this, not on `message`. |
| `message` | Human-facing, secret-free, no stack traces, no absolute user paths. |
| `recommendedAction` | What the operator should do next (§8). |
| `componentIds` | Setup/Source Manager component ids implicated in the blocker. |
| `serviceRef` / `httpRef` | Where the behaviour lives. A test asserts every `serviceRef` resolves to real code. |
| `scope` | `global` or `project`. |
| `details` | Structured extras, scrubbed of secret-shaped keys and values. |
| `lastCheckedAt` | Probe timestamp for this snapshot. |

---

## 4. Status vocabulary

Exactly eleven values, and no others may be introduced without updating the matrix, the
frontend union type, and the vocabulary test:

`not_implemented`, `ui_only`, `backend_only`, `partially_wired`, `mock_verified`,
`locally_verified`, `production_ready`, `blocked`, `degraded`, `not_configured`, `unknown`

Three groupings matter to consumers:

- **Usable** — `locally_verified`, `production_ready`, `degraded`. These set `available: true`.
- **Blocking** — `blocked`, `degraded`, `not_configured`, `unknown`. These appear in `blockers`,
  because each represents something an operator can act on. `degraded` is deliberately in both
  groups: usable now, but the operator should still see why it is not whole.
- **Absent** — `not_implemented`, `ui_only`. Not blockers. There is nothing to fix; the
  behaviour simply does not exist yet, and listing it as a blocker would train operators to
  ignore the blocker list.

A live probe may only **lower** confidence relative to the registry baseline. It can resolve
`unknown`, and it can turn a code-level `backend_only` into `locally_verified` only when the
probe proves the real dependency is present. No probe ever promotes a capability above what the
code has earned.

---

## 5. Dependency propagation

A capability is never advertised as usable while a dependency is unusable. Propagation repeats
until the graph is stable, and the registry is asserted acyclic with no dangling dependency ids.

Two deliberate refinements:

- A capability that already has its own, more specific blocking reason keeps it. `workflows.ready`
  reports `WORKFLOW_MISSING_MODELS` naming the actual component rather than being overwritten
  with a generic "blocked by dependency".
- A propagated `not_configured` stays `not_configured` (missing configuration), and a propagated
  `unknown` stays `unknown` (missing evidence). Collapsing both to `blocked` would tell an
  operator to fix something that may not be broken.

---

## 6. Reason codes

Stable strings; consumers branch on these. Grouped by what they say about the world:

| Group | Codes |
|-------|-------|
| Capability lifecycle | `CAPABILITY_NOT_FOUND`, `CAPABILITY_NOT_IMPLEMENTED`, `CAPABILITY_UI_ONLY`, `CAPABILITY_UNVERIFIED`, `CAPABILITY_PROBE_FAILED` |
| Dependencies | `DEPENDENCY_UNAVAILABLE`, `DEPENDENCY_NOT_CONFIGURED`, `DEPENDENCY_DEGRADED` |
| Models / packs | `MODEL_MISSING`, `MODEL_SOURCE_PENDING`, `MODEL_UNVERIFIED` |
| ComfyUI / workflows | `EXTENSION_MISSING`, `WORKFLOW_NOT_FOUND`, `WORKFLOW_MISSING_MODELS`, `WORKFLOW_MISSING_EXTENSIONS`, `WORKFLOW_READINESS_UNKNOWN`, `WORKFLOW_INVALID_INPUTS` |
| Queue / storage | `QUEUE_UNAVAILABLE`, `QUEUE_BLOCKED`, `STORAGE_NOT_WRITABLE`, `STORAGE_PATH_MISSING` |
| Scope | `PROJECT_NOT_FOUND`, `PROJECT_SCOPE_VIOLATION`, `SCENE_NOT_FOUND`, `VALIDATION_ERROR` |

### Error envelope

Service-layer failures raise `CapabilityError`, which `main.py` translates into the same envelope
the Co-Director gateway already returns, so `studio-web/src/api.ts` surfaces it without
per-route handling:

```json
{
  "detail": {
    "code": "PROJECT_NOT_FOUND",
    "message": "Project abc does not exist.",
    "details": { "projectId": "abc" },
    "recoverable": false,
    "recommendedAction": "open_project"
  }
}
```

HTTP status follows the code: `404` for the not-found family, `403` for scope violations, `400`
for validation, `501` for not-implemented, `503` for unavailable dependencies, `409` for a
blocked queue, `502` for a failed probe, `500` otherwise.

`message` and every string inside `details` pass through secret redaction, and keys that look
like credentials (`token`, `secret`, `password`, `authorization`, `api_key`, `cookie`) are dropped
entirely rather than redacted — a redacted key still tells a reader the credential exists.

---

## 7. ComfyUI health

`GET /api/comfy/health` separates three independent questions that the previous single
try/except conflated:

1. Is the service reachable at the configured URL?
2. Can we read its node catalogue (`/object_info`), so extension gaps are *knowable*?
3. Which catalogued model components are verified on disk?

```json
{
  "reachable": true,
  "status": "ready",
  "baseUrl": "http://127.0.0.1:8188",
  "version": "0.3.27",
  "devices": [{ "name": "…", "type": "cuda", "vramTotalMb": 24564, "vramFreeMb": 21001 }],
  "nodeCatalogAvailable": true,
  "nodeTypeCount": 812,
  "reasonCode": null,
  "message": "ComfyUI is reachable.",
  "recommendedAction": null,
  "models": [{ "componentId": "ltx_checkpoint", "required": true, "present": true, "…": null }],
  "missingModelComponentIds": [],
  "checkedAt": "2026-07-24T22:25:03Z"
}
```

`status` is `ready`, `degraded`, or `unreachable`. Model presence is answered by the Setup
component verifiers — the same source the Setup Wizard and Source Manager use — so the answer
stays consistent and names real component ids instead of prose labels. The previous
implementation hardcoded three model paths under one developer's `%LOCALAPPDATA%`; nothing in the
payload is machine-specific now, and an E2E test asserts no user path leaks.

`/api/health` keeps its shape for existing consumers but is now populated from this payload, so
the legacy endpoint and the structured one cannot disagree.

---

## 8. Recommended actions

`recommendedAction` names what the operator should do, not what the UI should render. The
frontend maps each to a label and, where applicable, a destination:

| Action | Destination |
|--------|-------------|
| `open_source_manager`, `add_source_url` | `/source-manager` |
| `install_comfyui_extensions`, `verify_model_path`, `run_diagnostics` | The Setup Wizard card for the first named component (`#setup-card-{componentId}`), falling back to `/source-manager` |
| `start_comfyui`, `start_ollama`, `select_model`, `use_real_provider`, `choose_data_directory`, `run_verification_render`, `verify_slice`, `open_project`, `request_project_scope`, `list_capabilities`, `list_workflows`, `review_request`, `review_capability`, `none` | Advisory text, no navigation |

**Every action navigates or re-probes. None starts a download.** Installing remains an explicit
per-component decision on a Setup Wizard card, and `POST /api/capabilities/refresh` only drops
the probe cache. An E2E test asserts that clicking Refresh issues no download/install/prepare
`POST`.

---

## 9. Caching and cost

A snapshot is cached for 20 seconds, keyed by `projectId`, behind a lock so concurrent readers
share one probe pass. Blocking probes (storage write test, SQLite inspection, component
verification, Source Manager overview) run in worker threads; ComfyUI and the local model
provider are probed concurrently as async work. Workflow readiness reuses the node catalogue and
component states already gathered rather than re-probing.

A consumer that needs fresher data passes `?refresh=true` or calls the refresh endpoint. UI
surfaces poll at 30s, which the TTL absorbs.

---

## 10. Rules for the Co-Director M2.2 tool registry

The tool registry is **out of scope for this milestone** and is not implemented here. When it is
built, this API is its gate:

1. **Only expose tools whose capability is in `callable`.** A tool whose capability is `blocked`
   must not appear as available; the model should never propose an action guaranteed to fail.
2. **Use `requiresApproval` to decide whether a human must confirm.** Do not infer it from the
   HTTP verb.
3. **Use `readOnly` to decide what may run without a proposal.** A read-only capability can be
   called to answer a question; a write must go through the existing propose/approve path.
4. **Surface `reasonCode` + `recommendedAction` verbatim when refusing.** "I can't queue a render
   because ComfyUI isn't running — start ComfyUI and refresh" is useful; "an error occurred" is not.
5. **Never cache readiness across turns.** Re-read the snapshot; ComfyUI can stop mid-session.
6. **`serviceRef` names the call target.** It is the application service or router function that
   already owns the behaviour — the tool registry must call existing paths, not add new write paths.
