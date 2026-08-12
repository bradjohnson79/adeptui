# M5.0 — Co-Director Integration

| Field | Value |
| --- | --- |
| Milestone | `M5.0 Final E2E` |
| Branch | `feature/ai-guided-setup` |
| SHA | `fa09c99d6395c29461cdec4555055faad116c435` |
| Beta target | `http://127.0.0.1:8760/` and `http://127.0.0.1:8758/` |
| Verdict | **PARTIAL / NO-GO for final cert** |

## Summary

Co-Director is live, reachable, and persisting real status runs, but it is not strong enough to lift M5 final certification. The main blockers in this pass were creator-visible Beta smoke failure and degraded/slow status-check truth on the anchor project.

## Live Provider Status

`GET /api/codirector/providers/active/health` returned:

- `providerId=ollama`
- `status=Ready`
- `reachable=true`
- `selectedModel=gemma4:31b-it-qat`
- `modelAvailable=true`

This proves the selected Co-Director provider is reachable. It does **not** prove the full creator-facing status workflow is ready.

## Live Status-Check Evidence

### Timing samples

- repeated live probe: `POST /api/codirector/status/check` -> `15410.8 ms`, `15433.2 ms`
- later manual probe on anchor project -> `7109.5 ms`

### Latest persisted run

`GET /api/codirector/status/latest?projectId=e32dae30-a014-4ea4-a2f2-69f4b7809bde` returned a real persisted run:

- `runId=cdr_status_0882d106ef52`
- `partial=true`
- `startedAt=2026-08-02T16:35:19.337756+00:00`
- `completedAt=2026-08-02T16:35:26.391655+00:00`

Summary:

- `statusIndicator=Degraded`
- `score=82`
- `band=Fair`
- `healthyChecks=5`
- `warningChecks=5`
- `blockedChecks=0`

Dominant warning set:

- `capabilities.registry`
- `codirector.provider`
- `comfy.health`
- `image_runtime.readiness`
- `tools.registry`

## Smoke Result On Real Beta

The focused Beta-targeted Playwright run failed:

- `tests/e2e/codirector/codirector-status-cross-check.spec.ts`

The same spec passed on the isolated Playwright-managed local stack, so the problem is not the spec itself. For M5 final release truth, the Beta failure is the one that counts.

## Integration Reading

| Area | Result | Reading |
| --- | --- | --- |
| Provider reachability | `PASS` | Ollama and the selected model are reachable. |
| Status-run persistence | `PASS` | `latest` returns a real persisted run for the anchor project. |
| Status quality | `PARTIAL` | The run is real, but degraded and warning-heavy. |
| Status latency | `FAIL for final-cert quality` | `~7.1s` to `~15.4s` is too slow for a final creator readiness surface. |
| Creator-visible Beta smoke | `FAIL` | The Beta status panel/history smoke failed twice. |

## Verdict

**PARTIAL / NO-GO for final cert**

Co-Director integration is present and no longer appears absent or fake. It is still below final-release quality because the live Beta smoke fails and the real status-check path remains degraded and slow.
