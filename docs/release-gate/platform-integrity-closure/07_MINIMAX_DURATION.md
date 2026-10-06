# 07 — Gate G MiniMax duration truth

**Surface:** BOTH (Route A profile + public preflight copy)  
**Date:** 2026-08-29

## Finding

Route A `length` is **frame count 5**, encoded at **24 fps**. Honest generated duration is `5/24 ≈ 0.21s`.

This is not 5 seconds and not 15 seconds. No 15s media was produced. No stretch / loop / metadata lie.

## Repair

Single source: `EXPERIMENTAL_LENGTH`, `EXPERIMENTAL_FPS`, `EXPERIMENTAL_DURATION_SEC` in `route_a_adapter.py`.

- Timeline adapters advertise `supportedDurations=[5/24]`. A 5s planned batch is refused (`DURATION_EXCEEDS_GENERATOR`) — no silent truncate.
- Collect-result duration uses probed `durationSeconds` when present, else the experimental duration — never hardcoded `5.0`.
- Public preflight no longer says clips “need” 4–15s. Hosted duration is disclosed as uncertified.
- Frontend `MINIMAX_ROUTE_A_DURATION_SEC` matches the same 5/24 value.

## Tests

`pytest tests/test_minimax_duration_truth.py app/minimax_h3/test_route_a_adapter.py -q`

**No measured 15s media.** Owner-testing should expect ~0.21s Route A clips.

## Peer close

- Kimi K3 (`47921dfb`): **PASS WITH NON-BLOCKING** — 15s is not claimed; honest limit is 5 frames @ 24 fps. Non-blocking: `generator_authority` still has a 5.0s fallback if the MiniMax adapter is unregistered. **ACCEPTED NON-BLOCKING** (adapter is registered on the live join).
- GLM 5.2 (`8bb07cc7`): **PASS WITH NON-BLOCKING** — live/source surfaces agree on ~0.21s. Non-blocking: `.runtime/verify-copy` adapters still hardcode `duration=5.0`. **ACCEPTED NON-BLOCKING** (sandbox copy, not the live Studio API).

**Gate G: CLOSED**
