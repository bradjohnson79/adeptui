# M3.0a — fal.ai Integration Audit (state after Phase 1 + Phase 2 code)

| Field | Value |
|-------|-------|
| Scope | Every production-reachable fal.ai surface in `studio-api/` and `studio-web/` |
| Date | 2026-07-26 |
| Related | `MOCK_AND_SCAFFOLD_AUDIT.md` (Phase 0), `FAL_AI_CAPABILITY_MATRIX.md`, `FAL_AI_CREDENTIAL_SECURITY.md` |
| Model | BYOK — the user supplies their own fal.ai key; Adept never ships or proxies one |

---

## 1. Surfaces

| Surface | File | What it does now |
|---------|------|------------------|
| Credential store | `studio-api/app/secrets_store.py` | Fernet-encrypted key at rest, plus a fingerprint-bound verification record |
| Live validation | `studio-api/app/fal_client.py:validate_fal_key` | Authorized probe against a real fal endpoint; classifies verified / invalid / unverified |
| Save + verify | `studio-api/app/routers/api.py` `PUT /api/fal/key` | Probes **before** storing; a key fal rejects is refused with HTTP 400 and never written |
| Re-verify | `studio-api/app/routers/api.py` `POST /api/fal/key/validate` | Re-probes the stored key and refreshes its state |
| Status | `GET /api/fal/key` | `configured`, `hint`, `fingerprint`, `state`, `verified`, `verifiedAt`, `message` — never the key |
| Usage | `GET /api/fal/usage` | Credit balance / spend via fal Platform APIs (admin-scoped keys only) |
| Catalogue | `studio-api/app/fal_catalog.py` | Four video engines, each with an explicit `media_type` |
| Render path | `studio-api/app/queue_worker.py` | Submits to fal, persists the queue `request_id`, fails closed with no key |
| Diagnostics | `studio-api/app/setup/diagnostics.py` | Setup component `fal_key` reports verified / invalid / unverified / missing |
| Settings UI | `studio-web/src/components/ProjectSettings.tsx` | Save & verify, re-verify, clear; shows the real state and any fal message |
| Co-Director | `tools/handlers/system.py:get_cloud_render_status` | Read tool: credential state + usable engines, with no credential material |

---

## 2. What changed in M3.0a

### 2.1 Validation is real, not assumed

Before, `PUT /api/fal/key` stored whatever it was given and reported `configured: true`. A
typo produced a green-looking integration that only failed at render time, minutes later,
inside a queue worker.

Now the endpoint runs an authorized probe first:

```
GET https://queue.fal.run/fal-ai/veo3.1/requests/{random-uuid}/status
Authorization: Key <candidate key>
```

The request id is random and does not exist, so no job is created and nothing is billed.
The response separates the two questions that matter:

| fal response | Meaning | Recorded state |
|--------------|---------|----------------|
| `401` / `403` | fal rejected the credential | `invalid` — request refused with HTTP 400, key not stored |
| `404` (or any other <500) | The credential authenticated; the request id simply does not exist | `verified` |
| `5xx` or transport failure | fal could not answer | `unverified` — key is stored, state says so plainly |

The third row is the honest case that a boolean `configured` flag cannot express: we do not
claim a key works when fal never told us, and we do not throw away a good key because fal
had an outage.

### 2.2 Verification is bound to the key

The verification record stores the key's fingerprint. Replacing the key — through the API or
by any other write to the secret — makes the previous record stop matching, so the status
falls back to `unverified` rather than describing a secret that is no longer there.

### 2.3 Renders are traceable

`run_fal_model` now reports the fal queue `request_id` as soon as fal issues one, and the
queue worker writes it to the job's `history_json` as `falRequestId` (with `falModelId`).
A user asking "what happened to my render?" can be answered against the fal dashboard
without a schema migration.

### 2.4 Failure stays closed

No fal path has a mock or fixture fallback. Without a key, `_build_and_run_fal_scene` and the
txt2vid path raise; a rejected key surfaces as `FalAuthError` with a message that points at
Project Settings rather than a generic HTTP dump.

---

## 3. Honest gaps

| Gap | Why it is a gap, not a bug |
|-----|---------------------------|
| No fal **image** models | No fal image endpoint id exists anywhere in this repository. Adding Seedream / GPT Image / Nano Banana from memory would ship endpoints the queue cannot run. Still images go through local ComfyUI ImageGen. `FAL_IMAGE_MODELS` is an empty, documented slot. |
| Usage requires an admin-scoped key | `GET /api/fal/usage` calls fal Platform billing APIs. A render-only key authenticates for renders and is rejected for billing, so usage may be unavailable for a key that is genuinely `verified`. Validation deliberately does not use the billing endpoint for this reason. |
| Verification is a point-in-time check | A key revoked at fal after verification still reads `verified` until the next probe or the next failing render. The Settings panel exposes "Re-verify" for this. |
| No per-project keys | The key is global to the installation, matching the existing secrets store. |

---

## 4. Verification

| Check | Where |
|-------|-------|
| Rejected key refused, nothing stored | `studio-api/tests/test_fal_credentials.py::test_put_key_rejects_a_key_fal_refuses` |
| Unreachable fal reads as unverified | `::test_probe_treats_unreachable_service_as_unverified` |
| Status/validate never echo the key | `::test_status_never_returns_the_key` |
| Replaced key drops the old badge | `::test_replacing_the_key_invalidates_the_previous_verification` |
| Diagnostics reflects each state | `::test_diagnostics_reports_the_verified_state` |
| `request_id` persisted on the job | `::test_queue_worker_records_the_fal_request_id` |
| Browser-level redaction + catalogue shape | `tests/e2e/m30a/m30a-fal-ai-provider.spec.ts` |
| Live key round-trip | Same spec, gated on `ADEPT_M30A_FAL_LIVE=1` |
