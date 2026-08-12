# M42 W47 — Shared Contracts

Schema version: **1**

Parity paths:

- Python: `studio-api/app/docker_runtime/contracts.py`
- TypeScript: `studio-web/src/dockerRuntime/contracts.ts`
- JSON freeze: `artifacts/m42/w47/shared_contracts.json`

## Classifications

`core_mandatory` | `official_optional` | `user_added`

## Readiness (user-added)

`unverified` | `inspecting` | `building` | `installing` | `testing` | `tested_locally` | `ready` | `disabled` | `update_available` | `degraded` | `error` | `requires_repair`

Never auto-label user-added as `Certified`.

## Dock execution class

Additive on `ModelDescriptor`: `executionClass: native_local | docker_local | hosted_api`

Back-compat: native/docker → `locality: local`; hosted → `hosted`.

## Contract change process

change request → impact analysis → primary approval → Python/TS parity → dependent-agent notification → tests updated.
