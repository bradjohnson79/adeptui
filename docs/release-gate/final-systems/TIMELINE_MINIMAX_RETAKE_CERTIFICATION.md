# Timeline MiniMax H3 Re-take — Certification Evidence

```text
GO — TIMELINE MINIMAX H3 RE-TAKE READY
```

## Scope

Phase — Timeline MiniMax Re-take (Final Systems locked gate).

## Evidence run

| Field | Value |
| --- | --- |
| Artifact dir | `docs/release-gate/final-systems/artifacts/retake-2026-08-05T04-39-30-669Z/` |
| Playwright | `tests/e2e/final-systems/timeline-minimax-retake.spec.ts` — **1 passed** (12.6s wall; H3 job ~4.3s) |
| Project | disposable `cc78b797-142a-4f49-be37-7f1edb9d7d88` (deleted after run) |
| Protected project | never mutated |
| Beta UI | `http://127.0.0.1:8760/` |
| Studio API | `http://127.0.0.1:8758/` |

## Checklist

| Requirement | Result |
| --- | --- |
| Re-take control on creator Timeline (`timeline-open-retake`) | PASS |
| Cancel attempt creates no ghost / alternate take | PASS (`after-cancel.json` takes.length = 1) |
| Successful Route A H3 generation | PASS (`success-job.json`, real MP4 + library import) |
| `apiUsed=false`, `ltxUsed=false`, private-local, route-a | PASS |
| Add as Alternate Take → Take 2 linked to Take 1 | PASS |
| Take 1 preserved | PASS |
| Activate Take 2 + reload persistence | PASS (`after-reload.json` activeTakeId = Take 2) |
| Edit history reversible entries | PASS (baseline / add_alternate / set_active) |
| Silent H3→LTX | not observed |

## GPU / Law 26

| Field | Value |
| --- | --- |
| Readiness | `ready=true`, `runtimeIsIsolatedRouteA=true` |
| Device | `cuda:0 NVIDIA GeForce RTX 5090 : cudaMallocAsync` |
| Profile | Experimental Private Profile (480×256, length 5, steps 4) |
| nvidia-smi (post-run sample) | RTX 5090, ~31 GB / 32 GB VRAM in use |
| Silent CPU fallback | No |
| Output | `Adept_H3_Private_1e0db47a_00001_.mp4` (decodePass, native audio AAC) |

## Creator Illusion / Product path notes

- Generation originated from Adept UI Timeline Re-take drawer + MiniMax H3 panel (product APIs only).
- Playwright did not open `:8192` or submit `/prompt` directly.
- Runtime orchestration remained behind Adept UI.

## Limitations

- Experimental Private Profile produces a short low-step clip (5 frames / ~0.2s container duration). This is the locked experimental profile, not a production-length ad.
- Baseline Take 1 was registered via product API before UI Re-take (allowed verification/setup); the successful Re-take generation and Add as Alternate were UI-driven.
