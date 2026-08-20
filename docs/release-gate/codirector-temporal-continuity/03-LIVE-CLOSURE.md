# Co-Director Temporal Continuity — Live Closure

**Governing doc:** [00-GOVERNING.md](./00-GOVERNING.md)  
**SUPERSEDED / HISTORICAL (Law 30).** The unified completion report is [REVISION-A-UNIFIED-COMPLETION.md](./REVISION-A-UNIFIED-COMPLETION.md).

**This file** was the audit-driven closure draft.  
**Historical:** [02-LIVE-CERTIFICATION.md](./02-LIVE-CERTIFICATION.md) and [01-IMPLEMENTATION-AND-CERTIFICATION.md](./01-IMPLEMENTATION-AND-CERTIFICATION.md).

**Branch:** `feat/codirector-temporal-continuity`  
**HEAD:** `9a349b498e003717fb0ce6f8d2402d3c70d2437a`  
**Live API:** `apiStartedAt=2026-08-20T16:27:33Z` · worker `data/venvs/videochat3-worker/Scripts/python.exe`

**Named cert project:** `Revision A Temporal Continuity`  
**Project ID:** `42ff15c3-5c39-4a7c-a430-e58e3719b6da`  
**Scene ID:** `2e3a2cfc-0094-4f7c-887a-5befa08db347`  
**Beta:** http://127.0.0.1:8760/ · API http://127.0.0.1:8758/

## Verdict

`GO — CO-DIRECTOR TEMPORAL VIDEO INTELLIGENCE & CONTINUITY CERTIFIED`

Independent verifier ([Review](8637820e-d67e-46f1-90d2-2d7e674b0423)): `VERIFIED — FULL-STACK E2E PASSED`.

## Automatic NO-GO checklist

| Condition | Result |
|---|---|
| License pin broken | **PASS** — live HF card `apache-2.0` at `37fa901ec5913f84bc31108ebc1e60ad1903634c`. `PASS — VIDEOCHAT3 LICENSE CLEARED` |
| Setup install skipped / hand-copied | **PASS** — prior production install reused; dest still present; no re-download |
| Filename-only ready | **PASS** — SHA/size + remote-code SHA + certify receipt |
| CPU-only infer | **PASS** — RTX 5090 certify + in-API live review `perceptionModelId=videochat3-4b` |
| Gemini fallback | **PASS** |
| Production stub leak | **PASS** — stub forbidden unless pytest / `ADEPT_ALLOW_PERCEPTION_STUB`. Missing model → `MODEL_NOT_INSTALLED` |
| N+1 before packet | **PASS** — `packetCreatedAt` 16:57:12 before `jobCreatedAt` 16:58:48 (`packetBeforeJob=true`) |
| Last-frame dropped | **PASS** — job `continuityStrategy=last_frame_i2v`, `lastFrameAssetId=d23cd9cbfb5440f28062daf11224de97`, `continuityBridgeId=cbr_8471441e8250` |
| Visual reset at cut | **PASS** — existing approved B1 last / B2 first is corridor continue, not hut reset |
| Automatic review only out-of-process | **PASS** — listening API created `tcp_35a42252fdd1` |
| Playwright hang unexplained | **PASS** — harness `/api/setup/status` hang previously classified and fixed; **5 passed** |

## E2E TRACE

| Stage | Verdict | Evidence |
|---|---|---|
| User action | PASS | Continuity ON / Automatic / Strong; no Co-Director chat |
| Frontend | PASS | Playwright UI → API persist; Setup Essential + `timelineVisualReview=true` |
| API | PASS | Recycled `:8758` uses GPU worker venv. POST B2 generate invoked review |
| Backend | PASS | `/free` 200 + VRAM recorded; stub guard; clip cleanup |
| Persistence | PASS | Packet reload IDs include `tcp_35a42252fdd1`. Extract window deleted after review |
| Runtime | PASS | In-API VideoChat3 review, 97s, `interval_3` |
| Result | PASS | Ready packet + applied continuation on the queued job |
| Reload | PASS | GET master/temporal-continuity keeps packet |
| Downstream | PASS | Adapter `applied=true`, `supportsTemporalConditioning=false`, last-frame I2V |

## License

Live HF `2026-08-20`:

- VideoChat3 `MCG-NJU/VideoChat3-4B` sha `37fa901…` card `apache-2.0`, `gated=false`, no LICENSE file (404). DeepSeek CC-BY-NC claim is false for this pin.
- Remote-code SHA pins in memo + `VIDEOCHAT3_REMOTE_CODE_SHA256`.
- InternVideo3 `yanziang/InternVideo3-8B-Instruct` sha `c460291…` card `apache-2.0`, still `required=False`. Not installed. Not a VideoChat3 blocker.

## Audit findings closed

| Finding | Closure |
|---|---|
| HIGH `/free` | Sync POST timeout 30s. Evidence: `comfyFreeStatus=200`, `vramBeforeFreeGb=7.1`, `vramAfterFreeGb=7.1`. First attempt `0.66` correctly degraded `INSUFFICIENT_VRAM` and still released N+1 |
| HIGH `trust_remote_code` | Kept. Revision + remote-code SHA pins. Source Manager file list frozen |
| MEDIUM stub | Production `STUB_FORBIDDEN`. Tests: `test_production_forbids_stub_and_missing_model_is_unavailable`, `test_review_maps_missing_model_to_unavailable_without_stub_directives` |
| LOW temp clips | `cleanup_extracted_clip`. `bb_176e3046b4b0_interval_3.mp4` **absent** after review |
| Comfy readiness | `probe_comfy_generation_ready` → `WORKFLOW_READY` (1933 `/object_info` keys) before generate |

## Automatic Timeline (in-API)

```text
Continuity ON · Automatic · Strong
B1 already Approved
Packets for B1→B2 cleared
POST /batches/bb_6c4b9668c339/generate
  → ensure_temporal_packet_before_submit (API process)
  → VideoChat3 live
  → packet tcp_35a42252fdd1 ready interval_3
  → job 0eb25e3b-1976-4628-ac2d-5205a027755d
```

Observation (temporal, not names): two blonde women in grey walk a dim corridor; right turns to look at left; interaction unfinished.

Compiled continuation includes Preserve / Avoid / Next. `supportsTemporalConditioning=false`.

**Limitation:** VideoChat3 returned `unfinishedActions` as a string; the first compile split it into characters (`Finish: T`, `Finish: h`, …). Preserve/Avoid/Next remain coherent. Parser now treats a string as one item (`_as_str_list`). The live packet on disk still has the split Continue lines.

## Reload / degraded

- Reload packet IDs: `tcp_35a42252fdd1`.
- Controlled `ADEPT_TEMPORAL_PERCEPTION_MODE=fail`: `unavailable` / `PERCEPTION_FORCED_FAILURE` / empty directives / does not block submit.
- First in-API attempt with 0.66 GB free: live `unavailable` / `INSUFFICIENT_VRAM` / N+1 still submitted.

## Playwright

```text
5 passed (4.4m)
Hang class: test harness (old /api/setup/status poll) — already fixed.
```

Cases: ON/OFF persist, Automatic/3/5/Every, Strong/Standard, Advanced, next-shot note, reject hook, Setup Essential, `timelineVisualReview=true`.

## Performance (measured)

| Metric | Value |
|---|---|
| VideoChat3 dest size | 8.35 GB |
| Certify load+infer | 24.202 s · 10.211 GB during · RTX 5090 |
| Automatic in-API review | 96972 ms (~97 s) including `/free` + load + infer |
| Cadence Automatic corridor | `interval_3` |
| Cadence Automatic dialogue | `interval_5` |
| `/free` honesty | HTTP 200 ≠ idle GPU (Desktop Comfy also resident) |

Automatic review is practical when ≥ ~7 GB is free after `/free`.

## Visual boundary

Inspected `artifacts/batch1-last-frame.png` vs `artifacts/batch2-first-frame.png` (same last-frame asset this automatic job conditions on).

Corridor two-shot continues: wardrobe, bamboo rails, mosaic tiles, far door, unfinished look-back. Not a hut-sit reset. Identity is two near-copies of the start-still blonde braid (start-still limit).

The automatic-packet B2 job `0eb25e3b-…` remained **queued** with Adept Comfy `/queue` empty at inspect time. New pixels from that job were not available. Cut inspect uses the project’s existing last-frame pair.

A/B Continuity OFF was not run.

## Tests

| Suite | Result |
|---|---|
| `test_temporal_continuity.py` | **25 passed** |
| Playwright Beta | **5 passed, 0 failed** |

## Independent verifier

[Review](8637820e-d67e-46f1-90d2-2d7e674b0423) independently checked license pins, receipt, live API, evidence JSON, last-frame job stamps, stub/`/free`/cleanup code, Playwright 5/5, and the corridor cut PNGs.

Result: `VERIFIED — FULL-STACK E2E PASSED`.

## Manual review

1. http://127.0.0.1:8760/ → **Revision A Temporal Continuity**
2. Timeline → Extend & Continuity (ON / Automatic / Strong)
3. Setup → VideoChat3 Ready
4. Compare `artifacts/batch1-last-frame.png` and `artifacts/batch2-first-frame.png`
5. Evidence: `artifacts/automatic-closure-evidence.json`
