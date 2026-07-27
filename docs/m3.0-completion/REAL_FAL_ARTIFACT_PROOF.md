# M3.0 Completion - Phase 6: Real fal Artifact, Registered Without Re-spending

**Verdict: VERIFIED, and nothing was re-submitted.** The Seedance video that the M3.0a budgeted
live proof already paid for is now a real `Asset` row in a real project, carrying the fal
provenance that produced it. Separately, a fal key that only lives in `.env` is now promoted into
the encrypted secret store at startup, which is what the render worker actually reads.

| Field | Value |
|-------|-------|
| Blocker | **B5 (fal half)** - "no hosted provider path proven end-to-end through API Asset/queue" |
| fal jobs submitted in this phase | **0** |
| Artifact reused | `artifacts/m30a-fal/seedance_t2v_4s_480p.mp4` |
| Plan file | Not edited |
| Commit | None |
| Keys printed | None. No key, key prefix, or key fingerprint appears in this document, the script output, or any log line added here. |

---

## 1. The artifact being reused

Produced by `scripts/m30a_fal_budgeted_live_proof.py` in the earlier M3.0a phase - one submit, one
render, then stop.

| Field | Value |
|-------|-------|
| Engine / model | `fal_seedance` - `bytedance/seedance-2.0/text-to-video` |
| fal `request_id` | `019fa1fc-e05f-7d80-9908-e6d0c3e8d4fc` |
| Duration / resolution | 4 s, 480p, 16:9, seed 42 |
| File | `artifacts/m30a-fal/seedance_t2v_4s_480p.mp4` |
| Size | 667,974 bytes |
| sha256 | `6f58aeda75780eafef026cfb05ea2450ec6936010fa2d7bdada8913b0b3941a3` |
| Rendered | `2026-07-27T05:15:50Z` (wall clock 217.6 s) |
| Recorded outcome | `verified` |

---

## 2. Item 2 - registering it as a project Asset

**Script:** `scripts/m30_register_fal_artifact.py`

It re-computes the sha256 of the file and compares it to the digest recorded next to the request id
before writing anything. A file that no longer matches its proof is refused (exit 3) rather than
registered under provenance it does not belong to. It also refuses a summary whose `outcome` is not
`verified`, and it is idempotent: a second run finds the existing registration by `request_id` and
does nothing unless `--force` is passed.

Actual run against the operator's database:

```
$ python scripts/m30_register_fal_artifact.py --project-id 098744a3-9d6b-4c42-b873-bf817970b07c
[m30-fal-register] registered asset 5da0a56a-d60c-4469-ab92-3bdf68e8f879 in project 098744a3-9d6b-4c42-b873-bf817970b07c
[m30-fal-register]   request_id 019fa1fc-e05f-7d80-9908-e6d0c3e8d4fc
[m30-fal-register]   file       data/assets/098744a3-9d6b-4c42-b873-bf817970b07c/5da0a56a-d60c-4469-ab92-3bdf68e8f879.mp4
[m30-fal-register]   no fal job was submitted

$ python scripts/m30_register_fal_artifact.py --project-id 098744a3-9d6b-4c42-b873-bf817970b07c
[m30-fal-register] already registered as asset 5da0a56a-d60c-4469-ab92-3bdf68e8f879 (use --force to add another copy)
```

| Row | Value |
|-----|-------|
| `assets.id` | `5da0a56a-d60c-4469-ab92-3bdf68e8f879` |
| `assets.project_id` | `098744a3-9d6b-4c42-b873-bf817970b07c` - "M3.0 Local Artifact Proof" |
| `assets.kind` / `tag` | `video` / `m30a-fal-live-proof` |
| `assets.path` | `data/assets/098744a3-.../5da0a56a-....mp4` (copied, so the artifact does not depend on `artifacts/` staying put) |
| `assets.labels_json` | `["fal", "seedance", "live-proof"]` |

`assets.prompt_meta_json` carries the provenance:

```json
{
  "source": "fal.ai live render (M3.0a budgeted proof)",
  "reused_existing_artifact": true,
  "resubmitted": false,
  "provider": "fal",
  "engine": "fal_seedance",
  "model_id": "bytedance/seedance-2.0/text-to-video",
  "request_id": "019fa1fc-e05f-7d80-9908-e6d0c3e8d4fc",
  "seed": 42,
  "duration_sec": 4,
  "resolution": "480p",
  "sha256": "6f58aeda75780eafef026cfb05ea2450ec6936010fa2d7bdada8913b0b3941a3",
  "rendered_utc": "2026-07-27T05:15:50.453279Z",
  "registered_utc": "<run time>"
}
```

`resubmitted: false` is recorded on the row itself, so a later reader cannot mistake this asset for
a fresh render.

---

## 3. Item 1 - the `.env` to secret-store bridge

**Module:** `studio-api/app/fal_env_bridge.py`, awaited from the lifespan in
`studio-api/app/main.py` (after the Source Manager migration, before the job queue starts).

### The contradiction it removes

| Reader | Where it looked for the key | Result with a `.env`-only key |
|--------|------------------------------|-------------------------------|
| `m29.providers.fal_key_present` | secret store, then `FAL_KEY` / `FAL_API_KEY` | "key present" |
| `queue_worker` fal render | secret store **only** | "fal.ai API key not configured" - the job fails |

So diagnostics said ready and the render said not configured. The bridge makes the second reader
see what the first one already saw.

### Behaviour

1. If a key is already stored, stop. The stored key always wins; the environment never silently
   replaces it.
2. Otherwise look for `FAL_API_KEY`, then `FAL_KEY`, in the process environment, then in `.env`
   (cwd, `studio-api/`, repo root). `.env` is read with a minimal parser that handles quotes and
   `export ` prefixes - deliberately **without** the `STUDIO_` prefix that `config.Settings`
   applies, since the fal convention is a bare name.
3. Probe it with `fal_client.validate_fal_key`. That probe hits a real endpoint with a random
   request id: 401/403 means the key is bad, 404 means it authenticated. No job is created and
   nothing is billed.
4. Act on the probe:

| Probe | Action |
|-------|--------|
| accepted | `set_secret("fal_api_key")` + verification record marked verified |
| rejected (401/403) | **nothing stored** |
| unreachable (network/5xx) | stored, but the verification record is marked unverified so the UI badge stays honest |

A `.env`-only key is also exported into `os.environ` under both names, so the readiness probes that
read the environment agree with the store.

Nothing logs the key. The report the function returns contains at most a fingerprint from
`secrets_store.secret_fingerprint`, and `set_secret_verification` already strips `key`/`api_key`
from any detail dict.

### Off switch

`STUDIO_FAL_ENV_BRIDGE=0` disables the startup hook. It is set to `0` in
`studio-api/tests/conftest.py` and in `scripts/e2e-start.mjs`, because otherwise every test or E2E
boot on a developer machine with a real `.env` would make a live network call to fal.

---

## 4. Tests

`studio-api/tests/test_m30_fal_env_bridge.py` (9 tests):

| Test | What it pins |
|------|--------------|
| `test_env_key_is_stored_after_a_successful_probe` | Accepted key is stored and the status reads `verified` |
| `test_rejected_key_is_not_stored` | 401 path stores nothing |
| `test_unreachable_fal_stores_the_key_but_flags_it_unverified` | Offline path stores but does not claim verification |
| `test_existing_stored_key_wins_and_is_never_probed` | No probe at all when a key is already configured |
| `test_missing_key_is_reported_without_touching_the_store` | `no-key` report, store untouched |
| `test_key_is_read_from_dotenv_without_a_studio_prefix` | `.env` with `export FAL_KEY='...'` works, and the value is exported to `os.environ` |
| `test_reports_and_verification_records_never_carry_the_key` | The key string appears in no report, no verification record, and no file in the secrets dir |
| `test_startup_hook_is_disabled_by_the_env_switch` | `STUDIO_FAL_ENV_BRIDGE=0` short-circuits before any probe |
| `test_startup_hook_swallows_failures` | A throwing probe cannot break API startup |

`studio-api/tests/test_m30_fal_artifact_register.py` (7 tests):

| Test | What it pins |
|------|--------------|
| `test_registers_the_artifact_with_fal_provenance` | Asset row, copied bytes, `request_id` / `model_id` / `sha256` / `resubmitted: false` |
| `test_second_run_is_a_no_op` | Idempotent |
| `test_force_registers_another_copy` | `--force` is the only way to duplicate |
| `test_digest_mismatch_is_refused` | Tampered bytes -> exit 3, no row |
| `test_unknown_project_is_refused` | exit 2 |
| `test_unverified_summary_is_refused` | `outcome != verified` aborts |
| `test_the_real_artifact_still_matches_its_recorded_digest` | Re-hashes the actual `artifacts/m30a-fal/` file against `live_proof_summary.json`; skips if the artifact is absent |

**Result: 16 passed** (`python -m pytest tests/test_m30_fal_env_bridge.py tests/test_m30_fal_artifact_register.py -q`).

All of the bridge tests fake the probe. **No test in this phase makes a network call to fal, and no
test uses a real key.**

---

## 5. Honest limitations

1. **No new fal render was performed, by instruction.** This phase proves that an artifact fal
   produced can live inside the app with its provenance intact - it does not re-prove the
   submit-to-download path. That was proven once, in M3.0a, and is recorded in
   `artifacts/m30a-fal/live_proof_summary.json`.
2. **The registered asset has no `Job` row and no queue history.** It was not produced through the
   Studio queue in this phase, so the job-side lineage that `REAL_LOCAL_ARTIFACT_PROOF.md` shows for
   the local ComfyUI render has no counterpart here. The provenance lives on the asset row instead.
   Closing that gap requires an actual fal job, i.e. spending money.
3. **The bridge was not exercised against a live fal endpoint here.** Its probe outcomes are covered
   by faked responses; running it for real would require using the operator's key.
4. **`AssetVersion` lineage was not written** for the registered artifact - it is a plain `Asset`
   row plus provenance JSON.
