# M42 W47 — Test Report

## Unit / contract (`studio-api/tests/test_m42_w47_docker_runtime.py`)

| Test | Result |
| --- | --- |
| Security rejects privileged / docker.sock / `:latest` | PASS |
| Core mandatory uninstall blocked | PASS |
| Workflow import never mutates core | PASS |
| Failed uninstall rolls back registry | PASS |
| Resolver no silent substitute | PASS |
| Dock models stamp `executionClass` | PASS |
| Queue hook `noSilentFallback` | PASS |
| Co-Director runtime.* tools bound | PASS |
| Gate binary flag present | PASS |

**Suite:** 9 passed (`ADEPT_DOCKER_RUNTIME_SIMULATE=1`).

## Playwright (`tests/e2e/m42/m42-w47-docker-runtime-extensions.spec.ts`)

Journeys A–M cover platform, registry, security, workflow inspect, Runtime Manager UI, Setup Add Custom Capability, Dock Native/Docker/Hosted, gate honesty, Co-Director tool catalog, executionClass stamp, reload isolation.

**Run against Beta (2026-08-02):** 12 passed, 1 flaky (H Dock sections — passed on retry). Suite exit 0.

```bash
npx playwright test tests/e2e/m42/m42-w47-docker-runtime-extensions.spec.ts
```

## Live Docker / GPU container evidence

**Not available on this host at certify time:** `docker` binary not on PATH; `daemonRunning=false`.  
Host GPU visible: `NVIDIA GeForce RTX 5090`.  
Simulate mode used for unit/API paths only — **does not satisfy** `dockerRuntimeExtensionsGo`.

Evidence: `artifacts/m42/w47/live-docker-status.json`, stamp: `artifacts/m42/w47/gate-stamp.json`.
