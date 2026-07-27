# M3.0b Final Beta Blockers

| Field | Value |
| --- | --- |
| Tip SHA | `e2f3ae8a9750d44ec37b64361cbede6a95351d3c` |
| Date | 2026-07-26 |
| Gate | Manual User Beta |
| Verdict | **NOT READY FOR MANUAL USER BETA** |

## How to read this list

Blockers are ordered by what a manual beta user would hit first, not by implementation
cost. Severity is `BLOCKER` (beta cannot start), `MAJOR` (beta starts but a core promise
fails), or `MINOR`.

Every item was reproduced against the running API with fixture modes off. Evidence paths
are given so each can be re-checked independently.

---

## B1. The API mints asset IDs for artifacts that do not exist

**Severity: BLOCKER.** This is the single most damaging defect in the build.

`POST /api/codirector/m29/image/generate` and `POST /api/codirector/m29/video/generate`
return HTTP 200 with a populated `assetId`, a populated `versionId`, `fixture: false` and
`status: "draft"`:

```json
{"jobId": "...", "versionId": "fff41161f8474fa886a035d4b6524b68",
 "assetId": "image-fff41161f847", "status": "draft",
 "operation": "generate", "fixture": false, "projectId": "..."}
```

No `Asset` row is created. No file is written. Verified directly: `db.get(Asset, "image-fff41161f847")`
returns `None`, and there is no path to check because there is no row.

The audio path handles the identical situation correctly, returning `providerMissing: true`
and `awaitingProvider: true`. The image and video paths carry **no such signal**. A client,
a test, or a beta user reading the response has no way to distinguish "your shot was
created" from "nothing happened".

This is not a missing feature. It is the API asserting something untrue, and it undermines
every honesty guarantee the rest of the system works hard to maintain.

**Fix:** return `providerMissing: true` and withhold `assetId` when no provider produced an
artifact, matching `AudioService.generate`. Callers should have to opt into a draft
placeholder, not be handed one that looks real.

**Evidence:** `artifacts/functional-audit/m30b-artifact-honesty.json`

---

## B2. The M2.14 Unified Experience workspace cannot render

**Severity: BLOCKER.** The Storyteller and Sound Producer journeys - the centrepiece of
M3.0b - have no reachable user interface.

`CoDirectorShell.tsx:28` gates the workspace on `unifiedExperienceEnabled`, which
`CoDirectorSession.tsx:1404` reads from the provider health payload.
`ProviderHealth.to_dict()` (`studio-api/app/codirector/providers/base.py:52-71`) does not
serialise that field, so it is always `undefined`, so `Boolean(undefined)` is always
`false`, so the shell always renders the plain conversation view instead.

Queried with every flag on, the endpoint returns `visionValidationEnabled: true`,
`productionIntelligenceEnabled: true` and `timelineReferencesEnabled: true`, but omits
`unifiedExperienceEnabled`, `virtualEnvironmentStudioEnabled`, `audioProductionEnabled` and
`directorTimelineEnabled` entirely.

Everything M3.0b exercised was reached through the API. A manual beta user has no API.

**Fix:** add the four missing flags to `ProviderHealth.to_dict()`. This is a four-line
change that unblocks both the M2.14 and M2.13 workspaces.

**Related:** `studio-web/e2e/m214-unified-experience.spec.ts` navigates to `/codirector`
while the registered route (`App.tsx:22`) is `/co-director`, then soft-skips and blames the
feature flag. Both need fixing, and the spec should assert the flag rather than skip on a
missing element.

---

## B3. Mix revise is a silent no-op through the API

**Status: CLOSED for real imported audio; generated audio remains provider-dependent.** The required journey ends "mix revise, export",
and mix revise cannot be performed.

`AudioProcessBody.ops` is typed `list[dict[str, Any]]`. `process_audio_ffmpeg` tests
`str(op).lower() in {"normalize", "loudnorm", "cleanup"}`. A stringified dict never
matches, so the loudnorm branch is skipped, the code falls through to `-c copy`, and the
response still says `status: "processed"`.

Measured on a real 3-second 44,100 Hz WAV:

| Input shape | HTTP API accepts | loudnorm applied | Output sample rate |
| --- | --- | --- | --- |
| `[{"op": "normalize"}]` (matches the contract) | yes | **no** | 44,100 Hz |
| `["normalize"]` (matches the executor) | **no, HTTP 422** | yes | 48,000 Hz |

The two shapes are mutually exclusive, so no request both validates and normalises.

**Fix:** accept both shapes in the executor - read `op.get("op")` when the element is a
dict - or narrow the Pydantic type to `list[str]`. Prefer the former; it is backward
compatible. Add a test that asserts the output sample rate actually changes, because the
current failure mode is a success response.

**Evidence:** `artifacts/functional-audit/m30b-audio-ops-contract.json`,
`m30b-mix-revise.json`

---

## B4. Generated audio cues reach the director timeline for real imported audio

**Severity: BLOCKER for the sound path.**

`audio/generate` writes a cue row with `assetId: null` and `status: "draft"`. Only
`audio/place-cue` writes to the director timeline, and it requires an `assetId`. Generated
cues are therefore stranded: they exist in `m29_audio_cues` and never appear in
`director_json`.

Verified: after generating a music cue, `GET .../scenes/{id}/director` returned
`audio_clips: []` while `GET .../audio/cues` returned the cue.

The timeline side itself is correct. Supplying a real asset and calling `place-cue`
produced a properly formed clip with the right start, length, volume and label. The join
between generation and placement is what is missing.

**Fix:** when a generation job completes and yields an asset, place the cue on the timeline
automatically, or expose an explicit promote step. Either way the user needs a path from
"cue drafted" to "cue on the timeline" that does not require them to know an asset ID.

---

## B5. No generative provider exists for any medium

**Severity: BLOCKER.** Carried forward unchanged from M3.0a.

| Medium | State |
| --- | --- |
| Dialogue / TTS | No provider. `ProviderUnavailable` outside fixture mode. |
| SFX | No provider. |
| Music / score | No provider. |
| Ambience | No provider. |
| Still image | Local ComfyUI ImageGen not installed; `FAL_IMAGE_MODELS` is empty. |
| Video | Local engines not installed; fal has no key. |

Across twelve full situation runs, zero artifacts were produced. The only real media
produced during this milestone was an ffmpeg loudness-normalised WAV derived from a stem
supplied by the test itself - real processing, not generation.

A manual beta user cannot produce a single frame or a single second of audio.

**Fix:** install at least one local engine, or provision a fal key. See B6 for why a fal
key alone is not sufficient.

---

## B6. The fal chain has no first link

**Severity: MAJOR.** Structural, and it will surprise whoever provisions the key.

All four wired fal engines are image-to-video:

| Engine | Model | Mode | Durations | End image |
| --- | --- | --- | --- | --- |
| `fal_seedance` | `bytedance/seedance-2.0/image-to-video` | image_to_video | 4-12s | yes |
| `fal_kling` | `fal-ai/kling-video/v2.5-turbo/pro/image-to-video` | image_to_video | 5, 10s | no |
| `fal_veo` | `fal-ai/veo3.1/image-to-video` | image_to_video | 4, 6, 8s | no |
| `fal_runway` | `fal-ai/runway-gen3/turbo/image-to-video` | image_to_video | 5, 10s | no |

There is no text-to-video engine, and `FAL_IMAGE_MODELS` is empty, so fal cannot produce
the first frame that all four of its own engines require. Adding a fal key unlocks nothing
unless a local image engine is also installed.

**Status:** fal is `NOT_RUN`, not failed. `fal_key_present()` is `False`, `FAL_KEY` and
`FAL_API_KEY` are unset, `ADEPT_M30A_FAL_LIVE` is unset, and the live Playwright test
(`m30a-fal-ai-provider.spec.ts:84`) correctly skipped itself rather than fabricating a
pass.

**Fix:** either wire a fal image family with a verified endpoint id, or document clearly
that a local image engine is a hard prerequisite for any fal use.

---

## B7. Story understanding and emotional intelligence are not connected

**Severity: MAJOR.** The product promise is a Co-Director that understands your story.

`ProductionIntelligenceOrchestrator.orchestrate` calls `run_all` with
`use_provider=False`. `SpecialistRunner` only consults a model when
`use_provider and provider is not None and not _e2e_mode()`, so the LLM branch is
unreachable in every environment.

The measurable consequence: twelve briefs across six genres produced one orchestration
output (digest `ce0b59f48418` after UUID normalisation), and all twelve produced the
identical emotional profile `spark -> tension -> turn` / `intimate` / `personal`.

The system labels this correctly as `honesty: "unavailable"` and
`Heuristic specialist output (E2E/mock path)`, which is to its credit. But a beta user
asked to evaluate "emotional intelligence" would be evaluating a constant.

**Fix:** either bind the specialists to a provider, or surface the scaffold state in the UI
prominently enough that a user is not asked to review generated insight that is a template.

---

## B8. Three declared specialists never run

**Severity: MAJOR.**

`DEFAULT_PIPELINE` declares thirteen stages across twelve specialists. Orchestration
returns ten. Absent: `storyteller`, `sound-producer`, `virtual-production-coordinator`.

The first two are exactly the specialists the M3.0b sound path is built around. They exist
as separate M2.14 endpoints and work there, so the journey is not blocked, but the DAG that
advertises coordinating them does not.

**Fix:** run them in the DAG, or remove them from it so `GET /m211/dag` stops advertising
coordination that does not happen.

---

## B9. Response fields that contradict the response

**Severity: MAJOR.** Three separate instances, grouped because the fix is the same kind of
change.

1. `modelUsed: "gemma"` at the top of the orchestration response, while every specialist
   reports `modelId: null`. No model was consulted.
2. `status: "completed_with_errors"` on all twelve runs, returned under HTTP 200, with no
   error list anywhere in the response. A caller cannot learn what failed.
3. `missingAssets: []` on runs where every required asset was missing.

**Fix:** report `modelUsed: null` when no model ran; include the error detail that
`completed_with_errors` refers to; populate `missingAssets`.

---

## B10. Bible-apply approval path is fixed for the covered proposal

**Status: CLOSED for the covered character proposal.**

`tests/e2e/codirector/production-bible.spec.ts:90` fails with
`Couldn't approve that proposal: Applying this proposal to the Production Bible failed.`
on both the initial run and the retry.

The safety property is almost certainly intact - twelve orchestration runs confirmed
`mayMutateBible: false` is enforced and nothing was written without approval - but the test
that proves it at the browser level is red, so the guarantee is unverified where it counts.

---

## B11. Vision and validation specs failing

**Severity: MAJOR.** Both reproduce on retry, so neither is flake.

- `tests/e2e/codirector/intelligence-storyboard.spec.ts:47` - integrated planning and
  readiness flow keeps visual validation pending.
- `tests/e2e/codirector/vision-storyboard-validation.spec.ts:9` - validation workspace
  appears when flag on and pending deep-link works.

---

## B12. Job cancellation is racy

**Severity: MINOR**, but on a control path that matters.

`tests/e2e/codirector/production-executive-m27.spec.ts:398` ("cancel generic job") failed
its first attempt and passed on retry in 423ms. Cancellation is the first thing a beta user
reaches for when a long render goes wrong, so an intermittent cancel is worse than its
severity rating suggests.

---

## B13. Beat sync is implied but not implemented

**Severity: MINOR** for beta scope, **BLOCKER** for situation 3 specifically.

`AudioPlacement` carries a `syncEvent` field. Nothing reads it. There is no tempo or beat
primitive anywhere in the audio model, so tempo-locked cutting - the defining requirement
of a music video - cannot be expressed.

**Fix:** implement it or remove the field, so the schema stops promising it.

---

## B14. A Playwright test claims coverage it does not provide

**Severity: MINOR.**

`tests/e2e/codirector/production-executive-m27.spec.ts:429`:

```ts
test("restart recovery documented in pytest", async () => {
  test.skip(true, "Restart recovery covered by pytest crash recovery test");
});
```

It asserts nothing, and until this milestone the pytest coverage it points at did not
exercise queue restart recovery either. That gap is now closed (see below), but the stub
should still be given a real assertion or deleted.

---

## Resolved during M3.0b

### R1. Job queue restart recovery - FIXED

M3.0a recorded `RST = FAIL` across queue-backed platforms: the queue did not recover
interrupted work after a restart. This is implemented and tested.

`JobQueue.recover_interrupted()` (`studio-api/app/queue_worker.py`) runs from the FastAPI
lifespan (`studio-api/app/main.py`) before the worker starts, and:

- re-enqueues recent `queued` jobs so the work resumes;
- marks `running` jobs `failed` with stage `interrupted`, with a message stating the work
  was interrupted by a restart rather than that it failed on its own merits - a
  provider-side render held by a dead process cannot be resumed by a new one, and saying so
  is more useful than a bare failure;
- marks `queued` jobs older than `STUDIO_JOB_RECOVERY_MAX_AGE_HOURS` as interrupted rather
  than starting stale work;
- leaves `done`, `failed` and `cancelled` untouched;
- records each action in the job's history for audit.

`studio-api/tests/test_job_queue_recovery.py` adds seven tests, all passing. Verified not to
affect the rest of the suite: the twenty pre-existing pytest failures are identical with and
without this file present.

---

## Test state at the gate

| Suite | Result |
| --- | --- |
| Backend pytest (full) | 539 passed, 20 failed, 6 skipped (565 total, 11m34s) |
| Playwright (focused, 8 specs) | 23 passed, 3 failed, 1 flaky, 4 skipped (31 total, 2.6m) |
| Job queue recovery (new) | 7 passed |

The twenty pytest failures are pre-existing and unrelated to this milestone's changes.
Eighteen reproduce when run as an isolated group; two
(`test_phase0_baseline.py::test_sqlite_initialization_is_isolated` and
`test_production_executive.py::test_queue_order_by_priority`) pass in isolation and fail in
the full run, so they are order-dependent pollution from elsewhere in the suite. None
involve the queue recovery code.

## Constraints honoured

- No commit was made.
- Provider Manifest sha256 is unchanged:
  `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` (39,547 bytes).
- No live fal or local generative success is claimed anywhere in these documents.
- No claim of a full-green or zero-mock state is made; conditions plainly remain.

## Minimum bar for Manual User Beta

Beta can start when a user can complete one situation end to end and keep the result.
Concretely:

1. B5 - at least one generative provider installed or provisioned.
2. B1 - no phantom asset IDs.
3. B2 - the M2.14 workspace renders.
4. B3 and B4 - the sound path reaches the timeline and can be re-mixed.
5. B10 - Bible-apply green, so the "model never writes directly" promise is proven.

B7 (scaffolded intelligence) does not have to be solved before beta, but it must be
disclosed in the UI. Asking a beta user to rate emotional intelligence that is a hard-coded
constant would waste their time and damage trust in the feedback that comes back.

---

## Remediation - B1, B2 and B3 fixed in the working tree

| Field | Value |
| --- | --- |
| Date | 2026-07-26 |
| Base | tip `e2f3ae8a9750d44ec37b64361cbede6a95351d3c`; the fixes are uncommitted working-tree changes on top of that tip |
| Commits made | None |
| Provider Manifest sha256 | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` (UNCHANGED, 39,547 bytes) |

Three of the fourteen blockers are fixed. Nothing else in this list changed. B4 through B14
stand exactly as written, no generative provider was installed or provisioned, and no live
fal or local generative success is claimed anywhere below.

### B1 - FIXED. The generate endpoints no longer mint asset ids

`ImageService.generate` and `VideoService.generate`
(`studio-api/app/codirector/m29/image/service.py`, `.../video/service.py`) no longer create a
draft `m29_asset_versions` row on the production path, and therefore no longer have an asset
id to return. The queued response is now `assetId: null`, `versionId: null`,
`status: "queued"`, `fixture: false`, plus `providerMissing` computed from real provider
reachability. When no provider is reachable the response also carries `awaitingProvider: true`
and a message saying the job will report Blocked and that no asset was created.

Provider reachability is decided by two new helpers in
`studio-api/app/codirector/m29/providers.py`: `image_provider_available()` (ComfyUI) and
`video_provider_available(db)` (ComfyUI or a fal key), which mirror the checks `run_imagegen`
and `run_video` already make before they will do any work.

HTTP status stays 200, matching `AudioService.generate` and `FramesService.generate`. The
blocker was never the status code - it was a response that could not be distinguished from a
real creation. A queued-and-blocked job is now stated as such in the body rather than implied
by a code. Callers should read `providerMissing` and `assetId`, not the status line.

The fixture path is untouched and still env-gated on `ADEPT_M29_FIXTURE_MODE` / `STUDIO_E2E`:
fixture runs still return a real fixture asset id and a real version row, and still label
themselves `fixture: true`.

### B2 - FIXED. Provider health serialises the four missing flags

`ProviderHealthResult` (`studio-api/app/codirector/providers/base.py`) gained four fields -
`unified_experience_enabled`, `virtual_environment_studio_enabled`, `audio_production_enabled`
and `director_timeline_enabled` - and `to_dict()` now emits `unifiedExperienceEnabled`,
`virtualEnvironmentStudioEnabled`, `audioProductionEnabled` and `directorTimelineEnabled`
alongside the flags it already published. `codirector.service.get_health()` populates them
from `feature_flags.codirector_unified_experience_v1`,
`virtual_environment_studio_v1`, `audio_production_v1` and `director_timeline_v1`.

`CoDirectorSession.tsx:1404` already reads `Boolean(providerHealth?.unifiedExperienceEnabled)`
and `CoDirectorShell.tsx:28` already gates the workspace on it, so no component change was
needed; the value simply stopped being `undefined`. The response type in
`studio-web/src/api.ts` gained the two flag names it was still missing.

The route mismatch noted under "Related" (`/codirector` versus `/co-director` in
`studio-web/e2e/m214-unified-experience.spec.ts`) is **not** fixed and remains open.

### B3 - FIXED. Mix revise does real work through the documented shape

`process_audio_ffmpeg` no longer stringifies the op. Two new helpers in
`studio-api/app/codirector/m29/providers.py`, `normalize_audio_ops` and `validate_audio_ops`,
canonicalise both shapes - `{"op": "normalize"}` and `"normalize"` - to a lowercase op name,
so the contract shape and the executor shape now agree. `AudioProcessBody.ops` is typed
`list[dict[str, Any] | str]` with a validator, so a request naming an op the executor cannot
perform is rejected with HTTP 422 instead of being accepted and quietly ignored.

The executor result now reports what it did: `appliedOps`, `loudnormApplied` and, when
loudnorm ran, `sampleRate: 48000`. `AudioService.process` echoes `appliedOps` on the queued
response so a caller can see the interpretation before the job runs.

Measured again on a real 3-second 44,100 Hz WAV, with ffmpeg on PATH:

| Input shape | HTTP API accepts | loudnorm applied | Output sample rate |
| --- | --- | --- | --- |
| `[{"op": "normalize"}]` | yes | **yes** | **48,000 Hz** |
| `["normalize"]` | **yes** | yes | 48,000 Hz |
| `[{"op": "reverse-time"}]` | no, HTTP 422 | n/a | n/a |

### Tests added

`studio-api/tests/test_m30b_beta_blockers.py` - 12 tests, all passing:

- image and video generate with no provider return `providerMissing: true`, no `assetId`, no
  `versionId`, and create no `m29_asset_versions` row;
- image generate with a provider reachable still withholds `assetId`, because the artifact
  does not exist yet at the moment the response is written;
- the same two endpoints over HTTP return no asset id and no `Asset` row is resolvable;
- fixture mode still produces a recorded asset, so the honesty fix did not delete the CI path;
- `ProviderHealthResult.to_dict()` carries the four flags, and `get_health()` reads
  `unifiedExperienceEnabled` from the feature flag;
- audio ops accept both shapes, reject unknown ops with `ValueError` and HTTP 422, and the
  dict shape reaches the loudnorm branch;
- with ffmpeg present, the dict shape actually changes the output file from 44,100 Hz to
  48,000 Hz - the assertion the old failure mode would have passed silently.

### Test state after the fix

| Suite | Result |
| --- | --- |
| `test_m30b_beta_blockers.py` (new) | 12 passed |
| `test_m29_production_suite.py` | all passed |
| `test_m214_unified_experience.py` | all passed |
| `test_codirector_provider.py` | all passed |
| `test_production_executive.py` | 20 passed, 5 skipped |
| `test_m210b_execution_lock_guards.py`, `test_m2101_*`, `test_m2102_*`, `test_m212_*`, `test_m213_*` | all passed |
| `test_closed_loop_m2_6_1.py` | 1 failed (`test_migration_clean_install_has_m006_m007`) |
| `test_codirector_tools.py` | 2 failed (capability `not_configured` cases) |

Those three failures are on the pre-existing list of twenty recorded in
`artifacts/functional-audit/m30b-pytest.txt` and fail identically without these changes.

### What did not change

- No generative provider was installed or provisioned. B5 stands.
- Generated audio cues still do not reach the director timeline. B4 stands.
- Bible-apply, the vision and validation specs, the racy cancel and the rest of B6-B14 stand.
- The gate verdict is still **NOT READY FOR MANUAL USER BETA**. B1-B3 were the honesty
  blockers; B4 and B10 are functional blockers on the minimum bar and are still open.


## Post-fix status -  2026-07-27

**B1 CLOSED:** production image/video generation withholds phantom asset IDs.
**B2 CLOSED:** provider health serializes the unified-workspace flags.
**B3 CLOSED:** documented audio operation shapes reach real ffmpeg normalization.
**B4 CLOSED for real imported audio:** import/promote/gain reaches the public Director timeline;
generated audio remains provider-dependent.
**B10 FIXED for the covered character proposal:** approve persists Bible version 2 and reject
preserves version 1.

**B5 REDUCED, not eliminated:** local Z-Image is end-to-end proven; the fal video is reused and
registered, not produced by a new Studio queue job. One same-situation retained user journey is
still missing. B6-B9 and B11-B14 remain as previously described: incomplete provider/model
coverage, scaffolded situation intelligence, missing declared specialists, contradictory response
fields, vision/validation failures, cancellation race, schema-only beat sync, and the skipped
restart browser assertion.

The gate remains **NOT READY FOR UNRESTRICTED MANUAL USER BETA**. Tally:
**0 EXECUTED / 12 PARTIAL / 0 FAILED / 0 NOT_RUN**. No paid fal job was resubmitted.
