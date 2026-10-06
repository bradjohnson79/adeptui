# Adept Universal Generator Draft Preview + Cancel

**Status:** CONTRACT FROZEN — implementation in progress  
**Date:** 2026-09-07  
**Authority:** This is the single governing document for universal generator preview and cancellation. Historical investigation notes live under `.runtime/_universal_event_contract_proposal.md` and agent transcripts; they are not current product truth.

Investigation sources (READY FOR PRIMARY REVIEW, no production edits by investigators):

- [Provider capability inventory](af65fa78-10b9-424c-977a-5d2e51d0635b)
- [Canonical event contract design](918d709f-eeca-4f74-bc48-c3303b133a2c)
- [Cancellation semantics audit](954527a3-8f85-4328-bfb6-1012598e28b3)

---

## Product law

One shared contract from generator execution to Preview Monitor + Cancel UI.

- The frontend must not contain provider-specific preview or cancel logic (no `fal_` name matching).
- Capabilities come from adapter + Production Control metadata.
- Do not fake preview, progress, or cancel.
- Do not claim cost savings unless the provider documents them.
- `CANCEL_REQUESTED` is not `CANCELLED`.
- `CANCEL_REJECTED` is not `cancel_failed_runtime_active`.
- Certified MiniMax H3 Route A preview tap is frozen: no edits to `live_preview.py`, `preview_bus.py` internals, or `_poll_route_a_with_preview`.

Text to Video is text-only. No scene picker. No image / video / audio selection. 1 Frame and 3 Frame own stills. Timeline owns character and place references.

---

## Frozen decisions

### 1. Canonical event

`GeneratorRuntimeEvent` lives in:

- `studio-api/app/video_runtime/runtime_events.py`
- `studio-web/src/generatorRuntime/events.ts`

Event types: `PREPARING`, `PROGRESS`, `PREVIEW_FRAME`, `PREVIEW_VIDEO`, `FINALIZING`, `COMPLETED`, `CANCEL_REQUESTED`, `CANCELLED`, `CANCEL_REJECTED`, `FAILED`.

`progressPercent` is nullable. Coarse hosted buckets (`0.25`, `0.55`) map to `stage` only.

### 2. Transport

Reuse `GET /api/projects/{id}/preview/stream`. Add a `runtime_event` envelope beside legacy `preview_updated`. No third event bus.

### 3. Storage

Download hosted preview bytes into `preview_cache/{jobId}/`. Hotlink only as an exception with `expiresAt`. Per-job hosted cap: last 8 artifacts.

### 4. Hosted jobs get Studio Job rows

Timeline hosted submissions must create a lightweight `jobs` row so cancel, preview resume, Save Frame, and recycle re-attach share one `jobId`. In-memory `_HOSTED_JOBS` is not sufficient.

### 5. Cancel vocabulary

| State | Meaning |
| --- | --- |
| `CANCEL_REQUESTED` / `cancelling` | Creator asked; runtime halt in flight |
| `CANCELLED` | Runtime confirmed stopped (local) or provider confirmed cancelled (hosted) |
| `CANCEL_REJECTED` | Provider/runtime cannot or will not cancel; **job stays running** |
| `cancel_failed_runtime_active` | Local interrupt sent; prompt still active on the **correct** runtime |

`cancel_failed_runtime_active` must never be reused for “this API has no cancel.”

### 6. Cancel authority

`JobQueue.cancel_and_halt` is the single Studio cancel authority. It must classify the job before touching any runtime:

| Class | Runtime | Action |
| --- | --- | --- |
| `local_comfy` | Adept Comfy `:8188` | Existing `halt_prompt` (interrupt + queue delete + confirm + optional `/free`) |
| `route_a` | MiniMax H3 `:8192` | Same halt against Route A client. **No `/free`** (warm residency). Never interrupt `:8188`. |
| `hosted` | fal / Kie / other | Never interrupt `:8188` or `:8192`. Remote cancel only after a verified provider API. Otherwise `CANCEL_REJECTED`. |

Never treat `job.comfy_prompt_id` as a Comfy prompt when it holds a provider model id (`bytedance/…`, `fal-…`).

### 7. Capability flags (adapter truth)

`VideoGeneratorCapabilities` additive fields:

- `supportsLivePreview`
- `supportsHonestProgress`
- `supportsIntermediateFrames`
- `remoteCancelCostNote` (string or null — null unless the provider documents billing on cancel)

`draftPathway == "local_live"` implies the three preview flags unless an adapter overrides them.

Hosted Seedance / Kling / Veo remain:

- `supportsQueuedCancel=False`
- `supportsRunningCancel=False`
- `supportsLivePreview=False`
- `supportsHonestProgress=False`

`preview_bus.ENGINE_CAPS` must not claim `provider-thumbnail` or preview progress for fal engines until a fetcher exists.

### 8. Certified H3 path

Zero changes to:

- `studio-api/app/video_runtime/live_preview.py`
- `studio-api/app/minimax_h3/route_a_adapter.py` tap / submit
- `queue_worker._poll_route_a_with_preview`

A bridge may **subscribe** to PreviewBus and dual-emit `runtime_event`.

---

## Honesty inventory (current)

| Provider | Preview | Honest progress | Cancel | Persist |
| --- | --- | --- | --- | --- |
| MiniMax H3 Route A `:8192` | Live latent frames | Sampler fraction | Deep halt on `:8192` | `jobs` row |
| LTX / WAN / Hunyuan local | Live frames | Comfy WS | Deep halt on `:8188` | `jobs` row |
| Seedance 2.0 / 2.5 (fal) | None | Synthetic only — do not surface as percent | No remote cancel in Adept | Must gain a `jobs` row |
| Kling / Veo Timeline adapters | None | Fake | In-memory mark only | Stub — do not certify |
| Kie image tasks | None | State strings | Unsupported | `taskId` in `params_json` |

---

## Implementation slices

1. Freeze contract + capability flags + ENGINE_CAPS honesty + cancel runtime-class routing.
2. Canonical event bridge (subscribe-only on certified path).
3. Hosted Job row + `providerJobId` persistence + recycle re-attach.
4. Seedance: verify fal queue cancel against current fal docs; implement only with evidence; flip cancel flags only after a live proof.
5. Unified Preview Monitor + Cancel UI (capability-driven; keep Cancel below the monitor on 1F / 3F / T2V).
6. Co-Director / planner surfaces consume the same cancel states.
7. Playwright: local H3 cancel + Seedance honesty (cancel-rejected or real cancel, never a fake).
8. Independent review + binary GO / NO-GO.

---

## Explicit non-goals

- Do not restart, adopt, or replace Comfy `:8188`.
- Do not unload Route A models on cancel (`/free` forbidden on `:8192` cancel).
- Do not invent Seedance draft thumbnails.
- Do not disclose cancel cost until fal/Kie documentation is quoted in this file.

## Fal cancel evidence

fal.ai's queue API documents a real cancel endpoint for hosted (queue) requests:

- URL shape: `PUT https://queue.fal.run/{model_owner}/{model_name}/requests/{request_id}/cancel`
- Source: `https://fal.ai/docs/documentation/model-apis/inference/queue` ("Cancel a Request" section)
- OpenAPI: `https://raw.githubusercontent.com/api-evangelist/fal-ai/refs/heads/main/openapi/fal-ai-queue-api-openapi.yml`

Quoted behavior from the live docs (retrieved 2026-09-07):

> Cancel a request. What happens depends on the request's state:
> - Still in the queue (IN_QUEUE): The request is removed immediately and is never processed.
> - Already being processed (IN_PROGRESS): fal sends a cancellation signal to the runner. The request may still complete if the app does not handle cancellation.
>
> | HTTP Status | JSON Body | Meaning |
> | --- | --- | --- |
> | `202 Accepted` | `{"status": "CANCELLATION_REQUESTED"}` | Cancel accepted. The request may still complete if it was already mid-processing. |
> | `400 Bad Request` | `{"status": "ALREADY_COMPLETED"}` | The request already finished before the cancel arrived. |
> | `404 Not Found` | `{"status": "NOT_FOUND"}` | No request exists with that ID. |

The docs do not mention billing/credits/refunds for cancelled requests, so any cost claim for a cancelled Seedance job remains `UNKNOWN`.

Implementation impact:

- `studio-api/app/fal_client.py` gained `cancel_fal_request(model_id, request_id, api_key)` which performs the documented `PUT` and surfaces 400/404 as errors.
- `studio-api/app/director_timeline_w46/generation/adapters/seedance_api.py` `cancel()` now calls that helper for live records, records `cancelRejected` / `PROVIDER_CANCEL_UNSUPPORTED` on failure, and leaves the in-memory job running when the provider rejects.
- `VideoGeneratorCapabilities` flags for Seedance remain `supportsQueuedCancel=False` and `supportsRunningCancel=False` by this frozen contract; the remote helper is wired but not advertised as a user-facing capability until the cancel authority is integrated end-to-end.
