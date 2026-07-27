# M3.0a - fal.ai Real Job Results

| Field | Value |
|-------|-------|
| Tip SHA | `e2f3ae8a9750d44ec37b64361cbede6a95351d3c` |
| Date | 2026-07-27 (UTC) |
| Run | Budgeted live proof, `scripts/m30a_fal_budgeted_live_proof.py` |
| Key source | `FAL_API_KEY` in repo-root `.env` (never printed, logged or committed) |
| Result | **VERIFIED** - one fal.ai job submitted, one playable artifact downloaded |

---

## 1. Status

**VERIFIED for text-to-video.** One Seedance 2.0 job was submitted to fal.ai on 2026-07-27
and returned a real MP4, which is now on disk. Credits were spent for exactly one render;
the script hard-stops after a single submit and refuses to re-run once a summary with
`submitted: true` exists.

This supersedes the previous NOT_RUN state of this document. The earlier statement - that
the integration was known to reject bad keys but not known to succeed with good ones - no
longer holds for the acceptance and render paths. It still holds for image-to-video,
failure recovery, and the admin-scoped usage endpoint; see section 5.

## 2. The job

| Field | Value |
|-------|-------|
| Engine (app id) | `fal_seedance` |
| fal endpoint | `bytedance/seedance-2.0/text-to-video` |
| Request id | `019fa1fc-e05f-7d80-9908-e6d0c3e8d4fc` |
| Arguments | `resolution=480p`, `duration=4`, `aspect_ratio=16:9`, `generate_audio=false`, `seed=42` |
| Prompt | Cinematic slow dolly-in across an empty film studio at dawn (short test prompt) |
| Queue-to-result wall clock | 217.6 s |
| Terminal status | `COMPLETED` |
| Result payload keys | `video`, `seed` |

`build_fal_arguments(engine="fal_seedance", image_url=None, ...)` resolved to the
text-to-video endpoint by design: the Seedance catalogue entry is image-to-video, and with
no start image the builder falls back to `bytedance/seedance-2.0/text-to-video`. That
fallback branch is therefore now proven against live fal, and the I2V endpoint itself is
not.

## 3. The artifact

| Field | Value |
|-------|-------|
| Path | `artifacts/m30a-fal/seedance_t2v_4s_480p.mp4` |
| Size | 667,974 bytes |
| SHA-256 | `6f58aeda75780eafef026cfb05ea2450ec6936010fa2d7bdada8913b0b3941a3` |
| Container | ISO MP4 (`ftypisom`) |
| Duration (from `mvhd`) | 4.04 s |
| Track dimensions (from `tkhd`) | 864 x 496 |
| Audio track | None - matches `generate_audio=false` |

The file is non-empty, parses as a real MP4, and its header fields agree with what was
requested. That is what "VERIFIED" means here. Nobody has sat and watched it for aesthetic
quality, and this document does not claim they have.

Machine-readable summary (no secrets): `artifacts/m30a-fal/live_proof_summary.json`.

## 4. Jobs table

| Job | Engine | fal endpoint | Submitted | Request id | Artifact | Outcome |
|-----|--------|--------------|-----------|------------|----------|---------|
| 1 | `fal_seedance` | `bytedance/seedance-2.0/text-to-video` | 2026-07-27T05:12Z | `019fa1fc-e05f-7d80-9908-e6d0c3e8d4fc` | `artifacts/m30a-fal/seedance_t2v_4s_480p.mp4` (668 KB) | **VERIFIED** |

## 5. What this proves and what it still does not

| Question | Answered? | By what |
|----------|-----------|---------|
| Does fal **accept** a good key? | **Yes** | `validate_fal_key` returned `verified` (HTTP 404 on a random request id, which only an authenticated caller receives) |
| Does a fal render produce a real video file? | **Yes** | Job 1 above; 668 KB MP4 on disk |
| Is the `request_id` a real fal request id? | **Yes** | `019fa1fc-…` came from the queue submit response and drove the status polling |
| Does the API refuse a key fal rejects? | Yes | `test_put_key_rejects_a_key_fal_refuses`; Playwright rejection test |
| Does any endpoint leak the key? | Yes - no | `test_status_never_returns_the_key`; Playwright credential-redaction tests |
| Does the **image-to-video** endpoint work live? | **No** | Needs a start image; not submitted (one-job budget) |
| Does a fal failure recover cleanly? | **No** | Requires a live failure; this job succeeded |
| Does `GET /api/fal/usage` work? | **No** | Billing and usage returned "needs ADMIN-scoped key" for this credential |
| Did the **queue worker + Asset row** path run end to end? | **No** | See below |

The proof script calls `build_fal_arguments` -> `run_fal_model` -> `extract_video_url` ->
`download_url`, which is the exact helper chain and call order `queue_worker.py` uses for a
fal render. What it does not exercise is the surrounding job-row lifecycle: enqueue,
progress persistence, `falRequestId` write-back, and `Asset` creation. Those remain covered
only by tests, not by a live render.

## 6. Cost and budget controls

Usage and billing endpoints rejected this key as non-admin, so fal did not report a balance
before or after, and this document does not invent a dollar figure. Spend is bounded
structurally instead:

- one submit per invocation, with no resubmit on any failure path after the queue accepts;
- the script refuses to run again if `live_proof_summary.json` already records a submit
  (`--force` is required to override);
- the shortest supported Seedance duration (4 s) at the lowest resolution (480p) with audio
  disabled;
- a declared ceiling of $1.00 estimated against a $5.00 session cap, checked before submit.

Validation remains free: one authenticated GET against a queue-status URL with a random
request id, which creates no job.

## 7. Reproducing

```
python scripts/m30a_fal_budgeted_live_proof.py
```

Reads `FAL_API_KEY` (or `FAL_KEY` / `ADEPT_M30A_FAL_KEY`) from the repo-root `.env`. The key
is never printed; every fal error string is scrubbed for it before being logged or written
to the summary. The script exits non-zero without submitting if validation does not return
`verified`.

The Playwright live block is a separate, credential-only gate and still requires:

```
set ADEPT_M30A_FAL_LIVE=1
set ADEPT_M30A_FAL_KEY=<a real fal.ai key>
npx playwright test tests/e2e/m30a
```

That block asserts key acceptance and redaction. It does not submit a render.
