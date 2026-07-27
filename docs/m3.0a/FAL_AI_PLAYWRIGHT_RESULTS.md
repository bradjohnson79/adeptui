# M3.0a - fal.ai Playwright Results

| Field | Value |
|-------|-------|
| Tip SHA | e2f3ae8a9750d44ec37b64361cbede6a95351d3c |
| Date | 2026-07-26 |
| Suite | `tests/e2e/m30a/m30a-fal-ai-provider.spec.ts` |
| Structural block | 4 tests, **4 passed** |
| Live block | 1 test, **skipped (NOT_RUN)** - gated on `ADEPT_M30A_FAL_LIVE=1` plus a real key |
| Run | Full default suite, `npx playwright test`, 2026-07-26, 6.6 min |

---

## 1. Results

| # | Test | Tag | Result | What it actually proves |
|---|------|-----|--------|--------------------------|
| 1 | rejects a key fal.ai does not accept and stores nothing | @critical | PASS | `PUT /api/fal/key` probes fal before persisting. A key fal refuses is not written to the secret store, and the endpoint returns the rejection rather than a cheerful 200. |
| 2 | credential endpoints never return key material | @critical | PASS | `GET /api/fal/key`, `GET /api/fal/status` and the Co-Director tool return state, never the secret. The mask and fingerprint that the settings UI receives are not the key and cannot be reversed into it. |
| 3 | model catalogue declares media types and only wired endpoints | @critical | PASS | Every entry in `fal_catalog` carries a `mediaType` and points at an endpoint the queue worker can actually submit to. `FAL_IMAGE_MODELS` is empty, and the test asserts that the catalogue admits this rather than advertising an image engine that does not exist. |
| 4 | no page in the app ships credential material | @critical | PASS | Crawls the built pages for the key pattern. Nothing leaks into the bundle or into rendered HTML. |
| 5 | live: a real key verifies and unlocks cloud engines | @critical | **SKIPPED** | Nothing. See section 2. |

Reporter line for the skip, verbatim from the run log:

```
-  85 [chromium] tests/e2e/m30a/m30a-fal-ai-provider.spec.ts:84:7
   M3.0a fal.ai provider @critical > live: a real key verifies and unlocks cloud engines
```

The four structural tests were re-run on their own after the Phase 3 remediations landed and
passed again (subset run, 2026-07-26, 3.7 min).

## 2. What the skip costs

The structural block is a real result and it is worth having: it proves the integration
refuses bad credentials, keeps good ones out of every response body, and does not advertise
engines it cannot reach. It is also, in isolation, easy to over-read.

| Question | Structural block answers it? |
|----------|------------------------------|
| Does the app refuse a key fal rejects? | Yes |
| Does the app leak the key anywhere? | Yes - it does not |
| Is the catalogue honest about what is wired? | Yes |
| Does fal **accept** a valid key? | **No** |
| Does a fal job return a real `request_id`? | **No** |
| Does a fal render produce a playable artifact? | **No** |
| Does a mid-render fal failure recover cleanly? | **No** |

Every one of the four unanswered questions needs a real key and, for the last two, real
credits. That is why the live block exists and why it is gated rather than deleted.

### 2.1 Answered elsewhere since this run (2026-07-27)

The live Playwright block is still SKIPPED - nothing in this table changed. Three of those
four questions were answered outside Playwright, by the budgeted script proof recorded in
[FAL_AI_REAL_JOB_RESULTS.md](./FAL_AI_REAL_JOB_RESULTS.md):

| Question | Answered by | Result |
|----------|-------------|--------|
| Does fal accept a valid key? | `scripts/m30a_fal_budgeted_live_proof.py` | Yes - `validate_fal_key` -> `verified` |
| Does a fal job return a real `request_id`? | Same script | Yes - `019fa1fc-e05f-7d80-9908-e6d0c3e8d4fc` |
| Does a fal render produce a playable artifact? | Same script | Yes - 667,974-byte MP4, 4.04 s, 864x496 |
| Does a mid-render fal failure recover cleanly? | Nothing yet | Still unanswered |

Keeping the distinction sharp: that proof is a **script-level** run against the fal helpers,
not a browser-level run. It says nothing about the UI flow this suite covers, and the live
Playwright test remains the only thing that would prove the settings screen and the API
endpoints behave correctly with a key fal accepts.

## 3. Reproducing the live block

```
set ADEPT_M30A_FAL_LIVE=1
set ADEPT_M30A_FAL_KEY=<a real fal.ai key>
npx playwright test tests/e2e/m30a
```

The gate is checked inside the spec, so the command is identical with or without the
variables; only the skip disappears. `scripts/e2e-start.mjs` passes both variables through to
the API process, so no separate server configuration is required.

Validation itself costs nothing: it issues one authenticated GET against a queue-status URL
with a random request id, which fal answers without creating a job. Only an actual render
spends credits, and no test in this suite submits one.

## 4. Relationship to the other M3.0a fal documents

| Document | Scope |
|----------|-------|
| `FAL_AI_INTEGRATION_AUDIT.md` | How the integration is built |
| `FAL_AI_CAPABILITY_MATRIX.md` | Which engines exist and which are wired |
| `FAL_AI_CREDENTIAL_SECURITY.md` | How the key is stored, masked and redacted |
| `FAL_AI_REAL_JOB_RESULTS.md` | Live job attempts - one VERIFIED Seedance text-to-video render (2026-07-27) |
| This file | What the browser-level suite executed and what it proved |
