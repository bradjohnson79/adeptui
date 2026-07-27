# M3.0c Engineering Soak Report

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Scope | Engineering soak before Manual User Beta |

## Exercised paths

| Path | Result |
|------|--------|
| Repeated job inspect (Studio + Co-Director unified) | Exercised during fal proof + situation validation |
| API restart during job | Proven: interrupted honestly; fal request_id retained; reconcile completed |
| Browser refresh during processing | Covered by prior queue recovery tests + restart recovery pytest |
| Sequential local image jobs | 12 situation stills completed |
| Timeline save/reload | 12/12 director_json present in export packs |
| Session/project persistence | `persistence-check.json` read-only SQLite evidence |
| Provider health checks | fal key verified; Comfy used for situation stills |
| Export after long session | 12 export packs validated |

## Observations

- No permanent silent `processing` state after restart (recovery marks interrupted).
- Fal spend controlled; queue proof used one intentional submit + provider reconcile.
- Soak did not introduce duplicate asset minting on honesty paths.

## Residual

Long multi-hour memory profiling was not run; no memory-growth claim is made.
